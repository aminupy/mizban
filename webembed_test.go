package mizban

import (
	"io/fs"
	"testing"
)

func TestEmbeddedWebFSContainsIndex(t *testing.T) {
	webFS, err := EmbeddedWebFS()
	if err != nil {
		t.Fatalf("EmbeddedWebFS: %v", err)
	}
	if _, err := fs.Stat(webFS, "index.html"); err != nil {
		t.Fatalf("embedded web index missing: %v", err)
	}
}

