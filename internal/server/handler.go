package server

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/aminupy/mizban/internal/config"
	"github.com/aminupy/mizban/internal/share"
	"github.com/aminupy/mizban/internal/thumb"
	qrcode "github.com/skip2/go-qrcode"
)

const extraMultipartOverhead = int64(10 * 1024 * 1024)

type Handler struct {
	settings *config.Settings
	share    *share.Manager
	thumbDir string
	web      http.Handler
	uploads  *UploadManager
	restart  func() bool
	activePort int
}

func NewHandler(
	settings *config.Settings,
	shared *share.Manager,
	thumbDir, webDir string,
	uploads *UploadManager,
	activePort int,
	restart func() bool,
) (*Handler, error) {
	if settings == nil {
		return nil, errors.New("settings is required")
	}
	if shared == nil {
		return nil, errors.New("share manager is required")
	}
	if uploads == nil {
		return nil, errors.New("upload manager is required")
	}
	if webDir == "" {
		return nil, errors.New("web directory is required")
	}

	if activePort <= 0 || activePort > 65535 {
		activePort = settings.Port()
	}

	return &Handler{
		settings:   settings,
		share:      shared,
		thumbDir:   filepath.Clean(thumbDir),
		web:        http.FileServer(http.Dir(webDir)),
		uploads:    uploads,
		restart:    restart,
		activePort: activePort,
	}, nil
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	switch {
	case r.URL.Path == "/files/" && r.Method == http.MethodGet:
		h.handleFiles(w, r)
	case r.URL.Path == "/settings/" && r.Method == http.MethodGet:
		h.handleTransferSettings(w)
	case (r.URL.Path == "/settings" || r.URL.Path == "/info" || r.URL.Path == "/info/") && r.Method == http.MethodGet:
		if !requireLoopback(w, r) {
			return
		}
		h.handleAdminPage(w, r)
	case r.URL.Path == "/api/admin/settings" && (r.Method == http.MethodGet || r.Method == http.MethodPut):
		if !requireLoopback(w, r) {
			return
		}
		if r.Method == http.MethodGet {
			h.handleAdminSettingsGet(w)
		} else {
			h.handleAdminSettingsUpdate(w, r)
		}
	case r.URL.Path == "/api/admin/qr.png" && r.Method == http.MethodGet:
		if !requireLoopback(w, r) {
			return
		}
		h.handleAdminQR(w, r)
	case r.URL.Path == "/api/admin/restart" && r.Method == http.MethodPost:
		if !requireLoopback(w, r) {
			return
		}
		h.handleAdminRestart(w)
	case r.URL.Path == "/upload/chunked/init" && r.Method == http.MethodPost:
		h.handleChunkInit(w, r)
	case r.URL.Path == "/upload/chunked/chunk" && (r.Method == http.MethodPut || r.Method == http.MethodPost):
		h.handleChunkWrite(w, r)
	case r.URL.Path == "/upload/chunked/complete" && r.Method == http.MethodPost:
		h.handleChunkComplete(w, r)
	case r.URL.Path == "/upload/chunked/abort" && r.Method == http.MethodPost:
		h.handleChunkAbort(w, r)
	case r.URL.Path == "/upload/" && r.Method == http.MethodPost:
		h.handleLegacyUpload(w, r)
	case strings.HasPrefix(r.URL.Path, "/download/") && (r.Method == http.MethodGet || r.Method == http.MethodHead):
		h.handleDownload(w, r)
	case strings.HasPrefix(r.URL.Path, "/thumbnails/") && (r.Method == http.MethodGet || r.Method == http.MethodHead):
		h.handleThumbnail(w, r)
	default:
		h.web.ServeHTTP(w, r)
	}
}

func (h *Handler) ensureStorage() error {
	if err := h.share.Ensure(); err != nil {
		return err
	}
	return os.MkdirAll(h.thumbDir, 0o755)
}

func (h *Handler) handleTransferSettings(w http.ResponseWriter) {
	h.writeJSON(w, http.StatusOK, map[string]any{
		"parallel_chunks":     h.settings.ParallelChunks(),
		"chunk_size_bytes":    h.settings.ChunkSizeBytes(),
		"max_file_size_bytes": h.settings.MaxFileSizeBytes(),
	})
}

