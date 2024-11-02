import webbrowser
from app.utils.network_util import get_ip_address
from app.utils.qrcode_util import generate_qr_code
from app.core.config import settings

def start():
    ip = get_ip_address()

    print(f' Welcome to Mizban! 🚀 \n Your fast & light file-sharing server \n\n')
    print(f' Mizban uses {settings.UPLOAD_DIR} as the shared folder. \n')
    print(f' For access to the server, please visit: http://{ip}:8000')
    print(f' Or scan the QR code below: \n\n')
    generate_qr_code(f'http://{ip}:8000')
    webbrowser.open(f'http://{ip}:8000')