#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-2.0.0}"
ARCH="${2:-amd64}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PAYLOAD_DIR="$ROOT_DIR/dist/windows-$ARCH"
OUTPUT_DIR="$ROOT_DIR/dist/packages"
WXS_FILE="$ROOT_DIR/packaging/windows/mizban.wxs"
ICON_FILE="$ROOT_DIR/web/favicon.ico"

if ! command -v wix >/dev/null 2>&1; then
  echo "WiX v4 CLI is required (https://wixtoolset.org)." >&2
  exit 1
fi

if [[ ! -f "$PAYLOAD_DIR/mizban.exe" ]]; then
  echo "Missing payload binary: $PAYLOAD_DIR/mizban.exe" >&2
  echo "Run: make build" >&2
  exit 1
fi

if [[ ! -f "$ICON_FILE" ]]; then
  echo "Missing installer icon: $ICON_FILE" >&2
  exit 1
fi

case "$ARCH" in
  amd64) WIX_ARCH="x64" ;;
  arm64) WIX_ARCH="arm64" ;;
  *)
    echo "Unsupported Windows architecture: $ARCH" >&2
    exit 1
    ;;
esac

mkdir -p "$OUTPUT_DIR"
OUT_FILE="$OUTPUT_DIR/mizban-${VERSION}-windows-${ARCH}.msi"

wix build \
  -arch "$WIX_ARCH" \
  -dVersion="$VERSION" \
  -dPayloadDir="$PAYLOAD_DIR" \
  -dIconFile="$ICON_FILE" \
  "$WXS_FILE" \
  -o "$OUT_FILE"

echo "Created MSI: $OUT_FILE"