func (h *Handler) handleFiles(w http.ResponseWriter, _ *http.Request) {
	if err := h.ensureStorage(); err != nil {
		http.Error(w, "Storage configuration error.", http.StatusInternalServerError)
		return
	}

	files, err := h.share.ListFiles()
	if err != nil {
		http.Error(w, "Failed to list files.", http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]any{"files": files})
}

func (h *Handler) handleDownload(w http.ResponseWriter, r *http.Request) {
	if err := h.ensureStorage(); err != nil {
		http.Error(w, "Storage configuration error.", http.StatusInternalServerError)
		return
	}

	relative := strings.TrimPrefix(r.URL.Path, "/download/")
	if relative == "" {
		http.NotFound(w, r)
		return
	}

	path, err := h.share.Join(relative)
	if err != nil {
		http.NotFound(w, r)
		return
	}

	f, err := os.Open(path)
	if err != nil {
		http.NotFound(w, r)
		return
	}
	defer f.Close()

	stat, err := f.Stat()
	if err != nil || !stat.Mode().IsRegular() {
		http.NotFound(w, r)
		return
	}

	w.Header().Set("Accept-Ranges", "bytes")
	if ctype := mime.TypeByExtension(filepath.Ext(stat.Name())); ctype != "" {
		w.Header().Set("Content-Type", ctype)
	}
	http.ServeContent(w, r, stat.Name(), stat.ModTime(), f)
}

func (h *Handler) handleThumbnail(w http.ResponseWriter, r *http.Request) {
	if err := h.ensureStorage(); err != nil {
		http.Error(w, "Storage configuration error.", http.StatusInternalServerError)
		return
	}

	relative := strings.TrimPrefix(r.URL.Path, "/thumbnails/")
	if relative == "" {
		http.NotFound(w, r)
		return
	}

	path, err := share.SafeJoin(h.thumbDir, relative+".jpg")
	if err != nil {
		http.NotFound(w, r)
		return
	}

	f, err := os.Open(path)
	if err != nil {
		http.NotFound(w, r)
		return
	}
	defer f.Close()

	stat, err := f.Stat()
	if err != nil || !stat.Mode().IsRegular() {
		http.NotFound(w, r)
		return
	}

	w.Header().Set("Content-Type", "image/jpeg")
	http.ServeContent(w, r, stat.Name(), stat.ModTime(), f)
}

func (h *Handler) handleLegacyUpload(w http.ResponseWriter, r *http.Request) {
	if err := h.ensureStorage(); err != nil {
		http.Error(w, "Storage configuration error.", http.StatusInternalServerError)
		return
	}

	maxUpload := h.settings.MaxFileSizeBytes()
	maxRequest := maxUpload + extraMultipartOverhead
	if r.ContentLength > maxRequest {
		http.Error(w, "Upload exceeds limit.", http.StatusRequestEntityTooLarge)
		return
	}
	if r.ContentLength <= 0 {
		http.Error(w, "Missing Content-Length header.", http.StatusLengthRequired)
		return
	}

	r.Body = http.MaxBytesReader(w, r.Body, maxRequest)
	reader, err := r.MultipartReader()
	if err != nil {
		http.Error(w, "Expected multipart/form-data.", http.StatusBadRequest)
		return
	}

	var filename string
	for {
		part, err := reader.NextPart()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			http.Error(w, "Malformed multipart payload.", http.StatusBadRequest)
			return
		}

		if part.FormName() != "file" {
			_, _ = io.Copy(io.Discard, part)
			_ = part.Close()
			continue
		}

		cleanName, err := share.SanitizeFilename(part.FileName())
		if err != nil {
			_ = part.Close()
			http.Error(w, "Invalid file name.", http.StatusBadRequest)
			return
		}

		destination, err := h.share.Join(cleanName)
		if err != nil {
			_ = part.Close()
			http.Error(w, "Invalid destination path.", http.StatusBadRequest)
			return
		}

		tempID, randErr := randomID(6)
		if randErr != nil {
			_ = part.Close()
			http.Error(w, "Failed to allocate upload target.", http.StatusInternalServerError)
			return
		}
		tempPath := filepath.Join(h.share.Root(), ".mizban-upload-"+tempID+"-"+cleanName+".tmp")
		if err := streamToTempFile(part, tempPath, maxUpload); err != nil {
			_ = part.Close()
			status := http.StatusInternalServerError
			if errors.Is(err, errTooLarge) {
				status = http.StatusRequestEntityTooLarge
			}
			http.Error(w, err.Error(), status)
			return
		}
		_ = part.Close()

		if err := replaceFile(tempPath, destination); err != nil {
			_ = os.Remove(tempPath)
			http.Error(w, "Failed to save file.", http.StatusInternalServerError)
			return
		}

		thumbPath, thumbErr := share.SafeJoin(h.thumbDir, cleanName+".jpg")
		if thumbErr == nil {
			_ = thumb.Generate(destination, thumbPath)
		}

		filename = cleanName
		break
	}

	if filename == "" {
		http.Error(w, "No file provided.", http.StatusBadRequest)
		return
	}

	h.writeJSON(w, http.StatusCreated, map[string]any{
		"filename": filename,
		"message":  "Uploaded",
	})
}

