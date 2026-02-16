#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-2.0.0}"
ARCH="${2:-amd64}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_DIR="$ROOT_DIR/dist/packages"
PKG_FILE="$OUTPUT_DIR/mizban-${VERSION}-macos-${ARCH}.pkg"

if ! command -v hdiutil >/dev/null 2>&1; then
  echo "hdiutil is required to build macOS .dmg images." >&2
  exit 1
fi

if [[ ! -f "$PKG_FILE" ]]; then
  echo "Missing PKG file: $PKG_FILE" >&2
  echo "Run: ./packaging/macos/build_pkg.sh $VERSION $ARCH" >&2
  exit 1
fi

STAGING_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGING_DIR"' EXIT

cp "$PKG_FILE" "$STAGING_DIR/"
cat > "$STAGING_DIR/README.txt" <<'README'
Install Mizban package, then run:

  mizban
README

OUT_FILE="$OUTPUT_DIR/mizban-${VERSION}-macos-${ARCH}.dmg"
rm -f "$OUT_FILE"

hdiutil create \
  -volname "Mizban" \
  -srcfolder "$STAGING_DIR" \
  -ov \
  -format UDZO \
  "$OUT_FILE"

echo "Created DMG: $OUT_FILE"
