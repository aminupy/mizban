import json
import mimetypes
import urllib.parse
import cgi
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
import logging

from .utils import generate_thumbnail

logger = logging.getLogger("mizban")


import functools

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
        # Pass the directory to the parent class for serving frontend files
        super().__init__(*args, directory=directory, **kwargs)

    @ensure_storages_exists
    def do_POST(self):
        """
        Handles streaming file uploads without loading the whole file into memory.
        """
        if self.path != "/upload/":
            return self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

        # Use cgi.FieldStorage for robust multipart/form-data parsing
        # It correctly handles streaming data from self.rfile
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': self.headers['Content-Type']}
        )

        if 'file' not in form:
            return self.send_error(HTTPStatus.BAD_REQUEST, "File field 'file' not found in form.")

        file_item = form['file']
        if not file_item.filename:
            return self.send_error(HTTPStatus.BAD_REQUEST, "No file selected for upload.")

        # Sanitize filename to prevent directory traversal attacks
        filename = Path(file_item.filename).name
        dest_path = self.shared_dir / filename
        
        chunk_size = 8192 # Read and write in 8KB chunks
        bytes_written = 0
        try:
            with open(dest_path, 'wb') as f:
                while True:
                    chunk = file_item.file.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_written += len(chunk)

            logger.info(f"Received file: {filename}, size: {bytes_written} bytes")

            # Generate thumbnail after successful upload
            thumb_path = self.thumb_dir / f"{filename}.jpg"
            generate_thumbnail(dest_path, thumb_path)

            self._send_json({"filename": filename, "message": "Uploaded"}, HTTPStatus.CREATED)
            
        except Exception as e:
            logger.error(f"Error during file upload: {e}")
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Failed to save file.")

    
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
        elif self.path == "/files/":
            files = [f.name for f in self.shared_dir.iterdir() if f.is_file()]
            self._send_json({"files": files})
        else:
            # Fallback to serving frontend files
            super().do_GET()

    def _get_path_for_request(self) -> Path | None:
        """Helper to determine the file path from the request URL."""
        if self.path.startswith("/download/"):
            name = urllib.parse.unquote(self.path.removeprefix("/download/"))
            return self.shared_dir / name
        if self.path.startswith("/thumbnails/"):
            name = self.path.removeprefix("/thumbnails/")
            return self.thumb_dir / f"{name}.jpg"
        return None

    def _send_file_headers(self, path: Path):
        """Sends the HTTP headers for a file response."""
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return False
        
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        return True

    def _serve_file(self, path: Path):
        """Sends the headers and body for a file."""
        if not self._send_file_headers(path):
            return
        try:
            with open(path, "rb") as f:
                self.wfile.write(f.read())
        except Exception as e:
            logger.error(f"Error serving file {path}: {e}")

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