func (h *Handler) handleChunkInit(w http.ResponseWriter, r *http.Request) {
	if err := h.ensureStorage(); err != nil {
		http.Error(w, "Storage configuration error.", http.StatusInternalServerError)
		return
	}

	var req struct {
		Filename  string `json:"filename"`
		Size      int64  `json:"size"`
		ChunkSize int64  `json:"chunk_size"`
	}
	if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON payload.", http.StatusBadRequest)
		return
	}

	initData, err := h.uploads.Init(req.Filename, req.Size, req.ChunkSize)
	if err != nil {
		if errors.Is(err, ErrInvalidUpload) {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		http.Error(w, "Failed to create upload session.", http.StatusInternalServerError)
		return
	}

	h.writeJSON(w, http.StatusCreated, initData)
}

func (h *Handler) handleChunkWrite(w http.ResponseWriter, r *http.Request) {
	uploadID := r.Header.Get("X-Upload-ID")
	chunkIndex, err := parseIntHeader(r.Header.Get("X-Chunk-Index"))
	if err != nil {
		http.Error(w, "Missing or invalid X-Chunk-Index header.", http.StatusBadRequest)
		return
	}
	offset, err := parseInt64Header(r.Header.Get("X-Chunk-Offset"))
	if err != nil {
		http.Error(w, "Missing or invalid X-Chunk-Offset header.", http.StatusBadRequest)
		return
	}
	if uploadID == "" {
		http.Error(w, "Missing X-Upload-ID header.", http.StatusBadRequest)
		return
	}
	if r.ContentLength <= 0 {
		http.Error(w, "Missing Content-Length header.", http.StatusLengthRequired)
		return
	}

	err = h.uploads.WriteChunk(uploadID, chunkIndex, offset, r.ContentLength, r.Body)
	if err != nil {
		switch {
		case errors.Is(err, ErrSessionNotFound):
			http.Error(w, err.Error(), http.StatusNotFound)
		case errors.Is(err, ErrInvalidUpload):
			http.Error(w, err.Error(), http.StatusBadRequest)
		default:
			http.Error(w, "Failed to write chunk.", http.StatusInternalServerError)
		}
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]any{
		"message":     "Chunk received",
		"upload_id":   uploadID,
		"chunk_index": chunkIndex,
	})
}

func (h *Handler) handleChunkComplete(w http.ResponseWriter, r *http.Request) {
	var req struct {
		UploadID string `json:"upload_id"`
	}
	if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON payload.", http.StatusBadRequest)
		return
	}
	if req.UploadID == "" {
		http.Error(w, "Missing upload_id.", http.StatusBadRequest)
		return
	}

	filename, err := h.uploads.Complete(req.UploadID)
	if err != nil {
		switch t := err.(type) {
		case *IncompleteUploadError:
			h.writeJSON(w, http.StatusConflict, map[string]any{
				"error":          t.Error(),
				"missing_chunks": t.MissingChunks,
			})
			return
		default:
			switch {
			case errors.Is(err, ErrSessionNotFound):
				http.Error(w, err.Error(), http.StatusNotFound)
			case errors.Is(err, ErrInvalidUpload):
				http.Error(w, err.Error(), http.StatusBadRequest)
			default:
				http.Error(w, "Failed to finalize upload.", http.StatusInternalServerError)
			}
			return
		}
	}

	h.writeJSON(w, http.StatusCreated, map[string]any{
		"filename": filename,
		"message":  "Uploaded",
	})
}

