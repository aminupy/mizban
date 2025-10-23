from core import utils, server
from config import settings


def main():
    url = utils.get_server_url(settings.PORT)
    print("\n🚀  Mizban — LAN File Sharing Server\n")
    print(f"📂  Shared folder : {settings.MIZBAN_SHARED_DIR}")
    print(f"🌐  Access URL    : {url}")
    print("📱  QR code       : Scan below to open in your mobile browser\n")
    utils.print_qr_code(url)

    server.start_server()


if __name__ == "__main__":
    main()