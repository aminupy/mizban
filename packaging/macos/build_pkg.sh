#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-2.0.0}"
ARCH="${2:-amd64}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PAYLOAD_DIR="$ROOT_DIR/dist/darwin-$ARCH"
OUTPUT_DIR="$ROOT_DIR/dist/packages"

if ! command -v pkgbuild >/dev/null 2>&1; then
  echo "pkgbuild is required to build macOS .pkg packages." >&2
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

PKG_ROOT="$BUILD_ROOT/root"
mkdir -p "$PKG_ROOT/usr/local/lib/mizban"
mkdir -p "$PKG_ROOT/usr/local/bin"

cp "$PAYLOAD_DIR/mizban" "$PKG_ROOT/usr/local/lib/mizban/mizban"
cp -R "$PAYLOAD_DIR/web" "$PKG_ROOT/usr/local/lib/mizban/web"
chmod 0755 "$PKG_ROOT/usr/local/lib/mizban/mizban"

cat > "$PKG_ROOT/usr/local/bin/mizban" <<'WRAP'
#!/usr/bin/env sh
exec /usr/local/lib/mizban/mizban "$@"
WRAP
chmod 0755 "$PKG_ROOT/usr/local/bin/mizban"

OUT_FILE="$OUTPUT_DIR/mizban-${VERSION}-macos-${ARCH}.pkg"
pkgbuild \
  --identifier "com.mizban.app" \
  --version "$VERSION" \
  --root "$PKG_ROOT" \
  "$OUT_FILE"

echo "Created PKG: $OUT_FILE"