func (h *Handler) handleChunkAbort(w http.ResponseWriter, r *http.Request) {
	var req struct {
		UploadID string `json:"upload_id"`
	}
	if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON payload.", http.StatusBadRequest)
		return
	}
	if req.UploadID == "" {
		http.Error(w, "Missing upload_id.", http.StatusBadRequest)
		return
	}

	err := h.uploads.Abort(req.UploadID)
	if err != nil && !errors.Is(err, ErrSessionNotFound) {
		http.Error(w, "Failed to abort upload.", http.StatusInternalServerError)
		return
	}
	h.writeJSON(w, http.StatusOK, map[string]string{"message": "Aborted"})
}

func (h *Handler) handleAdminPage(w http.ResponseWriter, _ *http.Request) {
	html := `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Mizban Settings</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; background: #f8fafc; margin: 0; color: #0f172a; }
    .container { max-width: 920px; margin: 20px auto; padding: 0 16px; }
    .card { background: white; border-radius: 14px; box-shadow: 0 8px 24px rgba(15,23,42,0.08); padding: 20px; margin-bottom: 16px; }
    h1 { margin: 0 0 6px; font-size: 24px; }
    p { margin: 0 0 8px; color: #475569; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    .full { grid-column: 1 / -1; }
    label { display: block; font-weight: 600; margin-bottom: 6px; }
    input { width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px; font-size: 14px; }
    button { border: 0; border-radius: 8px; padding: 10px 14px; background: #2563eb; color: white; font-size: 14px; cursor: pointer; }
    button:hover { background: #1d4ed8; }
    code { background: #e2e8f0; border-radius: 6px; padding: 2px 6px; }
    #status { min-height: 24px; font-weight: 600; }
    #status.ok { color: #166534; }
    #status.warn { color: #b45309; }
    #status.err { color: #b91c1c; }
    #qr { border: 1px solid #e2e8f0; border-radius: 10px; background: white; padding: 8px; }
    .hint { margin-top: 6px; color: #64748b; font-size: 12px; }
    @media (max-width: 760px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="container">
    <div class="card">
      <h1>Mizban Local Settings</h1>
      <p>This page is only accessible from <code>localhost</code>.</p>
      <p>LAN URL: <a id="lanUrl" href="/" target="_blank" rel="noreferrer">loading...</a></p>
      <p>Admin URL: <code id="adminUrl">loading...</code></p>
      <img id="qr" width="220" height="220" alt="QR code" />
    </div>

    <form id="settingsForm" class="card">
      <div class="grid">
        <div class="full">
          <label for="sharedDir">Shared Folder</label>
          <input id="sharedDir" type="text" required />
          <div class="hint">Enter an absolute folder path on this server machine. Example: <code>/home/username/Desktop/MizbanShared</code> on Linux/macOS or <code>C:\Users\YourName\Desktop\MizbanShared</code> on Windows.</div>
        </div>
        <div>
          <label for="port">Port</label>
          <input id="port" type="number" min="1" max="65535" required />
        </div>
        <div>
          <label for="parallelChunks">Parallel Chunks</label>
          <input id="parallelChunks" type="number" min="1" max="64" required />
        </div>
        <div>
          <label for="chunkSizeBytes">Chunk Size (bytes)</label>
          <input id="chunkSizeBytes" type="number" min="262144" required />
        </div>
        <div>
          <label for="maxFileSizeBytes">Max File Size (bytes)</label>
          <input id="maxFileSizeBytes" type="number" min="1" required />
        </div>
      </div>
      <div style="margin-top: 14px; display:flex; gap: 10px; align-items:center;">
        <button type="submit">Save Settings</button>
        <button type="button" id="restartNow" style="background:#475569;">Restart Now</button>
        <span id="status"></span>
      </div>
    </form>
  </div>

  <script>
    let runtimeInfo = null;

    async function loadSettings() {
      const response = await fetch('/api/admin/settings', { method: 'GET' });
      if (!response.ok) throw new Error('failed to load settings');
      const payload = await response.json();
      const cfg = payload.settings;
      const rt = payload.runtime;
      runtimeInfo = rt;

      document.getElementById('sharedDir').value = cfg.mizban_shared_dir;
      document.getElementById('port').value = cfg.port;
      document.getElementById('parallelChunks').value = cfg.parallel_chunks;
      document.getElementById('chunkSizeBytes').value = cfg.chunk_size_bytes;
      document.getElementById('maxFileSizeBytes').value = cfg.max_file_size_bytes;

      const lan = document.getElementById('lanUrl');
      lan.textContent = rt.lan_url;
      lan.href = rt.lan_url;
      document.getElementById('adminUrl').textContent = rt.admin_url;
      document.getElementById('qr').src = '/api/admin/qr.png?u=' + encodeURIComponent(rt.lan_url);
      const restartButton = document.getElementById('restartNow');
      restartButton.disabled = !rt.restart_supported;
      restartButton.style.opacity = rt.restart_supported ? '1' : '0.5';
      if (rt.port_change_pending) {
        setStatus('Port change is pending restart.', 'warn');
      }
    }

    function setStatus(text, level) {
      const node = document.getElementById('status');
      node.textContent = text;
      node.className = level ? level : '';
    }

    function withBoundPort(rawPort) {
      const port = Number(rawPort);
      if (!Number.isInteger(port) || port < 1 || port > 65535) {
        return null;
      }
      return port;
    }

    function disableAdminActions(disabled) {
      document.getElementById('settingsForm').querySelectorAll('input, button').forEach((node) => {
        node.disabled = disabled;
      });
    }

    function waitForAdminToComeBack(targetPort, maxWaitMs) {
      const probeURL = 'http://127.0.0.1:' + String(targetPort) + '/api/admin/qr.png?u=probe&t=';
      const destination = 'http://127.0.0.1:' + String(targetPort) + '/settings';
      const deadline = Date.now() + maxWaitMs;

      const probe = () => {
        if (Date.now() > deadline) {
          setStatus('Restart timed out. Open ' + destination + ' manually.', 'err');
          return;
        }
        const img = new Image();
        let settled = false;
        img.onload = () => {
          if (settled) {
            return;
          }
          settled = true;
          window.location.href = destination;
        };
        img.onerror = () => {
          if (settled) {
            return;
          }
          settled = true;
          setTimeout(probe, 500);
        };
        img.src = probeURL + String(Date.now());
      };
      probe();
    }

    function beginRestartRedirect(targetPort) {
      let remaining = 4;
      const countdown = () => {
        if (remaining > 0) {
          setStatus('Restarting server... reconnecting in ' + String(remaining) + 's', 'warn');
          remaining -= 1;
          setTimeout(countdown, 1000);
          return;
        }
        setStatus('Waiting for restarted server...', 'warn');
        waitForAdminToComeBack(targetPort, 30000);
      };
      countdown();
    }

    document.getElementById('settingsForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      setStatus('Saving...', '');

      const port = withBoundPort(document.getElementById('port').value);
      if (port === null) {
        setStatus('Port must be between 1 and 65535.', 'err');
        return;
      }

      const payload = {
        mizban_shared_dir: document.getElementById('sharedDir').value,
        port: port,
        parallel_chunks: Number(document.getElementById('parallelChunks').value),
        chunk_size_bytes: Number(document.getElementById('chunkSizeBytes').value),
        max_file_size_bytes: Number(document.getElementById('maxFileSizeBytes').value),
      };

      try {
        const response = await fetch('/api/admin/settings', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await response.json().catch(() => null);
        if (!response.ok) {
          setStatus((data && data.error) ? data.error : 'Failed to save settings.', 'err');
          return;
        }
        if (data.restart_required) {
          setStatus('Saved. Restart Mizban to apply new port.', 'warn');
        } else {
          setStatus('Saved successfully.', 'ok');
        }
        await loadSettings();
      } catch (_err) {
        setStatus('Failed to save settings.', 'err');
      }
    });

    document.getElementById('restartNow').addEventListener('click', async () => {
      let targetPort = null;
      if (runtimeInfo && runtimeInfo.port_change_pending) {
        targetPort = withBoundPort(document.getElementById('port').value);
      } else if (runtimeInfo) {
        targetPort = withBoundPort(runtimeInfo.active_port);
      }
      if (targetPort === null) {
        setStatus('Cannot restart: invalid target port.', 'err');
        return;
      }

      setStatus('Restarting...', 'warn');
      try {
        const response = await fetch('/api/admin/restart', { method: 'POST' });
        const data = await response.json().catch(() => null);
        if (!response.ok) {
          setStatus((data && data.error) ? data.error : 'Failed to restart.', 'err');
          return;
        }
        disableAdminActions(true);
        beginRestartRedirect(targetPort);
      } catch (_err) {
        setStatus('Failed to restart.', 'err');
      }
    });

    loadSettings().catch(() => setStatus('Failed to load settings.', 'err'));
  </script>
</body>
</html>`

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_, _ = io.WriteString(w, html)
}

