package config

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sync"
)

const (
	defaultPort           = 8000
	defaultParallelChunks = 8
	defaultChunkSizeBytes = 4 * 1024 * 1024
	defaultMaxFileSize    = int64(100) * 1024 * 1024 * 1024
)

// Settings keeps Mizban configuration compatible with the historical Python layout.
type Settings struct {
	mu sync.RWMutex

	homeDir    string
	configDir  string
	configFile string
	cacheDir   string

	data map[string]any
}

func New() (*Settings, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return nil, err
	}
	return NewForHome(home)
}

// NewForHome is mainly for tests.
func NewForHome(home string) (*Settings, error) {
	home = filepath.Clean(home)
	if home == "." || home == string(filepath.Separator) {
		return nil, errors.New("invalid home directory")
	}

	s := &Settings{
		homeDir:    home,
		configDir:  filepath.Join(home, ".config", "Mizban"),
		configFile: filepath.Join(home, ".config", "Mizban", "config.json"),
		cacheDir:   filepath.Join(home, ".cache", "Mizban"),
		data: map[string]any{
			"mizban_shared_dir": filepath.Join(home, "Desktop", "MizbanShared"),
			"port":              defaultPort,
		},
	}

	if err := s.load(); err != nil {
		return nil, err
	}
	return s, nil
}

func (s *Settings) load() error {
	if err := os.MkdirAll(s.configDir, 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll(s.cacheDir, 0o755); err != nil {
		return err
	}

	b, err := os.ReadFile(s.configFile)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return s.Save()
		}
		return err
	}

	var payload map[string]any
	if err := json.Unmarshal(b, &payload); err != nil {
		// Keep defaults when config exists but is malformed.
		return nil
	}

	s.mu.Lock()
	for k, v := range payload {
		s.data[k] = v
	}
	s.mu.Unlock()

	return nil
}

func (s *Settings) Save() error {
	s.mu.RLock()
	payload := make(map[string]any, len(s.data))
	for k, v := range s.data {
		payload[k] = v
	}
	s.mu.RUnlock()

	if err := os.MkdirAll(s.configDir, 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(payload, "", "    ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(s.configFile, b, 0o644)
}

func (s *Settings) ConfigDir() string {
	return s.configDir
}

func (s *Settings) ConfigFile() string {
	return s.configFile
}

func (s *Settings) CacheDir() string {
	return s.cacheDir
}

func (s *Settings) ThumbnailDir() string {
	return filepath.Join(s.cacheDir, ".thumbnails")
}

func (s *Settings) Host() string {
	return "0.0.0.0"
}

func (s *Settings) SharedDir() string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if val, ok := s.data["mizban_shared_dir"].(string); ok && val != "" {
		return filepath.Clean(val)
	}
	return filepath.Join(s.homeDir, "Desktop", "MizbanShared")
}

func (s *Settings) SetSharedDir(dir string) {
	s.mu.Lock()
	s.data["mizban_shared_dir"] = filepath.Clean(dir)
	s.mu.Unlock()
}

func (s *Settings) Port() int {
	s.mu.RLock()
	defer s.mu.RUnlock()

	port := intFromAny(s.data["port"], defaultPort)
	if port < 1 || port > 65535 {
		return defaultPort
	}
	return port
}

func (s *Settings) SetPort(port int) {
	s.mu.Lock()
	s.data["port"] = port
	s.mu.Unlock()
}

func (s *Settings) ParallelChunks() int {
	s.mu.RLock()
	defer s.mu.RUnlock()

	v := intFromAny(s.data["parallel_chunks"], defaultParallelChunks)
	if v < 1 {
		return defaultParallelChunks
	}
	if v > 64 {
		return 64
	}
	return v
}

func (s *Settings) SetParallelChunks(value int) {
	if value < 1 {
		value = defaultParallelChunks
	}
	if value > 64 {
		value = 64
	}
	s.mu.Lock()
	s.data["parallel_chunks"] = value
	s.mu.Unlock()
}

func (s *Settings) ChunkSizeBytes() int64 {
	s.mu.RLock()
	defer s.mu.RUnlock()

	v := int64(intFromAny(s.data["chunk_size_bytes"], defaultChunkSizeBytes))
	if v < 256*1024 {
		return 256 * 1024
	}
	if v > 64*1024*1024 {
		return 64 * 1024 * 1024
	}
	return v
}

func (s *Settings) SetChunkSizeBytes(value int64) {
	if value < 256*1024 {
		value = 256 * 1024
	}
	if value > 64*1024*1024 {
		value = 64 * 1024 * 1024
	}
	s.mu.Lock()
	s.data["chunk_size_bytes"] = value
	s.mu.Unlock()
}

func (s *Settings) MaxFileSizeBytes() int64 {
	s.mu.RLock()
	defer s.mu.RUnlock()

	v := int64(intFromAny(s.data["max_file_size_bytes"], int(defaultMaxFileSize)))
	if v <= 0 {
		return defaultMaxFileSize
	}
	if v > defaultMaxFileSize {
		return defaultMaxFileSize
	}
	return v
}

func (s *Settings) SetMaxFileSizeBytes(value int64) {
	if value <= 0 {
		value = defaultMaxFileSize
	}
	if value > defaultMaxFileSize {
		value = defaultMaxFileSize
	}
	s.mu.Lock()
	s.data["max_file_size_bytes"] = value
	s.mu.Unlock()
}

func intFromAny(v any, fallback int) int {
	switch t := v.(type) {
	case int:
		return t
	case int8:
		return int(t)
	case int16:
		return int(t)
	case int32:
		return int(t)
	case int64:
		return int(t)
	case uint:
		return int(t)
	case uint8:
		return int(t)
	case uint16:
		return int(t)
	case uint32:
		return int(t)
	case uint64:
		return int(t)
	case float64:
		return int(t)
	case float32:
		return int(t)
	case json.Number:
		i, err := t.Int64()
		if err == nil {
			return int(i)
		}
	}
	return fallback
}
