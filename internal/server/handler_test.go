package server

import (
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/aminupy/mizban/internal/config"
	"github.com/aminupy/mizban/internal/share"
)

func TestDownloadRangeAndHead(t *testing.T) {
	home := t.TempDir()
	settings, err := config.NewForHome(home)
	if err != nil {
		t.Fatalf("settings init: %v", err)
	}

	sharedDir := filepath.Join(home, "Desktop", "MizbanShared")
	settings.SetSharedDir(sharedDir)
	if err := settings.Save(); err != nil {
		t.Fatalf("settings save: %v", err)
	}

	if err := os.MkdirAll(sharedDir, 0o755); err != nil {
		t.Fatalf("mkdir shared: %v", err)
	}
	if err := os.MkdirAll(settings.ThumbnailDir(), 0o755); err != nil {
		t.Fatalf("mkdir thumb: %v", err)
	}

	content := []byte("abcdefghijklmnopqrstuvwxyz")
	if err := os.WriteFile(filepath.Join(sharedDir, "alpha.txt"), content, 0o644); err != nil {
		t.Fatalf("write fixture file: %v", err)
	}

	webDir := filepath.Join(home, "web")
	if err := os.MkdirAll(webDir, 0o755); err != nil {
		t.Fatalf("mkdir web: %v", err)
	}
	if err := os.WriteFile(filepath.Join(webDir, "index.html"), []byte("ok"), 0o644); err != nil {
		t.Fatalf("write web index: %v", err)
	}

	shareMgr := share.New(sharedDir)
	uploads := NewUploadManager(sharedDir, settings.ThumbnailDir(), settings.MaxFileSizeBytes(), settings.ChunkSizeBytes())
	defer uploads.Close()

	h, err := NewHandler(settings, shareMgr, settings.ThumbnailDir(), webDir, uploads, settings.Port(), nil)
	if err != nil {
		t.Fatalf("new handler: %v", err)
	}

	headReq := httptest.NewRequest(http.MethodHead, "/download/alpha.txt", nil)
	headRec := httptest.NewRecorder()
	h.ServeHTTP(headRec, headReq)
	if headRec.Code != http.StatusOK {
		t.Fatalf("HEAD status mismatch: got=%d", headRec.Code)
	}
	if got := headRec.Header().Get("Accept-Ranges"); got != "bytes" {
		t.Fatalf("Accept-Ranges mismatch: got=%q", got)
	}

	rangeReq := httptest.NewRequest(http.MethodGet, "/download/alpha.txt", nil)
	rangeReq.Header.Set("Range", "bytes=0-3")
	rangeRec := httptest.NewRecorder()
	h.ServeHTTP(rangeRec, rangeReq)

	if rangeRec.Code != http.StatusPartialContent {
		t.Fatalf("range status mismatch: got=%d", rangeRec.Code)
	}
	if got := rangeRec.Header().Get("Content-Range"); got != "bytes 0-3/26" {
		t.Fatalf("content-range mismatch: got=%q", got)
	}
	body, _ := io.ReadAll(rangeRec.Result().Body)
	if string(body) != "abcd" {
		t.Fatalf("range body mismatch: got=%q", string(body))
	}
}
