#!/usr/bin/env sh
set -eu

REPO="${REPO:-aminupy/mizban}"
API_URL="https://api.github.com/repos/$REPO/releases/latest"
BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"
LIB_DIR="${LIB_DIR:-$HOME/.local/lib/mizban}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Error: required command not found: $1" >&2
    exit 1
  }
}

for cmd in curl tar uname mktemp grep sed head find; do
  need_cmd "$cmd"
done

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64) ARCH="amd64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *)
    echo "Error: unsupported architecture: $ARCH" >&2
    exit 1
    ;;
esac

printf 'Fetching latest release metadata for %s...\n' "$REPO"
RELEASE_JSON="$(curl -fsSL "$API_URL")"

TAG_NAME="$(printf '%s\n' "$RELEASE_JSON" | sed -n 's/.*"tag_name":[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)"
DOWNLOAD_URL="$(
  printf '%s\n' "$RELEASE_JSON" \
    | sed -n 's/.*"browser_download_url":[[:space:]]*"\([^"]*\)".*/\1/p' \
    | grep "mizban-.*-linux-$ARCH\\.tar\\.gz" \
    | head -n1
)"

if [ -z "$DOWNLOAD_URL" ]; then
  echo "Error: could not find Linux $ARCH archive in latest release assets." >&2
  echo "Expected asset pattern: mizban-<version>-linux-$ARCH.tar.gz" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT INT TERM

ARCHIVE="$TMP_DIR/mizban.tar.gz"
EXTRACT_DIR="$TMP_DIR/extract"
mkdir -p "$EXTRACT_DIR"

printf 'Downloading %s...\n' "$DOWNLOAD_URL"
curl -fL "$DOWNLOAD_URL" -o "$ARCHIVE"
tar -xzf "$ARCHIVE" -C "$EXTRACT_DIR"

PAYLOAD_DIR="$(find "$EXTRACT_DIR" -mindepth 1 -maxdepth 1 -type d | head -n1)"
if [ -z "$PAYLOAD_DIR" ] || [ ! -f "$PAYLOAD_DIR/mizban" ] || [ ! -d "$PAYLOAD_DIR/web" ]; then
  echo "Error: archive layout is invalid; expected binary + web directory." >&2
  exit 1
fi

mkdir -p "$BIN_DIR" "$LIB_DIR"
rm -rf "$LIB_DIR"/*
cp "$PAYLOAD_DIR/mizban" "$LIB_DIR/mizban"
cp -R "$PAYLOAD_DIR/web" "$LIB_DIR/web"
chmod 0755 "$LIB_DIR/mizban"

cat > "$BIN_DIR/mizban" <<WRAP
#!/usr/bin/env sh
exec "$LIB_DIR/mizban" --web-dir "$LIB_DIR/web" "\$@"
WRAP
chmod 0755 "$BIN_DIR/mizban"

echo ""
echo "Installed Mizban ${TAG_NAME:-latest}"
echo "  Binary wrapper: $BIN_DIR/mizban"
echo "  Runtime files : $LIB_DIR"

echo ""
if command -v mizban >/dev/null 2>&1; then
  echo "Run: mizban"
else
  echo "Run: $BIN_DIR/mizban"
  echo "Note: add $BIN_DIR to PATH if needed."
fi
