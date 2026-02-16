#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-2.0.0}"
ARCH="${2:-amd64}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PAYLOAD_DIR="$ROOT_DIR/dist/windows-$ARCH"
OUTPUT_DIR="$ROOT_DIR/dist/packages"
WXS_TEMPLATE="$ROOT_DIR/packaging/windows/mizban.wxs"
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

if [[ ! -f "$WXS_TEMPLATE" ]]; then
  echo "Missing installer template: $WXS_TEMPLATE" >&2
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
BUILD_ROOT="$(mktemp -d)"
trap 'rm -rf "$BUILD_ROOT"' EXIT
PAYLOAD_XML="$BUILD_ROOT/payload-files.xml"
WXS_FILE="$BUILD_ROOT/mizban.generated.wxs"

escape_xml() {
  local input="$1"
  input="${input//&/&amp;}"
  input="${input//</&lt;}"
  input="${input//>/&gt;}"
  input="${input//\"/&quot;}"
  printf '%s' "$input"
}

component_idx=0
while IFS= read -r -d '' file; do
  component_idx=$((component_idx + 1))
  rel="${file#$PAYLOAD_DIR/}"
  rel_win="${rel//\//\\}"
  dir="$(dirname "$rel")"
  dir_win="${dir//\//\\}"

  source_attr="$(escape_xml "!(bindpath.payload)\\$rel_win")"
  component_id="$(printf 'MizbanFile%06d' "$component_idx")"
  if [[ "$dir" == "." ]]; then
    printf '      <Component Id="%s">\n' "$component_id" >> "$PAYLOAD_XML"
    printf '        <File Source="%s" />\n' "$source_attr" >> "$PAYLOAD_XML"
  else
    subdir_attr="$(escape_xml "$dir_win")"
    printf '      <Component Id="%s" Subdirectory="%s">\n' "$component_id" "$subdir_attr" >> "$PAYLOAD_XML"
    printf '        <File Source="%s" />\n' "$source_attr" >> "$PAYLOAD_XML"
  fi
  printf '      </Component>\n' >> "$PAYLOAD_XML"
done < <(find "$PAYLOAD_DIR" -type f -print0 | sort -z)

if [[ ! -s "$PAYLOAD_XML" ]]; then
  echo "No payload files found in: $PAYLOAD_DIR" >&2
  exit 1
fi

awk -v payload="$PAYLOAD_XML" '
  $0 ~ /__PAYLOAD_FILES__/ {
    while ((getline line < payload) > 0) {
      print line
    }
    close(payload)
    next
  }
  { print }
' "$WXS_TEMPLATE" > "$WXS_FILE"

wix build \
  -arch "$WIX_ARCH" \
  -d "Version=$VERSION" \
  -b "payload=$PAYLOAD_DIR" \
  -d "IconFile=$ICON_FILE" \
  "$WXS_FILE" \
  -o "$OUT_FILE"

echo "Created MSI: $OUT_FILE"
