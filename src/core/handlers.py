import functools
import json
import logging
import mimetypes
import shutil
import urllib.parse
import cgi
from contextlib import suppress
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler
from pathlib import Path, PurePosixPath

from .utils import generate_thumbnail

logger = logging.getLogger("mizban")


MAX_UPLOAD_BYTES = 4 * 1024 * 1024 * 1024  # 4 GiB
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES + (10 * 1024 * 1024)  # allow some multipart overhead
UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MiB
MAX_HEADER_LINE = 16 * 1024
DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class UploadError(Exception):
    """Raised for controlled upload failures."""

    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def ensure_storages_exists(func):
    """
    A decorator that ensures the shared directory exists before executing
    the decorated class method.
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # 'self' is the instance of MizbanHandler
        try:
            # The core logic: create the directory if it doesn't exist.
            self.shared_dir.mkdir(parents=True, exist_ok=True)
            self.thumb_dir.mkdir(parents=True, exist_ok=True)
            self._shared_root = self.shared_dir.resolve()
            self._thumb_root = self.thumb_dir.resolve()
        except PermissionError:
            # Handle the case where we can't create the directory
            logger.error(f"Permission denied to create directory: {self.shared_dir}")
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Storage permission error.")
            return # Stop execution
        except Exception as e:
            logger.error(f"Failed to create shared directory: {e}")
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Storage configuration error.")
            return

        # If everything is okay, run the original method (do_POST or do_GET)
        return func(self, *args, **kwargs)
    return wrapper


class MizbanHandler(SimpleHTTPRequestHandler):
    # __init__ is updated to accept the directory parameter correctly
    def __init__(self, *args, shared_dir: Path, thumb_dir: Path, directory=None, **kwargs):
        self.shared_dir = shared_dir
        self.thumb_dir = thumb_dir
        try:
            self._shared_root = shared_dir.resolve()
        except FileNotFoundError:
            shared_dir.mkdir(parents=True, exist_ok=True)
            self._shared_root = shared_dir.resolve()
        try:
            self._thumb_root = thumb_dir.resolve()
        except FileNotFoundError:
            thumb_dir.mkdir(parents=True, exist_ok=True)
            self._thumb_root = thumb_dir.resolve()
        # Pass the directory to the parent class for serving frontend files
        super().__init__(*args, directory=directory, **kwargs)

    @ensure_storages_exists
    def do_POST(self):
        """
        Handles streaming file uploads without loading the whole file into memory.
        """
        if self.path != "/upload/":
            return self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

        try:
            filename, dest_path, bytes_written = self._handle_file_upload()
        except UploadError as exc:
            logger.warning("Upload rejected from %s: %s", self.client_address[0], exc.message)
            self.send_error(exc.status, exc.message)
            return
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error during upload: %s", exc)
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Failed to save file.")
            return

        logger.info("Received file %s (%d bytes)", filename, bytes_written)
        thumb_path = self._thumb_root / f"{filename}.jpg"
        generate_thumbnail(dest_path, thumb_path)
        self._send_json({"filename": filename, "message": "Uploaded"}, HTTPStatus.CREATED)

    
    def do_HEAD(self):
        """
        Handles HEAD requests. This is used by the frontend to check if a 
        file exists before starting a download, without fetching the file body.
        """
        # We reuse the same logic as GET but send only headers
        path = self._get_path_for_request()
        if path:
            self._send_file_headers(path)
        else:
            # If path is not a file to serve, let the parent handle it (e.g., for index.html)
            super().do_HEAD()


    @ensure_storages_exists
    def do_GET(self):
        """Handles GET requests for downloads, thumbnails, and API calls."""
        path = self._get_path_for_request()
        if path:
            self._serve_file(path)
        elif urllib.parse.urlsplit(self.path).path == "/files/":
            files = [f.name for f in self.shared_dir.iterdir() if f.is_file()]
            self._send_json({"files": files})
        else:
            # Fallback to serving frontend files
            super().do_GET()

    def _get_path_for_request(self) -> Path | None:
        """Helper to determine the file path from the request URL."""
        route = urllib.parse.urlsplit(self.path).path
        if route.startswith("/download/"):
            relative = route.removeprefix("/download/")
            if not relative:
                return None
            candidate = self._safe_join(self._shared_root, relative)
            if candidate is None:
                return None
            return candidate
        if route.startswith("/thumbnails/"):
            relative = route.removeprefix("/thumbnails/")
            if not relative:
                return None
            candidate = self._safe_join(self._thumb_root, f"{relative}.jpg")
            if candidate is None:
                return None
            return candidate
        return None

    def _send_file_headers(self, path: Path):
        """Sends the HTTP headers for a file response."""
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return False

        try:
            stat_result = path.stat()
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not accessible")
            return False

        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(stat_result.st_size))
        self.end_headers()
        return True

    def _serve_file(self, path: Path):
        """Sends the headers and body for a file."""
        if not self._send_file_headers(path):
            return
        try:
            with path.open("rb") as src:
                shutil.copyfileobj(src, self.wfile, length=DOWNLOAD_CHUNK_SIZE)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            logger.info("Client disconnected while downloading %s", path.name)
        except Exception as exc:
            logger.error("Error serving file %s: %s", path, exc)

    def _send_json(self, obj, status=HTTPStatus.OK):
        try:
            data = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            logger.error(f"Error sending JSON: {e}")

    def log_message(self, format, *args):
        logger.info("%s - %s" % (self.client_address[0], format % args))

    # --- Upload helpers -------------------------------------------------

    def _handle_file_upload(self) -> tuple[str, int]:
        content_length_header = self.headers.get("Content-Length")
        if content_length_header is None:
            raise UploadError(HTTPStatus.LENGTH_REQUIRED, "Missing Content-Length header.")
        try:
            content_length = int(content_length_header)
        except ValueError as exc:
            raise UploadError(HTTPStatus.BAD_REQUEST, "Invalid Content-Length header.") from exc

        if content_length <= 0:
            raise UploadError(HTTPStatus.BAD_REQUEST, "Empty upload.")
        if content_length > MAX_REQUEST_BYTES:
            limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
            raise UploadError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                f"Upload exceeds limit of {limit_mb} MB."
            )

        content_type = self.headers.get("Content-Type", "")
        ctype, params = cgi.parse_header(content_type)
        if ctype != "multipart/form-data":
            raise UploadError(HTTPStatus.BAD_REQUEST, "Expected multipart/form-data.")

        boundary = params.get("boundary")
        if not boundary:
            raise UploadError(HTTPStatus.BAD_REQUEST, "Multipart boundary not found.")
        try:
            boundary_bytes = boundary.encode("ascii")
        except UnicodeEncodeError as exc:
            raise UploadError(HTTPStatus.BAD_REQUEST, "Multipart boundary must be ASCII.") from exc

        filename, remaining = self._parse_multipart_headers(boundary_bytes, content_length)
        dest_path, bytes_written = self._stream_file(boundary_bytes, remaining, filename)
        return filename, dest_path, bytes_written

    def _parse_multipart_headers(self, boundary: bytes, content_length: int) -> tuple[str, int]:
        boundary_line = b"--" + boundary
        remaining = content_length

        # Read opening boundary line
        line, remaining = self._readline(remaining)
        while line in (b"\r\n", b"\n"):
            line, remaining = self._readline(remaining)
        if line.rstrip(b"\r\n") != boundary_line:
            raise UploadError(HTTPStatus.BAD_REQUEST, "Malformed multipart payload.")

        headers: dict[str, str] = {}
        while True:
            line, remaining = self._readline(remaining)
            stripped = line.rstrip(b"\r\n")
            if not stripped:
                break
            if b":" not in stripped:
                raise UploadError(HTTPStatus.BAD_REQUEST, "Invalid multipart header line.")
            raw_key, raw_value = stripped.split(b":", 1)
            key = raw_key.decode("latin-1").strip().lower()
            value = raw_value.decode("latin-1").strip()
            headers[key] = value
            if len(headers) > 16:
                raise UploadError(HTTPStatus.BAD_REQUEST, "Too many multipart headers.")

        disposition = headers.get("content-disposition")
        if not disposition:
            raise UploadError(HTTPStatus.BAD_REQUEST, "Missing Content-Disposition header.")

        disp_type, disp_params = cgi.parse_header(disposition)
        if disp_type != "form-data":
            raise UploadError(HTTPStatus.BAD_REQUEST, "Unsupported Content-Disposition.")
        field_name = disp_params.get("name")
        if field_name != "file":
            raise UploadError(HTTPStatus.BAD_REQUEST, "Unexpected form field.")

        filename = disp_params.get("filename")
        if not filename:
            raise UploadError(HTTPStatus.BAD_REQUEST, "No file provided.")
        filename = Path(filename).name
        if not filename:
            raise UploadError(HTTPStatus.BAD_REQUEST, "Invalid file name.")

        return filename, remaining

    def _stream_file(self, boundary: bytes, remaining: int, filename: str) -> tuple[Path, int]:
        closing_marker = b"\r\n--" + boundary + b"--"
        closing_marker_with_crlf = closing_marker + b"\r\n"
        guard = len(closing_marker_with_crlf) + 4

        dest_path = self._safe_join(self._shared_root, filename)
        if dest_path is None:
            raise UploadError(HTTPStatus.BAD_REQUEST, "Invalid destination path.")

        bytes_written = 0
        buffer = bytearray()
        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with dest_path.open("wb") as dst:
                while True:
                    if remaining <= 0:
                        raise UploadError(HTTPStatus.BAD_REQUEST, "Unexpected end of upload stream.")

                    chunk = self.rfile.read(min(UPLOAD_CHUNK_SIZE, remaining))
                    if not chunk:
                        raise UploadError(HTTPStatus.BAD_REQUEST, "Upload stream terminated unexpectedly.")
                    remaining -= len(chunk)
                    buffer.extend(chunk)

                    marker_index, marker_length = self._find_closing_marker(buffer, closing_marker_with_crlf, closing_marker)
                    if marker_index == -1:
                        flush_len = len(buffer) - guard
                        if flush_len > 0:
                            dst.write(buffer[:flush_len])
                            bytes_written += flush_len
                            self._enforce_upload_limit(bytes_written)
                            del buffer[:flush_len]
                        continue

                    data = buffer[:marker_index]
                    if data:
                        dst.write(data)
                        bytes_written += len(data)
                        self._enforce_upload_limit(bytes_written)

                    del buffer[:marker_index + marker_length]
                    if buffer.startswith(b"\r\n"):
                        del buffer[:2]
                    break

            if buffer.strip(b"\r\n\t "):
                raise UploadError(HTTPStatus.BAD_REQUEST, "Unexpected multipart trailer.")
        except Exception:
            with suppress(FileNotFoundError):
                dest_path.unlink()
            raise

        self._discard_stream(remaining)
        return dest_path, bytes_written

    def _find_closing_marker(
        self,
        buffer: bytearray,
        marker_with_crlf: bytes,
        marker_without_crlf: bytes,
    ) -> tuple[int, int]:
        idx = buffer.find(marker_with_crlf)
        if idx != -1:
            return idx, len(marker_with_crlf)
        idx = buffer.find(marker_without_crlf)
        if idx != -1:
            return idx, len(marker_without_crlf)
        return -1, 0

    def _enforce_upload_limit(self, bytes_written: int) -> None:
        if bytes_written > MAX_UPLOAD_BYTES:
            limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
            raise UploadError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                f"Upload exceeds limit of {limit_mb} MB."
            )

    def _readline(self, remaining: int) -> tuple[bytes, int]:
        if remaining <= 0:
            raise UploadError(HTTPStatus.BAD_REQUEST, "Unexpected end of upload stream.")
        line = self.rfile.readline(MAX_HEADER_LINE + 1)
        if not line:
            raise UploadError(HTTPStatus.BAD_REQUEST, "Upload stream terminated unexpectedly.")
        if len(line) > MAX_HEADER_LINE:
            raise UploadError(HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE, "Multipart header line too long.")
        remaining -= len(line)
        if remaining < 0:
            raise UploadError(HTTPStatus.BAD_REQUEST, "Malformed multipart body.")
        return line, remaining

    def _discard_stream(self, remaining: int) -> None:
        while remaining > 0:
            chunk = self.rfile.read(min(UPLOAD_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
        if remaining > 0:
            raise UploadError(HTTPStatus.BAD_REQUEST, "Incomplete multipart payload.")

    def _safe_join(self, base_root: Path, relative: str) -> Path | None:
        decoded = urllib.parse.unquote(relative)
        if "\x00" in decoded:
            return None
        rel_path = PurePosixPath(decoded.replace("\\", "/"))
        if rel_path.is_absolute():
            return None

        parts: list[str] = []
        for part in rel_path.parts:
            if part in ("", "."):
                continue
            if part == "..":
                return None
            parts.append(part)

        if not parts:
            return None

        candidate = base_root.joinpath(*parts)
        try:
            resolved = candidate.resolve(strict=False)
        except OSError:
            resolved = candidate

        if not resolved.is_relative_to(base_root):
            return None
        return resolved
