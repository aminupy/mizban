import io
import logging
import os
import socket
import sys
from pathlib import Path
from typing import TextIO

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
    """Return a LAN-accessible URL without requiring Internet access.

    Attempts to detect a non-loopback IPv4 from local interfaces, then falls
    back to a UDP connect trick that doesn't send packets, and finally to
    localhost.
    """
    ip = None
    try:
        # Prefer interface-derived addresses (non-loopback)
        host = socket.gethostname()
        addrs = socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_DGRAM)
        for info in addrs:
            cand = info[4][0]
            if not cand.startswith("127."):
                ip = cand
                break
    except Exception:
        pass

    if not ip:
        try:
            # UDP connect trick that doesn't require Internet
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("10.255.255.255", 1))
                ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"

    return f"http://{ip}:{port}/"


def stream_supports_unicode(stream: TextIO | None) -> bool:
    """Return True when the stream's encoding can display Unicode glyphs."""
    if stream is None:
        return True
    encoding = getattr(stream, "encoding", None)
    if not encoding:
        return True
    try:
        "🚀📂🌐📱".encode(encoding, errors="strict")
    except UnicodeEncodeError:
        return False
    except Exception:
        return False
    return True



def generate_thumbnail(src_path: Path, dest_path: Path) -> None:
    if not PIL_AVAILABLE:
        return
    try:
        # Skip SVG as Pillow cannot rasterize it without additional deps
        if src_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif"):
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



def generate_qr_ascii(data: str) -> str:
    """
    Generates a compact ASCII QR code and returns it as a string.
    """
    if not QR_AVAILABLE:
        return "(Install `qrcode` to enable QR code)"
        
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        # box_size=5,  # Keeps the blocks small
        border=1,    # Reduced from 2 to make the overall code more compact
    )
    qr.add_data(data)
    qr.make(fit=True)

    # Use a string buffer to capture the output directly
    output_buffer = io.StringIO()
    qr.print_ascii(out=output_buffer, invert=True)
    
    return output_buffer.getvalue()


def open_folder(path):
    """Opens a directory in the default file explorer."""
    Path(path).mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform.startswith('linux'):
            os.system(f'xdg-open "{path}"')
        elif sys.platform == "darwin":  # macOS
            os.system(f'open "{path}"')
        elif sys.platform == "win32":
            os.startfile(path)
    except Exception as e:
        print(f"Error opening folder: {e}")