func (h *Handler) handleAdminSettingsGet(w http.ResponseWriter) {
	h.writeJSON(w, http.StatusOK, h.adminSettingsPayload())
}

func (h *Handler) handleAdminSettingsUpdate(w http.ResponseWriter, r *http.Request) {
	const maxConfigurableFileSize = int64(100) * 1024 * 1024 * 1024

	var req struct {
		SharedDir        *string `json:"mizban_shared_dir"`
		Port             *int    `json:"port"`
		ParallelChunks   *int    `json:"parallel_chunks"`
		ChunkSizeBytes   *int64  `json:"chunk_size_bytes"`
		MaxFileSizeBytes *int64  `json:"max_file_size_bytes"`
	}

	decoder := json.NewDecoder(io.LimitReader(r.Body, 1<<20))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&req); err != nil {
		h.writeJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid JSON payload."})
		return
	}

	restartRequired := false
	changes := make([]string, 0, 5)

	if req.SharedDir != nil {
		sharedDir := strings.TrimSpace(*req.SharedDir)
		if sharedDir == "" {
			h.writeJSON(w, http.StatusBadRequest, map[string]string{"error": "mizban_shared_dir cannot be empty."})
			return
		}
		absSharedDir, err := filepath.Abs(sharedDir)
		if err != nil {
			h.writeJSON(w, http.StatusBadRequest, map[string]string{"error": "mizban_shared_dir is invalid."})
			return
		}
		if err := os.MkdirAll(absSharedDir, 0o755); err != nil {
			h.writeJSON(w, http.StatusBadRequest, map[string]string{"error": "Unable to access shared folder path."})
			return
		}
		if absSharedDir != h.share.Root() {
			if err := h.uploads.UpdateStorage(absSharedDir, h.thumbDir); err != nil {
				h.writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "Failed to apply shared folder."})
				return
			}
			h.share.SetRoot(absSharedDir)
			h.settings.SetSharedDir(absSharedDir)
			changes = append(changes, "mizban_shared_dir")
		}
	}

	if req.Port != nil {
		if *req.Port < 1 || *req.Port > 65535 {
			h.writeJSON(w, http.StatusBadRequest, map[string]string{"error": "port must be between 1 and 65535."})
			return
		}
		if *req.Port != h.settings.Port() {
			h.settings.SetPort(*req.Port)
			restartRequired = true
			changes = append(changes, "port")
		}
	}

	if req.ParallelChunks != nil {
		if *req.ParallelChunks < 1 || *req.ParallelChunks > 64 {
			h.writeJSON(w, http.StatusBadRequest, map[string]string{"error": "parallel_chunks must be between 1 and 64."})
			return
		}
		if *req.ParallelChunks != h.settings.ParallelChunks() {
			h.settings.SetParallelChunks(*req.ParallelChunks)
			changes = append(changes, "parallel_chunks")
		}
	}

	if req.ChunkSizeBytes != nil {
		if *req.ChunkSizeBytes < 256*1024 || *req.ChunkSizeBytes > 64*1024*1024 {
			h.writeJSON(w, http.StatusBadRequest, map[string]string{"error": "chunk_size_bytes must be between 262144 and 67108864."})
			return
		}
		if *req.ChunkSizeBytes != h.settings.ChunkSizeBytes() {
			h.settings.SetChunkSizeBytes(*req.ChunkSizeBytes)
			changes = append(changes, "chunk_size_bytes")
		}
	}

	if req.MaxFileSizeBytes != nil {
		if *req.MaxFileSizeBytes <= 0 || *req.MaxFileSizeBytes > maxConfigurableFileSize {
			h.writeJSON(w, http.StatusBadRequest, map[string]string{"error": "max_file_size_bytes must be between 1 and 107374182400."})
			return
		}
		if *req.MaxFileSizeBytes != h.settings.MaxFileSizeBytes() {
			h.settings.SetMaxFileSizeBytes(*req.MaxFileSizeBytes)
			changes = append(changes, "max_file_size_bytes")
		}
	}

	h.uploads.UpdateLimits(h.settings.MaxFileSizeBytes(), h.settings.ChunkSizeBytes())

	if err := h.settings.Save(); err != nil {
		h.writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "Failed to persist settings."})
		return
	}

	if h.settings.Port() != h.activePort {
		restartRequired = true
	}

	response := h.adminSettingsPayload()
	response["changes"] = changes
	response["restart_required"] = restartRequired
	h.writeJSON(w, http.StatusOK, response)
}

