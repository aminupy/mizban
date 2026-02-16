# Release Checklist

This checklist prepares a clean Go-only Mizban release.

## 1) Pre-flight

- Verify working tree:
  - `git status`
- Verify Go tests:
  - `go test ./...`
- Verify integration smoke test against local server:
  - `./scripts/integration_smoke.sh http://127.0.0.1:8000`

## 2) Build portable artifacts

- Set version and build archives/checksums:
  - `make VERSION=<x.y.z> release`

Outputs:

- `dist/packages/mizban-<version>-linux-amd64.tar.gz`
- `dist/packages/mizban-<version>-linux-arm64.tar.gz`
- `dist/packages/mizban-<version>-macos-amd64.tar.gz`
- `dist/packages/mizban-<version>-macos-arm64.tar.gz`
- `dist/packages/mizban-<version>-windows-amd64.tar.gz`
- `dist/packages/mizban-<version>-windows-arm64.tar.gz`
- `dist/packages/SHA256SUMS.txt`

## 3) Build native installers

Run on environments with required tools installed.

- Windows (WiX v4):
  - `make VERSION=<x.y.z> package-windows`
- macOS (`pkgbuild`, `hdiutil`):
  - `make VERSION=<x.y.z> package-macos`
- Linux (`dpkg-deb`):
  - `make VERSION=<x.y.z> package-linux`

## 4) Manual validation

- Launch binary and confirm startup output:
  - client URL
  - localhost admin URL
  - scannable terminal QR code
- Confirm LAN client flow:
  - browse files
  - upload/download large file (>= 2 GB)
- Confirm admin flow (`127.0.0.1` only):
  - view/update settings
  - QR image endpoint
  - restart endpoint

## 5) Publish

- Create git tag: `v<x.y.z>`.
- Create GitHub release.
- Upload all archives, installers, and `SHA256SUMS.txt`.
- Verify `install.sh` can install from latest release on Linux.

## 6) Test Workflow Without Publishing

Use the GitHub Actions manual trigger:

- Open `Actions` -> `Release` workflow -> `Run workflow`.
- Set `version` to a test value (example: `2.1.0-rc1`).
- Run it on your branch.

What this does:

- Builds Linux + Windows binaries.
- Builds Linux `.deb`.
- Builds macOS `.pkg` + `.dmg`.
- Generates `SHA256SUMS.txt`.
- Uploads a workflow artifact named `release-assets-<version>`.

What it does not do in manual mode:

- It does **not** create a GitHub Release.
