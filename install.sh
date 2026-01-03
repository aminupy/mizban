#!/bin/sh
set -eu

REPO="aminupy/mizban"
ASSET_NAME="mizban-cli-linux-x86_64"

# PNG icon (recommended for Linux launchers)
ICON_URL="https://raw.githubusercontent.com/aminupy/mizban/main/clients/frontend/favicon.png"

# Per-user install locations (no sudo)
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
HICOLOR_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"

BIN_PATH="$BIN_DIR/mizban-cli"
ICON_PATH="$HICOLOR_DIR/mizban-cli.png"
DESKTOP_PATH="$APP_DIR/mizban-cli.desktop"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Error: required command not found: $1" >&2
    exit 1
  }
}

need_cmd curl
need_cmd python3
need_cmd uname
need_cmd mktemp

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64) : ;;
  *)
    echo "Error: This installer currently supports x86_64 only. Detected: $ARCH" >&2
    exit 1
    ;;
esac

mkdir -p "$BIN_DIR" "$APP_DIR" "$HICOLOR_DIR"

TMP_JSON="$(mktemp)"
TMP_HEADERS="$(mktemp)"
cleanup() { rm -f "$TMP_JSON" "$TMP_HEADERS"; }
trap cleanup EXIT INT TERM

fetch_latest_asset_url_via_api() {
  API_URL="https://api.github.com/repos/$REPO/releases/latest"

  # -f: fail on non-2xx, -sS: silent but show errors, -L: follow redirects
  curl -fsSL -D "$TMP_HEADERS" "$API_URL" -o "$TMP_JSON" || return 1

  # sanity check: should be JSON object
  firstchar="$(dd if="$TMP_JSON" bs=1 count=1 2>/dev/null || true)"
  [ "$firstchar" = "{" ] || return 1

  python3 - "$ASSET_NAME" <"$TMP_JSON" <<'PY'
import json, sys
asset_name = sys.argv[1]
j = json.load(sys.stdin)
tag = j.get("tag_name") or ""
url = ""
for a in (j.get("assets") or []):
    if a.get("name") == asset_name:
        url = a.get("browser_download_url") or ""
        break
if url:
    print(url + "|" + tag)
PY
}

fetch_latest_tag_via_redirect() {
  # GitHub redirects /releases/latest -> /releases/tag/<tag>
  LATEST_URL="https://github.com/$REPO/releases/latest"
  loc="$(curl -sI "$LATEST_URL" | tr -d '\r' | awk -F': ' 'tolower($1)=="location"{print $2}' | tail -n 1)"
  tag="$(printf "%s" "$loc" | awk -F'/tag/' 'NF>1{print $2}')"
  [ -n "$tag" ] && printf "%s" "$tag"
}

echo "Fetching latest release info for $REPO ..."

DOWNLOAD_URL=""
TAG_NAME=""

api_out="$(fetch_latest_asset_url_via_api 2>/dev/null || true)"
if [ -n "$api_out" ]; then
  DOWNLOAD_URL="$(printf "%s" "$api_out" | awk -F'|' '{print $1}')"
  TAG_NAME="$(printf "%s" "$api_out" | awk -F'|' '{print $2}')"
else
  TAG_NAME="$(fetch_latest_tag_via_redirect 2>/dev/null || true)"
  if [ -n "$TAG_NAME" ]; then
    DOWNLOAD_URL="https://github.com/$REPO/releases/download/$TAG_NAME/$ASSET_NAME"
  fi
fi

if [ -z "$DOWNLOAD_URL" ]; then
  echo "Error: Could not determine latest release download URL." >&2
  echo "Check: https://github.com/$REPO/releases/latest" >&2
  exit 1
fi

echo "Latest release: ${TAG_NAME:-unknown}"
echo "Downloading CLI binary..."
curl -fL "$DOWNLOAD_URL" -o "$BIN_PATH"
chmod +x "$BIN_PATH"

echo "Downloading icon (PNG)..."
curl -fL "$ICON_URL" -o "$ICON_PATH"

echo "Creating desktop entry..."
cat > "$DESKTOP_PATH" <<EOF
[Desktop Entry]
Type=Application
Name=Mizban CLI
Comment=Share files on your LAN (CLI)
Exec=$BIN_PATH
Terminal=true
Icon=mizban-cli
Categories=Utility;Network;
EOF

chmod 644 "$DESKTOP_PATH"

# Refresh desktop + icon caches (optional, but helps rofi/menus pick up changes)
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo ""
echo "✅ Installed Mizban CLI"
echo "  Binary:  $BIN_PATH"
echo "  Desktop: $DESKTOP_PATH"
echo "  Icon:    $ICON_PATH"
echo ""
echo "Run now:"
echo "  $BIN_PATH"
echo ""
echo "Or launch from your application menu: Mizban CLI"
