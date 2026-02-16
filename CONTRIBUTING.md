# Contributing to Mizban

Thanks for contributing.

## Development setup

1. Fork and clone the repository.
2. Install Go (`1.22+`) and required platform tooling.
3. Run tests:
   - `go test ./...`
4. Build:
   - `make build`

## Branch and pull request workflow

1. Create a branch from `main`.
2. Keep changes focused and scoped.
3. Add or update tests when behavior changes.
4. Open a pull request with:
   - problem statement
   - summary of changes
   - testing notes

## Code expectations

- Preserve existing API and UX behavior unless change is intentional and documented.
- Keep dependencies minimal (prefer Go stdlib where practical).
- Ensure cross-platform behavior (Windows/macOS/Linux).
- For performance-sensitive paths, avoid unnecessary allocations and full-file buffering.

## Reporting bugs and proposing features

- Use GitHub Issues.
- Include environment details, steps to reproduce, expected vs actual behavior, and logs/screenshots if available.

## Security

Please do not report security issues in public issues. See `SECURITY.md`.
