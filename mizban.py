import json
import logging
import mimetypes
import os
import socket
import sys
import threading
import urllib.parse
import gui
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Optional dependencies
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

# ─── Configuration ───────────────────────────────────────────────────────────

HOST = "0.0.0.0"
PORT = int(os.environ.get("MIZBAN_PORT", 8000))

BASE_DIR = Path(__file__).parent.resolve()
UPLOAD_DIR = Path.home() / "Desktop" / "MizbanShared"
THUMBNAIL_DIR = UPLOAD_DIR / ".thumbnails"
FRONTEND_DIR = BASE_DIR / "clients" / "frontend"

for d in (UPLOAD_DIR, THUMBNAIL_DIR):
    try:
        d.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        print(f"Cannot create {d!r}: {e}")
        sys.exit(1)

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.CRITICAL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mizban")

# ─── Utilities ───────────────────────────────────────────────────────────────


def get_server_url() -> str:
    """Determine local LAN IP + port for sharing."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        sock.close()
    return f"http://{ip}:{PORT}/"


def generate_thumbnail(src_path: Path) -> None:
    """Generate a 200x200 JPEG thumbnail if Pillow is installed."""
    if not PIL_AVAILABLE:
        return
    try:
        if src_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".svg"):
            thumb = THUMBNAIL_DIR / f"{src_path.name}.jpg"
            with Image.open(src_path) as img:
                img = img.convert('RGB')
                img.thumbnail((200, 200))
                img.save(thumb, "JPEG")
                logger.debug(f"Thumbnail saved: {thumb}")
    except Exception as e:
        logger.warning(f"Thumbnail failed for {src_path}: {e}")


def print_qr_code(data: str) -> None:
    """Prints ASCII QR code in terminal."""
    if not QR_AVAILABLE:
        print("(Install `qrcode` module to see QR code)")
        return
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr.print_ascii(invert=True)


# ─── HTTP Handler ────────────────────────────────────────────────────────────


class MizbanHandler(SimpleHTTPRequestHandler):
    """Serves APIs and static files from frontend."""

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

                dest = UPLOAD_DIR / filename
                with open(dest, "wb") as f:
                    f.write(body)
                generate_thumbnail(dest)

                response = {"filename": filename, "message": "Uploaded"}
                self._send_json(response, HTTPStatus.CREATED)
                return

        self.send_error(HTTPStatus.BAD_REQUEST, "No file found")

    def do_GET(self):
        if self.path.startswith("/download/"):
            name = urllib.parse.unquote(self.path.removeprefix("/download/"))
            return self._serve_file(UPLOAD_DIR / name)

        if self.path.startswith("/thumbnails/"):
            name = self.path.removeprefix("/thumbnails/")
            return self._serve_file(THUMBNAIL_DIR / f"{name}.jpg")

        if self.path == "/files/":
            files = [f.name for f in UPLOAD_DIR.iterdir() if f.is_file()]
            return self._send_json({"files": files})

        self.path = "/" + self.path.lstrip("/")
        return super().do_GET()

    def _serve_file(self, path: Path):
        if not path.exists() or not path.is_file():
            return self.send_error(HTTPStatus.NOT_FOUND, "Not found")
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


# ─── Server Startup ─────────────────────────────────────────────────────────


def main():
    os.chdir(FRONTEND_DIR)  # Serve frontend files
    server = ThreadingHTTPServer((HOST, PORT), MizbanHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        server.server_close()


if __name__ == "__main__":
    threading.Thread(target=gui.start_gui, daemon=True).start()
    main()