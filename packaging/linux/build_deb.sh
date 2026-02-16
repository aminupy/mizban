#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-2.0.0}"
ARCH="${2:-amd64}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PAYLOAD_DIR="$ROOT_DIR/dist/linux-$ARCH"
OUTPUT_DIR="$ROOT_DIR/dist/packages"

if ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "dpkg-deb is required to build .deb packages." >&2
  exit 1
fi

if [[ ! -f "$PAYLOAD_DIR/mizban" ]]; then
  echo "Missing payload binary: $PAYLOAD_DIR/mizban" >&2
  echo "Run: make build" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
BUILD_ROOT="$(mktemp -d)"
trap 'rm -rf "$BUILD_ROOT"' EXIT

PKG_ROOT="$BUILD_ROOT/mizban_${VERSION}_${ARCH}"
mkdir -p "$PKG_ROOT/DEBIAN"
mkdir -p "$PKG_ROOT/usr/lib/mizban"
mkdir -p "$PKG_ROOT/usr/bin"
mkdir -p "$PKG_ROOT/usr/share/applications"
mkdir -p "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps"

cp "$PAYLOAD_DIR/mizban" "$PKG_ROOT/usr/lib/mizban/mizban"
cp -R "$PAYLOAD_DIR/web" "$PKG_ROOT/usr/lib/mizban/web"
chmod 0755 "$PKG_ROOT/usr/lib/mizban/mizban"

cat > "$PKG_ROOT/usr/bin/mizban" <<'WRAP'
#!/usr/bin/env sh
exec /usr/lib/mizban/mizban "$@"
WRAP
chmod 0755 "$PKG_ROOT/usr/bin/mizban"

if [[ -f "$PAYLOAD_DIR/web/favicon.png" ]]; then
  cp "$PAYLOAD_DIR/web/favicon.png" "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps/mizban.png"
fi

cat > "$PKG_ROOT/usr/share/applications/mizban.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Mizban
Comment=LAN file sharing
Exec=/usr/bin/mizban
Terminal=false
Icon=mizban
Categories=Network;Utility;
DESKTOP

cat > "$PKG_ROOT/DEBIAN/control" <<EOF_CONTROL
Package: mizban
Version: $VERSION
Section: net
Priority: optional
Architecture: $ARCH
Maintainer: Mizban <noreply@example.com>
Description: Mizban LAN file sharing utility
 A lightweight local-network file sharing tool.
EOF_CONTROL

OUT_FILE="$OUTPUT_DIR/mizban-${VERSION}-linux-${ARCH}.deb"
dpkg-deb --build --root-owner-group "$PKG_ROOT" "$OUT_FILE"

echo "Created DEB: $OUT_FILE"
