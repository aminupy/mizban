# Mizban Migration Notes (Python -> Go)

This document captures the current Python implementation contracts that the Go rewrite must preserve unless explicitly called out for performance improvements.

## Runtime behavior

- Startup creates required directories:
  - Shared folder: `~/Desktop/MizbanShared` (configurable)
  - Thumbnail cache: `~/.cache/Mizban/.thumbnails`
- HTTP server binds to `0.0.0.0:<port>` where default port is `8000`.
- If configured port is unavailable, it auto-increments until free and persists the new port back to config.
- CLI prints:
  - Shared folder path
  - URL (`http://<lan-ip>:<port>/`)
  - ASCII QR code for the URL
- GUI mode:
  - Starts same HTTP server
  - Shows URL + QR + shared folder
  - Can change shared folder and persists to config
  - Uses single-instance lock on `127.0.0.1:60123`
  - Falls back to CLI when GUI environment is unavailable

## Config contract

File paths:

- Config dir: `~/.config/Mizban`
- Config file: `~/.config/Mizban/config.json`
- Cache dir: `~/.cache/Mizban`

Current JSON keys/defaults:

```json
{
  "mizban_shared_dir": "~/Desktop/MizbanShared",
  "port": 8000
}
```

Compatibility requirements for Go:

- Read existing JSON shape unchanged.
- Preserve existing key names.
- Keep same default values.
- Keep saving back to same file path.

## HTTP/API routes used by frontend

- `GET /` and static asset paths from frontend directory.
- `GET /files/`
  - Response: `{ "files": ["file1", "file2", ...] }`
  - Only top-level files from shared directory.
- `GET /download/<filename>`
  - Returns file bytes.
- `HEAD /download/<filename>`
  - Used by frontend to verify file existence before download.
- `POST /upload/`
  - `multipart/form-data`, field name: `file`
  - Response on success: HTTP `201` with `{ "filename": "...", "message": "Uploaded" }`
- `GET /thumbnails/<filename>`
  - Serves thumbnail file from `~/.cache/Mizban/.thumbnails/<filename>.jpg`

## Upload and thumbnail behavior

- Single-file upload endpoint writes streamed bytes to disk (no full-file buffering).
- Python version had upload limit around 4 GiB; Go rewrite will raise to 100 GiB per new requirement.
- Thumbnail generation happens after successful upload.
- Thumbnail output format:
  - Destination path: `<thumb_dir>/<original_filename>.jpg`
  - Size target: max `200x200`
  - JPEG output
  - Supported source formats in current behavior: JPG/JPEG/PNG/GIF

## Frontend behavior expectations

- Drag/drop and file input uploads.
- File cards with icons/thumbnails.
- Progress indicator per upload.
- Click file card triggers download.
- Existing JS currently uses:
  - `POST /upload/`
  - `GET /files/`
  - `GET|HEAD /download/<file>`
  - `GET /thumbnails/<file>`

## Planned compatibility additions for throughput

To reach LAN throughput close to iperf capacity, Go rewrite adds while preserving existing routes:

- Correct HTTP Range handling for `GET /download/<filename>`.
- New chunked upload session endpoints for parallel upload streams.
- Frontend upgrade to use default 8 parallel streams/chunks with fallback to legacy behavior.

## Runtime simplification in Go rewrite

- The Go binary now runs in a single mode (no separate GUI executable mode).
- Client UI remains at `/` for all LAN users.
- Local administration UI is provided at `/settings` (alias `/info`) and is loopback-only.
- Local-only admin APIs allow updating config values and restarting to apply port changes without exposing controls to the LAN.
