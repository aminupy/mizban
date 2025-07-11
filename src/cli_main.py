from core import get_server_url, print_qr_code, start_server, UPLOAD_DIR


def main():
    url = get_server_url()
    print("\n🚀  Mizban — LAN File Sharing Server\n")
    print(f"📂  Shared folder : {UPLOAD_DIR}")
    print(f"🌐  Access URL    : {url}")
    print("📱  QR code       : Scan below to open in your mobile browser\n")
    print_qr_code(url)

    start_server()


if __name__ == "__main__":
    main()