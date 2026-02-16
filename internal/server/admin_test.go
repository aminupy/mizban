package server

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sync/atomic"
	"testing"

	"github.com/aminupy/mizban/internal/config"
	"github.com/aminupy/mizban/internal/share"
)

func newTestHandler(t *testing.T) (*Handler, *config.Settings) {
	t.Helper()

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
		t.Fatalf("mkdir shared dir: %v", err)
	}
	if err := os.MkdirAll(settings.ThumbnailDir(), 0o755); err != nil {
		t.Fatalf("mkdir thumbnail dir: %v", err)
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
	t.Cleanup(func() { uploads.Close() })

	h, err := NewHandler(settings, shareMgr, settings.ThumbnailDir(), webDir, uploads, settings.Port(), nil)
	if err != nil {
		t.Fatalf("new handler: %v", err)
	}

	return h, settings
}

func TestAdminPageIsLoopbackOnly(t *testing.T) {
	h, _ := newTestHandler(t)

	remoteReq := httptest.NewRequest(http.MethodGet, "/settings", nil)
	remoteReq.RemoteAddr = "192.168.1.25:4040"
	remoteRec := httptest.NewRecorder()
	h.ServeHTTP(remoteRec, remoteReq)
	if remoteRec.Code != http.StatusForbidden {
		t.Fatalf("expected forbidden for remote host, got %d", remoteRec.Code)
	}

	loopReq := httptest.NewRequest(http.MethodGet, "/settings", nil)
	loopReq.RemoteAddr = "127.0.0.1:5050"
	loopRec := httptest.NewRecorder()
	h.ServeHTTP(loopRec, loopReq)
	if loopRec.Code != http.StatusOK {
		t.Fatalf("expected 200 for loopback, got %d", loopRec.Code)
	}
}

func TestAdminSettingsUpdate(t *testing.T) {
	h, settings := newTestHandler(t)

	newShare := filepath.Join(t.TempDir(), "CustomShare")
	payload := map[string]any{
		"mizban_shared_dir":   newShare,
		"parallel_chunks":     12,
		"chunk_size_bytes":    int64(2 * 1024 * 1024),
		"max_file_size_bytes": int64(50) * 1024 * 1024 * 1024,
		"port":                8123,
	}
	body, _ := json.Marshal(payload)

	req := httptest.NewRequest(http.MethodPut, "/api/admin/settings", bytes.NewReader(body))
	req.RemoteAddr = "127.0.0.1:6000"
	rec := httptest.NewRecorder()

	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("unexpected status: %d body=%s", rec.Code, rec.Body.String())
	}

	if got := settings.SharedDir(); got != filepath.Clean(newShare) {
		t.Fatalf("shared dir mismatch: got=%q", got)
	}
	if got := settings.ParallelChunks(); got != 12 {
		t.Fatalf("parallel chunks mismatch: got=%d", got)
	}
	if got := settings.Port(); got != 8123 {
		t.Fatalf("port mismatch: got=%d", got)
	}

	var response map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &response); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if restartRequired, _ := response["restart_required"].(bool); !restartRequired {
		t.Fatalf("expected restart_required=true")
	}
}

func TestAdminRestartEndpoint(t *testing.T) {
	home := t.TempDir()
	settings, err := config.NewForHome(home)
	if err != nil {
		t.Fatalf("settings init: %v", err)
	}

	sharedDir := filepath.Join(home, "Desktop", "MizbanShared")
	if err := os.MkdirAll(sharedDir, 0o755); err != nil {
		t.Fatalf("mkdir shared dir: %v", err)
	}
	if err := os.MkdirAll(settings.ThumbnailDir(), 0o755); err != nil {
		t.Fatalf("mkdir thumbnail dir: %v", err)
	}
	webDir := filepath.Join(home, "web")
	if err := os.MkdirAll(webDir, 0o755); err != nil {
		t.Fatalf("mkdir web dir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(webDir, "index.html"), []byte("ok"), 0o644); err != nil {
		t.Fatalf("write web index: %v", err)
	}

	shareMgr := share.New(sharedDir)
	uploads := NewUploadManager(sharedDir, settings.ThumbnailDir(), settings.MaxFileSizeBytes(), settings.ChunkSizeBytes())
	defer uploads.Close()

	var called atomic.Int32
	h, err := NewHandler(
		settings,
		shareMgr,
		settings.ThumbnailDir(),
		webDir,
		uploads,
		settings.Port(),
		func() bool {
			return called.CompareAndSwap(0, 1)
		},
	)
	if err != nil {
		t.Fatalf("new handler: %v", err)
	}

	req := httptest.NewRequest(http.MethodPost, "/api/admin/restart", nil)
	req.RemoteAddr = "127.0.0.1:7777"
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusAccepted {
		t.Fatalf("expected 202, got %d body=%s", rec.Code, rec.Body.String())
	}
	if called.Load() != 1 {
		t.Fatalf("restart callback was not called")
	}

	remoteReq := httptest.NewRequest(http.MethodPost, "/api/admin/restart", nil)
	remoteReq.RemoteAddr = "192.168.1.50:7777"
	remoteRec := httptest.NewRecorder()
	h.ServeHTTP(remoteRec, remoteReq)
	if remoteRec.Code != http.StatusForbidden {
		t.Fatalf("expected forbidden for remote restart call, got %d", remoteRec.Code)
	}
}
