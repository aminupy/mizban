from __future__ import annotations

import sys
from http.server import ThreadingHTTPServer
from typing import Tuple

from config import settings
from core import server, utils


def _banner_icons() -> Tuple[str, str, str, str]:
    """Return glyphs (emoji or ASCII fallbacks) suitable for the active console."""
    if utils.stream_supports_unicode(sys.stdout):
        return "🚀", "📂", "🌐", "📱"
    return "[MZ]", "[DIR]", "[URL]", "[QR]"


def _print_banner(shared_dir: str, url: str) -> None:
    rocket, folder_icon, globe_icon, phone_icon = _banner_icons()
    print(f"\n{rocket}  Mizban - LAN File Sharing Server\n")
    print(f"{folder_icon}  Shared folder : {shared_dir}")
    print(f"{globe_icon}  Access URL    : {url}")
    print(f"{phone_icon}  QR code       : Scan below to open in your mobile browser\n")


def run(http_server: ThreadingHTTPServer | None = None) -> None:
    """Start the CLI server, optionally using a pre-existing HTTP server."""
    if http_server is None:
        try:
            http_server = server.create_server()
        except OSError as exc:
            print(
                f"\n!! Unable to start Mizban server on {settings.HOST}:{settings.PORT}.\n   {exc}"
            )
            sys.exit(1)

    actual_port = http_server.server_address[1]
    url = utils.get_server_url(actual_port)
    _print_banner(str(settings.MIZBAN_SHARED_DIR), url)
    utils.print_qr_code(url)

    server.serve_forever(http_server)


def main() -> None:
    run()


if __name__ == "__main__":
    main()
