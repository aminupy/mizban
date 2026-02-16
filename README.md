# Mizban (Go Rewrite)

Mizban is a LAN file sharing utility. The Go rewrite preserves the existing UX/API contracts while adding high-throughput parallel transfers and a localhost-only admin page.

## Runtime Model

- Single binary: `mizban`
- One HTTP server on LAN (`0.0.0.0:<port>`)
- Client UI at `/` (LAN)
- Admin UI at `/settings` and `/info` (localhost only)
- Startup prints client URL and terminal QR code

## Preserved Compatibility

- Shared folder default: `~/Desktop/MizbanShared`
- Config path: `~/.config/Mizban/config.json`
- Thumbnail cache: `~/.cache/Mizban/.thumbnails`
- Existing client routes:
  - `GET /files/`
  - `POST /upload/` (legacy multipart)
  - `GET|HEAD /download/<filename>`
  - `GET /thumbnails/<filename>`

## Throughput Features

- HTTP Range downloads (`Accept-Ranges`, `206`, `Content-Range`)
- Parallel range downloads in frontend (default `8`)
- Parallel chunked uploads:
  - `POST /upload/chunked/init`
  - `PUT /upload/chunked/chunk`
  - `POST /upload/chunked/complete`
  - `POST /upload/chunked/abort`
- Streaming and bounded buffering only (no full-file RAM buffering)
- Atomic upload finalize (temp file + rename)

## Admin APIs (localhost only)

- `GET /api/admin/settings`
- `PUT /api/admin/settings`
- `GET /api/admin/qr.png`
- `POST /api/admin/restart`

`PUT /api/admin/settings` fields:

- `mizban_shared_dir` (string)
- `port` (1-65535; restart required)
- `parallel_chunks` (1-64)
- `chunk_size_bytes` (262144-67108864)
- `max_file_size_bytes` (1-107374182400)

Client transfer settings route stays at:

- `GET /settings/`

## Configuration

Config file: `~/.config/Mizban/config.json`

Compatible keys:

```json
{
  "mizban_shared_dir": "/home/user/Desktop/MizbanShared",
  "port": 8000
}
```

Optional performance keys:

- `parallel_chunks` (default `8`)
- `chunk_size_bytes` (default `4194304`)
- `max_file_size_bytes` (default `107374182400`)

## Run

```bash
go run ./cmd/mizban
```

Optional explicit web assets path:

```bash
go run ./cmd/mizban --web-dir ./web
```

## Build

Cross-platform binaries (`linux/darwin/windows`, `amd64/arm64`):

```bash
make build
```

Local build:

```bash
make build-local
```

Binary-size flags enabled by default:

- `-trimpath`
- `-buildvcs=false`
- `-ldflags "-s -w"`

Optional UPX compression:

```bash
make upx
```

## Release Artifacts

Create portable archives for all platforms and generate checksums:

```bash
make release
```

This produces:

- `dist/packages/mizban-<version>-linux-<arch>.tar.gz`
- `dist/packages/mizban-<version>-macos-<arch>.tar.gz`
- `dist/packages/mizban-<version>-windows-<arch>.tar.gz`
- `dist/packages/SHA256SUMS.txt`

Installers (run on platform with required toolchain):

```bash
make package
```

Platform scripts:

- `packaging/windows/build_msi.sh` (WiX)
- `packaging/macos/build_pkg.sh` + `packaging/macos/build_dmg.sh`
- `packaging/linux/build_deb.sh`

Detailed release checklist: `docs/RELEASE.md`

## Linux One-Command Install (from GitHub release)

```bash
./install.sh
```

Installs into user scope:

- binary wrapper: `~/.local/bin/mizban`
- runtime payload: `~/.local/lib/mizban`

## Tests

Unit tests:

```bash
go test ./...
```

Integration smoke test against a running server:

```bash
./scripts/integration_smoke.sh http://127.0.0.1:8000
```

Throughput plan: `docs/THROUGHPUT_TEST_PLAN.md`

## Repository Layout

- `cmd/mizban` - entrypoint
- `internal/config` - config compatibility and defaults
- `internal/server` - HTTP routes, admin APIs, transfer logic
- `internal/share` - shared directory lifecycle
- `internal/thumb` - thumbnail generation
- `web` - frontend assets served by the binary
- `packaging` - MSI/PKG/DMG/DEB scripts

## Troubleshooting

- `web assets not found`
  - Run from repo root or pass `--web-dir`.
- Port conflicts
  - Mizban auto-increments from configured port and persists the new value.
- Port changed in admin UI but server still on old port
  - Use `Restart Now` in `/settings` (or `POST /api/admin/restart`).
- `Restart Now` while using `go run`
  - Use built binary (`dist/.../mizban`) for most reliable restart behavior.
- Shared folder update fails
  - Use an absolute path that exists or can be created on the server machine.
- Slow transfers
  - Compare to `iperf3` baseline and tune `parallel_chunks`.
