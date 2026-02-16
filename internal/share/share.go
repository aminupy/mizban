package share

import (
	"errors"
	"net/url"
	"os"
	"path"
	"path/filepath"
	"sort"
	"strings"
	"sync"
)

var errUnsafePath = errors.New("unsafe path")

// Manager handles file operations under MizbanShared.
type Manager struct {
	mu   sync.RWMutex
	root string
}

func New(root string) *Manager {
	return &Manager{root: filepath.Clean(root)}
}

func (m *Manager) Root() string {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.root
}

func (m *Manager) SetRoot(root string) {
	m.mu.Lock()
	m.root = filepath.Clean(root)
	m.mu.Unlock()
}

func (m *Manager) Ensure() error {
	return os.MkdirAll(m.Root(), 0o755)
}

func (m *Manager) ListFiles() ([]string, error) {
	entries, err := os.ReadDir(m.Root())
	if err != nil {
		return nil, err
	}
	files := make([]string, 0, len(entries))
	for _, entry := range entries {
		if entry.Type().IsRegular() {
			files = append(files, entry.Name())
		}
	}
	sort.Strings(files)
	return files, nil
}

func (m *Manager) Join(relative string) (string, error) {
	return SafeJoin(m.Root(), relative)
}

func SafeJoin(root, relative string) (string, error) {
	decoded, err := url.PathUnescape(relative)
	if err != nil {
		return "", errUnsafePath
	}
	if decoded == "" || strings.ContainsRune(decoded, '\x00') {
		return "", errUnsafePath
	}

	normalized := strings.ReplaceAll(decoded, "\\", "/")
	cleanRel := strings.TrimPrefix(path.Clean("/"+normalized), "/")
	if cleanRel == "" || cleanRel == "." {
		return "", errUnsafePath
	}
	if cleanRel == ".." || strings.HasPrefix(cleanRel, "../") || strings.Contains(cleanRel, "/../") {
		return "", errUnsafePath
	}

	root = filepath.Clean(root)
	joined := filepath.Clean(filepath.Join(root, filepath.FromSlash(cleanRel)))
	relToRoot, err := filepath.Rel(root, joined)
	if err != nil {
		return "", errUnsafePath
	}
	if relToRoot == ".." || strings.HasPrefix(relToRoot, ".."+string(filepath.Separator)) {
		return "", errUnsafePath
	}
	return joined, nil
}

func SanitizeFilename(name string) (string, error) {
	name = strings.TrimSpace(name)
	if name == "" || strings.ContainsRune(name, '\x00') {
		return "", errUnsafePath
	}

	name = strings.ReplaceAll(name, "\\", "/")
	base := path.Base(name)
	if base == "." || base == ".." || base == "" {
		return "", errUnsafePath
	}
	if strings.ContainsRune(base, '/') || strings.ContainsRune(base, '\\') {
		return "", errUnsafePath
	}
	return base, nil
}
