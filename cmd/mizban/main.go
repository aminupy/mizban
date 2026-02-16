package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"runtime"
	"syscall"
	"time"

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

	resolvedWebDir, err := resolveWebDir(webDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to locate frontend assets: %v\n", err)
		os.Exit(1)
	}

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
