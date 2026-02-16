package server

import (
	"context"
	"errors"
	"fmt"
	"net"
	"net/http"
	"os"
	"strconv"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/aminupy/mizban/internal/config"
	"github.com/aminupy/mizban/internal/share"
)

const socketBufferSize = 4 * 1024 * 1024

// Runtime is the running HTTP server instance.
type Runtime struct {
	settings *config.Settings
	http     *http.Server
	listener net.Listener
	uploads  *UploadManager
	restart  chan struct{}

	shareMgr *share.Manager
	thumbDir string
	webDir   string
}

func New(settings *config.Settings, webDir string) (*Runtime, error) {
	if settings == nil {
		return nil, errors.New("settings is required")
	}
	if webDir == "" {
		return nil, errors.New("web directory is required")
	}

	shareMgr := share.New(settings.SharedDir())
	if err := shareMgr.Ensure(); err != nil {
		return nil, err
	}
	thumbDir := settings.ThumbnailDir()
	if err := os.MkdirAll(thumbDir, 0o755); err != nil {
		return nil, err
	}

	uploadMgr := NewUploadManager(
		shareMgr.Root(),
		thumbDir,
		settings.MaxFileSizeBytes(),
		settings.ChunkSizeBytes(),
	)
	restartCh := make(chan struct{}, 1)
	var restartRequested atomic.Bool

	listener, boundPort, err := bindWithRetry(settings.Host(), settings.Port())
	if err != nil {
		uploadMgr.Close()
		return nil, err
	}
	if boundPort != settings.Port() {
		settings.SetPort(boundPort)
		_ = settings.Save()
	}

	handler, err := NewHandler(
		settings,
		shareMgr,
		thumbDir,
		webDir,
		uploadMgr,
		boundPort,
		func() bool {
			if !restartRequested.CompareAndSwap(false, true) {
				return false
			}
			select {
			case restartCh <- struct{}{}:
				return true
			default:
				restartRequested.Store(false)
				return false
			}
		},
	)
	if err != nil {
		uploadMgr.Close()
		_ = listener.Close()
		return nil, err
	}

	httpServer := &http.Server{
		Handler:           handler,
		ReadHeaderTimeout: 10 * time.Second,
		IdleTimeout:       120 * time.Second,
		MaxHeaderBytes:    1 << 20,
	}

	return &Runtime{
		settings: settings,
		http:     httpServer,
		listener: listener,
		uploads:  uploadMgr,
		restart:  restartCh,
		shareMgr: shareMgr,
		thumbDir: thumbDir,
		webDir:   webDir,
	}, nil
}

func (r *Runtime) Serve() error {
	err := r.http.Serve(r.listener)
	if errors.Is(err, http.ErrServerClosed) {
		return nil
	}
	return err
}

func (r *Runtime) Shutdown(ctx context.Context) error {
	defer r.uploads.Close()
	return r.http.Shutdown(ctx)
}

func (r *Runtime) Port() int {
	addr, ok := r.listener.Addr().(*net.TCPAddr)
	if !ok {
		return r.settings.Port()
	}
	return addr.Port
}

func (r *Runtime) URL() string {
	return ServerURL(r.Port())
}

func (r *Runtime) ShareDir() string {
	return r.shareMgr.Root()
}

func (r *Runtime) WebDir() string {
	return r.webDir
}

func (r *Runtime) ThumbnailDir() string {
	return r.thumbDir
}

func (r *Runtime) RestartSignals() <-chan struct{} {
	return r.restart
}

func bindWithRetry(host string, startPort int) (net.Listener, int, error) {
	if startPort < 1 {
		startPort = 8000
	}

	port := startPort
	for port <= 65535 {
		addr := net.JoinHostPort(host, strconv.Itoa(port))
		listener, err := listenWithSocketTuning(addr)
		if err == nil {
			return listener, port, nil
		}

		retry, permission := isRetryableBindError(err)
		if !retry || port == 65535 {
			return nil, 0, err
		}

		if permission {
			next := port + 1
			if next < 1024 {
				next = 1024
			}
			port = next
			continue
		}
		port++
	}
	return nil, 0, fmt.Errorf("no available port found from %d", startPort)
}

func listenWithSocketTuning(addr string) (net.Listener, error) {
	lc := net.ListenConfig{
		Control: func(_, _ string, rc syscall.RawConn) error {
			if err := rc.Control(func(fd uintptr) {
				// Best-effort tuning: do not fail startup if any option is unsupported.
				setSocketOptionsBestEffort(fd)
			}); err != nil {
				return err
			}
			return nil
		},
	}

	return lc.Listen(context.Background(), "tcp", addr)
}

func isRetryableBindError(err error) (retry bool, permission bool) {
	switch {
	case errors.Is(err, syscall.EADDRINUSE):
		return true, false
	case errors.Is(err, syscall.EACCES), errors.Is(err, syscall.EPERM):
		return true, true
	default:
		return false, false
	}
}
