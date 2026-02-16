#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ICON_FILE="$ROOT_DIR/web/favicon.ico"
OUT_DIR="$ROOT_DIR/cmd/mizban"

if [[ ! -f "$ICON_FILE" ]]; then
  echo "Missing icon file: $ICON_FILE" >&2
  exit 1
fi

if ! command -v rsrc >/dev/null 2>&1; then
  echo "Missing rsrc tool. Install with: go install github.com/akavel/rsrc@latest" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

rsrc -arch amd64 -ico "$ICON_FILE" -o "$OUT_DIR/mizban_windows_amd64.syso"
rsrc -arch arm64 -ico "$ICON_FILE" -o "$OUT_DIR/mizban_windows_arm64.syso"

echo "Generated Windows icon resources in $OUT_DIR"
