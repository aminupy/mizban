package config

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestConfigCompatibilityAndUnknownFieldsPreserved(t *testing.T) {
	home := t.TempDir()
	cfgDir := filepath.Join(home, ".config", "Mizban")
	if err := os.MkdirAll(cfgDir, 0o755); err != nil {
		t.Fatalf("mkdir cfg dir: %v", err)
	}

	configPath := filepath.Join(cfgDir, "config.json")
	seed := map[string]any{
		"mizban_shared_dir": filepath.Join(home, "Desktop", "LegacyShared"),
		"port":              9001,
		"custom_key":        "keep-me",
	}
	seedJSON, _ := json.Marshal(seed)
	if err := os.WriteFile(configPath, seedJSON, 0o644); err != nil {
		t.Fatalf("write seed config: %v", err)
	}

	s, err := NewForHome(home)
	if err != nil {
		t.Fatalf("load settings: %v", err)
	}

	if got := s.SharedDir(); got != filepath.Join(home, "Desktop", "LegacyShared") {
		t.Fatalf("shared dir mismatch: got=%q", got)
	}
	if got := s.Port(); got != 9001 {
		t.Fatalf("port mismatch: got=%d", got)
	}
	if got := s.ParallelChunks(); got != 8 {
		t.Fatalf("parallel chunk default mismatch: got=%d", got)
	}

	s.SetPort(9100)
	if err := s.Save(); err != nil {
		t.Fatalf("save settings: %v", err)
	}

	raw, err := os.ReadFile(configPath)
	if err != nil {
		t.Fatalf("read config file: %v", err)
	}

	var updated map[string]any
	if err := json.Unmarshal(raw, &updated); err != nil {
		t.Fatalf("decode saved config: %v", err)
	}
	if updated["custom_key"] != "keep-me" {
		t.Fatalf("custom field not preserved: %+v", updated)
	}
	if int(updated["port"].(float64)) != 9100 {
		t.Fatalf("saved port mismatch: %+v", updated)
	}
}

func TestDefaultConfigCreatedWhenMissing(t *testing.T) {
	home := t.TempDir()
	s, err := NewForHome(home)
	if err != nil {
		t.Fatalf("new settings: %v", err)
	}

	if s.Port() != 8000 {
		t.Fatalf("expected default port 8000, got %d", s.Port())
	}

	if _, err := os.Stat(filepath.Join(home, ".config", "Mizban", "config.json")); err != nil {
		t.Fatalf("expected config file to be created: %v", err)
	}
}
