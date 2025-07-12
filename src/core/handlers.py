
import json
import mimetypes
import urllib.parse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
import logging

from .utils import generate_thumbnail

logger = logging.getLogger("mizban")


class MizbanHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, shared_dir: Path, thumb_dir: Path, **kwargs):
        self.shared_dir = shared_dir
        self.thumb_dir = thumb_dir
        super().__init__(*args, **kwargs)

    def do_POST(self):
        if self.path != "/upload/":
            return self.send_error(HTTPStatus.NOT_FOUND)

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            return self.send_error(HTTPStatus.BAD_REQUEST, "Invalid Content-Type")

        boundary = content_type.split("boundary=")[-1]
        remain = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(remain)

        delimiter = f"--{boundary}".encode()
        parts = data.split(delimiter)

        for part in parts:
            if b"Content-Disposition" in part:
                header, body = part.split(b"\r\n\r\n", 1)
                body = body.rstrip(b"\r\n--")
                for line in header.decode().split("\r\n"):
                    if "filename=" in line:
                        filename = line.split("filename=")[-1].strip('"')
                        break
                else:
                    continue

                dest = self.shared_dir / filename
                with open(dest, "wb") as f:
                    f.write(body)
                thumb = self.thumb_dir / f"{filename}.jpg"
                generate_thumbnail(dest, thumb)

                self._send_json({"filename": filename, "message": "Uploaded"}, HTTPStatus.CREATED)
                return

        self.send_error(HTTPStatus.BAD_REQUEST, "No file found")

    def do_GET(self):
        if self.path.startswith("/download/"):
            name = urllib.parse.unquote(self.path.removeprefix("/download/"))
            return self._serve_file(self.shared_dir / name)

        if self.path.startswith("/thumbnails/"):
            name = self.path.removeprefix("/thumbnails/")
            return self._serve_file(self.thumb_dir / f"{name}.jpg")

        if self.path == "/files/":
            files = [f.name for f in self.shared_dir.iterdir() if f.is_file()]
            return self._send_json({"files": files})

        self.path = "/" + self.path.lstrip("/")
        return super().do_GET()

    def _serve_file(self, path: Path):
        if not path.exists() or not path.is_file():
            return self.send_error(HTTPStatus.NOT_FOUND)
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        with open(path, "rb") as f:
            self.wfile.write(f.read())

    def _send_json(self, obj, status=HTTPStatus.OK):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        logger.info("%s - %s" % (self.client_address[0], format % args))