func (h *Handler) handleAdminQR(w http.ResponseWriter, r *http.Request) {
	url := r.URL.Query().Get("u")
	if url == "" {
		url = ServerURL(h.settings.Port())
	}
	png, err := qrcode.Encode(url, qrcode.Low, 256)
	if err != nil {
		http.Error(w, "Failed to generate QR.", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "image/png")
	w.Header().Set("Content-Length", strconv.Itoa(len(png)))
	_, _ = w.Write(png)
}

func (h *Handler) handleAdminRestart(w http.ResponseWriter) {
	if h.restart == nil {
		h.writeJSON(w, http.StatusNotImplemented, map[string]string{
			"error": "Restart is not available in this runtime.",
		})
		return
	}

	accepted := h.restart()
	if !accepted {
		h.writeJSON(w, http.StatusConflict, map[string]string{
			"error": "Restart already in progress.",
		})
		return
	}

	h.writeJSON(w, http.StatusAccepted, map[string]string{
		"message": "Restart scheduled.",
	})
}

func (h *Handler) adminSettingsPayload() map[string]any {
	configuredPort := h.settings.Port()
	activePort := h.activePort
	lanURL := ServerURL(activePort)
	return map[string]any{
		"settings": map[string]any{
			"mizban_shared_dir":   h.share.Root(),
			"port":                configuredPort,
			"parallel_chunks":     h.settings.ParallelChunks(),
			"chunk_size_bytes":    h.settings.ChunkSizeBytes(),
			"max_file_size_bytes": h.settings.MaxFileSizeBytes(),
		},
		"runtime": map[string]any{
			"lan_url":             lanURL,
			"admin_url":           fmt.Sprintf("http://127.0.0.1:%d/settings", activePort),
			"active_port":         activePort,
			"port_change_pending": configuredPort != activePort,
			"restart_supported":   h.restart != nil,
			"loopback_only":       true,
		},
	}
}

func (h *Handler) writeJSON(w http.ResponseWriter, status int, payload any) {
	data, err := json.Marshal(payload)
	if err != nil {
		http.Error(w, "Failed to serialize JSON.", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Content-Length", strconv.Itoa(len(data)))
	w.WriteHeader(status)
	_, _ = w.Write(data)
}

var errTooLarge = errors.New("upload exceeds limit")

func streamToTempFile(src io.Reader, tmpPath string, maxBytes int64) error {
	tmpFile, err := os.OpenFile(tmpPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if err != nil {
		return err
	}

	limited := io.LimitReader(src, maxBytes+1)
	written, copyErr := io.CopyBuffer(tmpFile, limited, make([]byte, 512*1024))
	closeErr := tmpFile.Close()
	if copyErr != nil {
		_ = os.Remove(tmpPath)
		return copyErr
	}
	if closeErr != nil {
		_ = os.Remove(tmpPath)
		return closeErr
	}
	if written > maxBytes {
		_ = os.Remove(tmpPath)
		return errTooLarge
	}
	return nil
}

func parseIntHeader(v string) (int, error) {
	if v == "" {
		return 0, errors.New("empty")
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return 0, err
	}
	return n, nil
}

func parseInt64Header(v string) (int64, error) {
	if v == "" {
		return 0, errors.New("empty")
	}
	n, err := strconv.ParseInt(v, 10, 64)
	if err != nil {
		return 0, err
	}
	return n, nil
}

func requireLoopback(w http.ResponseWriter, r *http.Request) bool {
	if isLoopbackRemoteAddr(r.RemoteAddr) {
		return true
	}
	http.Error(w, "Forbidden: local access only.", http.StatusForbidden)
	return false
}

func isLoopbackRemoteAddr(remoteAddr string) bool {
	host := remoteAddr
	if splitHost, _, err := net.SplitHostPort(remoteAddr); err == nil {
		host = splitHost
	}
	host = strings.Trim(host, "[]")
	if zoneIdx := strings.LastIndex(host, "%"); zoneIdx >= 0 {
		host = host[:zoneIdx]
	}
	ip := net.ParseIP(host)
	if ip == nil {
		return false
	}
	return ip.IsLoopback()
}
