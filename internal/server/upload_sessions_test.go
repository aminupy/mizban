package server

import (
	"bytes"
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestChunkAssemblyOutOfOrderFinalize(t *testing.T) {
	root := t.TempDir()
	thumbDir := filepath.Join(root, ".thumb")
	if err := os.MkdirAll(thumbDir, 0o755); err != nil {
		t.Fatalf("mkdir thumb dir: %v", err)
	}

	mgr := NewUploadManager(root, thumbDir, 100*1024*1024, 4)
	defer mgr.Close()

	content := []byte("hello-parallel-upload")
	initData, err := mgr.Init("sample.bin", int64(len(content)), 4)
	if err != nil {
		t.Fatalf("init upload: %v", err)
	}

	order := []int{2, 0, 4, 1, 3}
	for _, idx := range order {
		start := int64(idx) * initData.ChunkSize
		if start >= int64(len(content)) {
			continue
		}
		end := start + initData.ChunkSize
		if end > int64(len(content)) {
			end = int64(len(content))
		}
		chunk := content[start:end]
		err := mgr.WriteChunk(initData.UploadID, idx, start, int64(len(chunk)), bytes.NewReader(chunk))
		if err != nil {
			t.Fatalf("write chunk %d: %v", idx, err)
		}
	}

	filename, err := mgr.Complete(initData.UploadID)
	if err != nil {
		t.Fatalf("complete upload: %v", err)
	}
	if filename != "sample.bin" {
		t.Fatalf("filename mismatch: got=%q", filename)
	}

	stored, err := os.ReadFile(filepath.Join(root, "sample.bin"))
	if err != nil {
		t.Fatalf("read stored file: %v", err)
	}
	if !bytes.Equal(stored, content) {
		t.Fatalf("stored content mismatch: got=%q want=%q", string(stored), string(content))
	}
}

func TestCompleteFailsWhenChunksMissing(t *testing.T) {
	root := t.TempDir()
	mgr := NewUploadManager(root, filepath.Join(root, ".thumb"), 100*1024*1024, 4)
	defer mgr.Close()

	initData, err := mgr.Init("incomplete.bin", 12, 4)
	if err != nil {
		t.Fatalf("init upload: %v", err)
	}

	chunk := []byte("1234")
	if err := mgr.WriteChunk(initData.UploadID, 0, 0, 4, bytes.NewReader(chunk)); err != nil {
		t.Fatalf("write first chunk: %v", err)
	}

	_, err = mgr.Complete(initData.UploadID)
	if err == nil {
		t.Fatal("expected incomplete upload error")
	}

	var incompleteErr *IncompleteUploadError
	if !errors.As(err, &incompleteErr) {
		t.Fatalf("expected IncompleteUploadError, got %T", err)
	}
	if incompleteErr.MissingChunks != 2 {
		t.Fatalf("missing chunk count mismatch: got=%d", incompleteErr.MissingChunks)
	}
}
