# Go Rewrite Design

## Goals

- Preserve existing Mizban behavior and API contracts used by the current frontend.
- Improve transfer throughput to better use available LAN bandwidth.
- Keep dependency footprint small (Go stdlib + lightweight QR lib only).

## Package Layout

- `cmd/mizban`
  - Single-binary startup, banner/QR output, signal handling.
- `internal/config`
  - Config compatibility (`~/.config/Mizban/config.json`) and defaults.
- `internal/share`
  - Shared directory management and safe path joins.
- `internal/thumb`
  - Thumbnail generation (`200x200`, JPEG output, image-only formats).
- `internal/server`
  - HTTP routes, Range support, legacy upload handling, chunked upload sessions.
- `web`
  - Reused frontend assets with minimal JS changes for parallel transfer support.
- `packaging`
  - MSI/PKG/DMG/DEB build scripts.

## Compatibility Routes

Preserved routes:

- `GET /`
- `GET /files/`
- `POST /upload/`
- `GET|HEAD /download/<filename>`
- `GET /thumbnails/<filename>`

Added throughput routes:

- `GET /settings/`
- `POST /upload/chunked/init`
- `PUT /upload/chunked/chunk`
- `POST /upload/chunked/complete`
- `POST /upload/chunked/abort`

Added local admin routes:

- `GET /settings` (localhost only)
- `GET /info` (localhost only alias)
- `GET /api/admin/settings` (localhost only)
- `PUT /api/admin/settings` (localhost only)
- `GET /api/admin/qr.png` (localhost only)
- `POST /api/admin/restart` (localhost only)

## Download Throughput Design

- Uses `http.ServeContent` for standards-compliant Range handling (`206`, `Content-Range`, `Accept-Ranges`).
- Frontend performs parallel ranged downloads by chunk when supported by browser APIs.
- Fallback to native browser download remains available.

## Upload Throughput Design

- Session-based chunked uploads write directly to pre-sized temp files via offsets.
- Supports concurrent chunk writes with per-chunk state tracking.
- Finalization verifies all chunks, fsyncs, then atomically renames to final destination.

## Safety and Reliability

- Path traversal protections in all file-serving and write paths.
- Upload sessions expire and cleanup stale temp files.
- No full-file buffering in memory.
- Supports large files up to configured max (default 100 GB).
