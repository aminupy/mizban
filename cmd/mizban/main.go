package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"runtime"
	"syscall"
	"time"

	mizban "github.com/aminupy/mizban"
	"github.com/aminupy/mizban/internal/config"
	"github.com/aminupy/mizban/internal/server"
)

var version = "2.0.0"
var errRestartRequested = errors.New("restart requested")

func main() {
	var (
		webDir   string
		showVers bool
	)

	flag.StringVar(&webDir, "web-dir", "", "path to frontend assets")
	flag.BoolVar(&showVers, "version", false, "print version")
	flag.Parse()

	if showVers {
		fmt.Println(version)
		return
	}

	settings, err := config.New()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to load config: %v\n", err)
		os.Exit(1)
	}

	resolvedWebDir, cleanupWebDir, err := resolveOrMaterializeWebDir(webDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to locate frontend assets: %v\n", err)
		os.Exit(1)
	}
	defer cleanupWebDir()

	runtimeServer, err := server.New(settings, resolvedWebDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to start Mizban server: %v\n", err)
		os.Exit(1)
	}

	accessURL := runtimeServer.URL()
	adminURL := fmt.Sprintf("http://127.0.0.1:%d/settings", runtimeServer.Port())
	printBanner(runtimeServer.ShareDir(), accessURL, adminURL)

	if qr, err := server.GenerateASCIIQR(accessURL); err == nil {
		fmt.Println(qr)
	} else {
		fmt.Printf("QR code unavailable: %v\n", err)
	}

	if err := serveUntilSignal(runtimeServer); err != nil {
		if errors.Is(err, errRestartRequested) {
			if restartErr := restartSelf(); restartErr != nil {
				fmt.Fprintf(os.Stderr, "Mizban restart failed: %v\n", restartErr)
				os.Exit(1)
			}
			return
		}
		fmt.Fprintf(os.Stderr, "Mizban stopped with error: %v\n", err)
		os.Exit(1)
	}
}

func serveUntilSignal(rt *server.Runtime) error {
	errCh := make(chan error, 1)
	go func() {
		errCh <- rt.Serve()
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	defer signal.Stop(sigCh)

	select {
	case err := <-errCh:
		return err
	case <-rt.RestartSignals():
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		shutdownErr := rt.Shutdown(ctx)
		serveErr := <-errCh
		if shutdownErr != nil {
			return shutdownErr
		}
		if serveErr != nil {
			return serveErr
		}
		return errRestartRequested
	case <-sigCh:
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		shutdownErr := rt.Shutdown(ctx)
		serveErr := <-errCh
		if shutdownErr != nil {
			return shutdownErr
		}
		return serveErr
	}
}

func restartSelf() error {
	exePath, err := os.Executable()
	if err != nil {
		return err
	}
	args := os.Args[1:]

	if runtime.GOOS == "windows" {
		cmd := exec.Command(exePath, args...)
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		cmd.Stdin = os.Stdin
		if err := cmd.Start(); err != nil {
			return err
		}
		os.Exit(0)
		return nil
	}

	argv := append([]string{exePath}, args...)
	return syscall.Exec(exePath, argv, os.Environ())
}

func printBanner(sharedDir, accessURL, adminURL string) {
	fmt.Println()
	fmt.Println("[MZ]  Mizban - LAN File Sharing Server")
	fmt.Println()
	fmt.Printf("[DIR] Shared folder : %s\n", sharedDir)
	fmt.Printf("[URL] Client URL    : %s\n", accessURL)
	fmt.Printf("[ADM] Local settings: %s\n", adminURL)
	fmt.Println("[QR]  QR code       : Scan below for client URL")
	fmt.Println()
}

func resolveWebDir(explicit string) (string, error) {
	candidates := make([]string, 0, 4)
	if explicit != "" {
		candidates = append(candidates, explicit)
	}

	cwd, err := os.Getwd()
	if err == nil {
		candidates = append(candidates, filepath.Join(cwd, "web"))
	}

	exePath, err := os.Executable()
	if err == nil {
		exeDir := filepath.Dir(exePath)
		candidates = append(candidates,
			filepath.Join(exeDir, "web"),
			filepath.Join(exeDir, "..", "web"),
		)
	}

	for _, cand := range candidates {
		if cand == "" {
			continue
		}
		indexPath := filepath.Join(cand, "index.html")
		if _, err := os.Stat(indexPath); err == nil {
			return filepath.Clean(cand), nil
		}
	}

	return "", fmt.Errorf("web assets not found (checked: %v)", candidates)
}

func resolveOrMaterializeWebDir(explicit string) (string, func(), error) {
	diskPath, diskErr := resolveWebDir(explicit)
	if diskErr == nil {
		return diskPath, func() {}, nil
	}
	if explicit != "" {
		return "", func() {}, diskErr
	}

	tempDir, err := materializeEmbeddedWebDir()
	if err != nil {
		return "", func() {}, fmt.Errorf("%w; embedded fallback failed: %v", diskErr, err)
	}
	return tempDir, func() {
		_ = os.RemoveAll(tempDir)
	}, nil
}

func materializeEmbeddedWebDir() (string, error) {
	webFS, err := mizban.EmbeddedWebFS()
	if err != nil {
		return "", err
	}

	tempDir, err := os.MkdirTemp("", "mizban-web-")
	if err != nil {
		return "", err
	}

	if err := writeFSToDir(webFS, tempDir); err != nil {
		_ = os.RemoveAll(tempDir)
		return "", err
	}

	if _, err := os.Stat(filepath.Join(tempDir, "index.html")); err != nil {
		_ = os.RemoveAll(tempDir)
		return "", fmt.Errorf("embedded index.html missing")
	}

	return tempDir, nil
}

func writeFSToDir(src fs.FS, dst string) error {
	return fs.WalkDir(src, ".", func(path string, d fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if path == "." {
			return nil
		}

		targetPath := filepath.Join(dst, filepath.FromSlash(path))
		if d.IsDir() {
			return os.MkdirAll(targetPath, 0o755)
		}

		if err := os.MkdirAll(filepath.Dir(targetPath), 0o755); err != nil {
			return err
		}

		mode := fs.FileMode(0o644)
		if info, err := d.Info(); err == nil {
			mode = info.Mode().Perm()
			if mode == 0 {
				mode = 0o644
			}
		}

		in, err := src.Open(path)
		if err != nil {
			return err
		}
		defer in.Close()

		out, err := os.OpenFile(targetPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, mode)
		if err != nil {
			return err
		}

		if _, err := io.Copy(out, in); err != nil {
			_ = out.Close()
			return err
		}
		return out.Close()
	})
}
