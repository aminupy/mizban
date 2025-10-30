import sys

from core import server, utils
from config import settings


def main() -> None:
    try:
        http_server = server.create_server()
    except OSError as exc:
        print(f"\n!! Unable to start Mizban server on {settings.HOST}:{settings.PORT}.\n   {exc}")
        sys.exit(1)

    actual_port = http_server.server_address[1]
    url = utils.get_server_url(actual_port)
    print("\n🚀  Mizban - LAN File Sharing Server\n")
    print(f"📂  Shared folder : {settings.MIZBAN_SHARED_DIR}")
    print(f"🌐  Access URL    : {url}")
    print("📱  QR code       : Scan below to open in your mobile browser\n")
    utils.print_qr_code(url)

    server.serve_forever(http_server)


if __name__ == "__main__":
    main()
