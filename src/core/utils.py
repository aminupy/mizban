import socket
from pathlib import Path
import logging

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

logger = logging.getLogger("mizban")


def get_server_url(port: int) -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        sock.close()
    return f"http://{ip}:{port}/"


def generate_thumbnail(src_path: Path, dest_path: Path) -> None:
    if not PIL_AVAILABLE:
        return
    try:
        if src_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".svg"):
            with Image.open(src_path) as img:
                img = img.convert('RGB')
                img.thumbnail((200, 200))
                img.save(dest_path, "JPEG")
    except Exception as e:
        logger.warning(f"Thumbnail failed for {src_path}: {e}")


def print_qr_code(data: str) -> None:
    if not QR_AVAILABLE:
        print("(Install `qrcode` to enable QR code)")
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
