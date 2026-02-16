#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing command: $1" >&2
    exit 1
  }
}

need_cmd curl
need_cmd jq

printf 'Checking settings endpoint...\n'
curl -fsS "$BASE_URL/settings/" | jq . >/dev/null

if [[ "$BASE_URL" == http://127.0.0.1* || "$BASE_URL" == http://localhost* || "$BASE_URL" == http://[::1]* ]]; then
  printf 'Checking localhost admin endpoint...\n'
  curl -fsS "$BASE_URL/api/admin/settings" | jq . >/dev/null
fi

printf 'Checking files endpoint...\n'
curl -fsS "$BASE_URL/files/" | jq . >/dev/null

printf 'Uploading legacy multipart sample...\n'
LEGACY_FILE="$TMP_DIR/legacy.txt"
printf 'legacy-upload-%s\n' "$(date +%s)" > "$LEGACY_FILE"
LEGACY_NAME="legacy-$(date +%s).txt"
cp "$LEGACY_FILE" "$TMP_DIR/$LEGACY_NAME"

curl -fsS -X POST "$BASE_URL/upload/" -F "file=@$TMP_DIR/$LEGACY_NAME" | jq . >/dev/null

printf 'Verifying HEAD and range download...\n'
curl -fsSI "$BASE_URL/download/$LEGACY_NAME" | grep -i 'Accept-Ranges: bytes' >/dev/null
RANGE_OUTPUT="$TMP_DIR/range.out"
curl -fsS -H 'Range: bytes=0-5' "$BASE_URL/download/$LEGACY_NAME" > "$RANGE_OUTPUT"

printf 'Running chunked upload flow...\n'
CHUNK_FILE="$TMP_DIR/chunked.bin"
head -c 65536 /dev/urandom > "$CHUNK_FILE"
CHUNK_NAME="chunked-$(date +%s).bin"

INIT_JSON="$TMP_DIR/init.json"
curl -fsS -X POST "$BASE_URL/upload/chunked/init" \
  -H 'Content-Type: application/json' \
  -d "{\"filename\":\"$CHUNK_NAME\",\"size\":65536,\"chunk_size\":16384}" > "$INIT_JSON"

UPLOAD_ID="$(jq -r '.upload_id' "$INIT_JSON")"
if [[ -z "$UPLOAD_ID" || "$UPLOAD_ID" == "null" ]]; then
  echo "chunk init did not return upload_id" >&2
  exit 1
fi

for idx in 0 1 2 3; do
  start=$((idx * 16384))
  dd if="$CHUNK_FILE" of="$TMP_DIR/chunk-$idx.bin" bs=1 skip="$start" count=16384 status=none
  curl -fsS -X PUT "$BASE_URL/upload/chunked/chunk" \
    -H "X-Upload-ID: $UPLOAD_ID" \
    -H "X-Chunk-Index: $idx" \
    -H "X-Chunk-Offset: $start" \
    --data-binary "@$TMP_DIR/chunk-$idx.bin" > /dev/null

done

curl -fsS -X POST "$BASE_URL/upload/chunked/complete" \
  -H 'Content-Type: application/json' \
  -d "{\"upload_id\":\"$UPLOAD_ID\"}" | jq . >/dev/null

printf 'Integration smoke checks passed.\n'
