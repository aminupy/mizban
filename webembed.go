package mizban

import (
	"embed"
	"io/fs"
)

// embeddedWeb contains a runtime fallback copy of the web frontend.
//
//go:embed all:web
var embeddedWeb embed.FS

// EmbeddedWebFS returns the frontend root (equivalent to ./web).
func EmbeddedWebFS() (fs.FS, error) {
	return fs.Sub(embeddedWeb, "web")
}

