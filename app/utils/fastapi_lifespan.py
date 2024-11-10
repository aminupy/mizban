import asyncio
import webbrowser
from typing import AsyncGenerator

from app.core import settings
from app.utils.network_util import get_server_url
from app.utils.qrcode_util import generate_qr_code


async def lifespan(app) -> AsyncGenerator:
    # Startup actions

    url = get_server_url()

    print(f" Welcome to Mizban! 🚀 \n Your fast & light file-sharing server \n\n")
    print(f" Mizban uses {settings.UPLOAD_DIR} as the shared folder. \n")
    print(f" For access to the server, please visit: {url}")
    print(f" Or scan the QR code below: \n\n")

    generate_qr_code(url)

    # Open the web browser asynchronously to avoid blocking
    loop = asyncio.get_event_loop()
    loop.call_later(1, webbrowser.open, url)

    yield  # Control returns to the application

    # Shutdown actions
    print("Shutting down Mizban server...")
    print("Goodbye! 👋")
