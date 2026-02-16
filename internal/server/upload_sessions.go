package server

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/aminupy/mizban/internal/share"
	"github.com/aminupy/mizban/internal/thumb"
)

var (
	ErrSessionNotFound  = errors.New("upload session not found")
	ErrInvalidUpload    = errors.New("invalid upload request")
	ErrUploadIncomplete = errors.New("upload incomplete")
)

type IncompleteUploadError struct {
	MissingChunks int
}

func (e *IncompleteUploadError) Error() string {
	if e.MissingChunks <= 0 {
		return ErrUploadIncomplete.Error()
	}
	return fmt.Sprintf("upload incomplete: %d chunks missing", e.MissingChunks)
}

type ChunkState uint8

const (
	chunkPending ChunkState = iota
	chunkWriting
	chunkComplete
)

type uploadSession struct {
	id       string
	filename string
	tempPath string
	finalPath string

	size        int64
	chunkSize   int64
	totalChunks int

	file *os.File

	mu            sync.Mutex
	chunkStates   []ChunkState
	receivedCount int
	completed     bool
	createdAt     time.Time
	lastSeen      time.Time
}

func (s *uploadSession) expectedChunkSize(index int) int64 {
	start := int64(index) * s.chunkSize
	remaining := s.size - start
	if remaining < s.chunkSize {
		return remaining
	}
	return s.chunkSize
}

type UploadInit struct {
	UploadID    string `json:"upload_id"`
	Filename    string `json:"filename"`
	Size        int64  `json:"size"`
	ChunkSize   int64  `json:"chunk_size"`
	TotalChunks int    `json:"total_chunks"`
}

// UploadManager coordinates parallel chunked uploads into temp files.
type UploadManager struct {
	root      string
	thumbDir  string
	maxFile   int64
	chunkSize int64

	sessionTTL time.Duration

	mu       sync.RWMutex
	sessions map[string]*uploadSession

	stopCleanup chan struct{}
	cleanupWG   sync.WaitGroup
}

func NewUploadManager(root, thumbDir string, maxFileSize, defaultChunkSize int64) *UploadManager {
	m := &UploadManager{
		root:        filepath.Clean(root),
		thumbDir:    filepath.Clean(thumbDir),
		maxFile:     normalizeMaxFile(maxFileSize),
		chunkSize:   normalizeChunkSize(defaultChunkSize),
		sessionTTL:  90 * time.Minute,
		sessions:    make(map[string]*uploadSession),
		stopCleanup: make(chan struct{}),
	}
	m.cleanupWG.Add(1)
	go m.cleanupLoop()
	return m
}

func (m *UploadManager) Close() {
	close(m.stopCleanup)
	m.cleanupWG.Wait()

	m.mu.Lock()
	sessions := make([]*uploadSession, 0, len(m.sessions))
	for _, s := range m.sessions {
		sessions = append(sessions, s)
	}
	m.sessions = make(map[string]*uploadSession)
	m.mu.Unlock()

	for _, s := range sessions {
		_ = m.cleanupSession(s)
	}
}

func (m *UploadManager) Init(filename string, size, chunkSize int64) (*UploadInit, error) {
	m.mu.RLock()
	root := m.root
	maxFile := m.maxFile
	defaultChunkSize := m.chunkSize
	m.mu.RUnlock()

	name, err := share.SanitizeFilename(filename)
	if err != nil {
		return nil, fmt.Errorf("%w: invalid filename", ErrInvalidUpload)
	}
	if size <= 0 || size > maxFile {
		return nil, fmt.Errorf("%w: file size out of bounds", ErrInvalidUpload)
	}
	if chunkSize <= 0 {
		chunkSize = defaultChunkSize
	}
	chunkSize = normalizeChunkSize(chunkSize)

	totalChunks := int((size + chunkSize - 1) / chunkSize)
	if totalChunks <= 0 {
		return nil, fmt.Errorf("%w: invalid chunk geometry", ErrInvalidUpload)
	}

	id, err := randomID(16)
	if err != nil {
		return nil, err
	}
	tempPath := filepath.Join(root, ".mizban-upload-"+id+".part")
	finalPath, err := share.SafeJoin(root, name)
	if err != nil {
		return nil, fmt.Errorf("%w: invalid destination", ErrInvalidUpload)
	}

	if err := os.MkdirAll(root, 0o755); err != nil {
		return nil, err
	}
	f, err := os.OpenFile(tempPath, os.O_RDWR|os.O_CREATE|os.O_EXCL, 0o644)
	if err != nil {
		return nil, err
	}
	if err := f.Truncate(size); err != nil {
		_ = f.Close()
		_ = os.Remove(tempPath)
		return nil, err
	}

	now := time.Now()
	s := &uploadSession{
		id:          id,
		filename:    name,
		tempPath:    tempPath,
		finalPath:   finalPath,
		size:        size,
		chunkSize:   chunkSize,
		totalChunks: totalChunks,
		file:        f,
		chunkStates: make([]ChunkState, totalChunks),
		createdAt:   now,
		lastSeen:    now,
	}

	m.mu.Lock()
	m.sessions[id] = s
	m.mu.Unlock()

	return &UploadInit{
		UploadID:    id,
		Filename:    name,
		Size:        size,
		ChunkSize:   chunkSize,
		TotalChunks: totalChunks,
	}, nil
}

func (m *UploadManager) WriteChunk(uploadID string, chunkIndex int, offset, contentLength int64, body io.Reader) error {
	if contentLength <= 0 {
		return fmt.Errorf("%w: invalid chunk length", ErrInvalidUpload)
	}

	s := m.get(uploadID)
	if s == nil {
		return ErrSessionNotFound
	}

	s.mu.Lock()
	if s.completed {
		s.mu.Unlock()
		return fmt.Errorf("%w: upload already completed", ErrInvalidUpload)
	}
	if chunkIndex < 0 || chunkIndex >= s.totalChunks {
		s.mu.Unlock()
		return fmt.Errorf("%w: chunk index out of range", ErrInvalidUpload)
	}
	expectedOffset := int64(chunkIndex) * s.chunkSize
	if offset != expectedOffset {
		s.mu.Unlock()
		return fmt.Errorf("%w: chunk offset mismatch", ErrInvalidUpload)
	}
	expectedSize := s.expectedChunkSize(chunkIndex)
	if contentLength != expectedSize {
		s.mu.Unlock()
		return fmt.Errorf("%w: chunk size mismatch", ErrInvalidUpload)
	}

	state := s.chunkStates[chunkIndex]
	if state == chunkComplete {
		s.lastSeen = time.Now()
		s.mu.Unlock()
		_, _ = io.Copy(io.Discard, body)
		return nil
	}
	if state == chunkWriting {
		s.mu.Unlock()
		return fmt.Errorf("%w: chunk currently being written", ErrInvalidUpload)
	}
	s.chunkStates[chunkIndex] = chunkWriting
	f := s.file
	s.mu.Unlock()

	sectionWriter := io.NewOffsetWriter(f, offset)
	written, err := io.CopyBuffer(sectionWriter, io.LimitReader(body, contentLength), make([]byte, 256*1024))
	if err != nil {
		s.mu.Lock()
		s.chunkStates[chunkIndex] = chunkPending
		s.lastSeen = time.Now()
		s.mu.Unlock()
		return err
	}
	if written != contentLength {
		s.mu.Lock()
		s.chunkStates[chunkIndex] = chunkPending
		s.lastSeen = time.Now()
		s.mu.Unlock()
		return fmt.Errorf("%w: short chunk write", ErrInvalidUpload)
	}

	s.mu.Lock()
	if s.chunkStates[chunkIndex] != chunkComplete {
		s.chunkStates[chunkIndex] = chunkComplete
		s.receivedCount++
	}
	s.lastSeen = time.Now()
	s.mu.Unlock()

	return nil
}

func (m *UploadManager) Complete(uploadID string) (string, error) {
	s := m.get(uploadID)
	if s == nil {
		return "", ErrSessionNotFound
	}

	s.mu.Lock()
	if s.completed {
		filename := s.filename
		s.mu.Unlock()
		return filename, nil
	}
	missing := s.totalChunks - s.receivedCount
	if missing > 0 {
		s.mu.Unlock()
		return "", &IncompleteUploadError{MissingChunks: missing}
	}
	s.completed = true
	filename := s.filename
	tmpPath := s.tempPath
	finalPath := s.finalPath
	f := s.file
	s.mu.Unlock()

	if err := f.Sync(); err != nil {
		return "", err
	}
	if err := f.Close(); err != nil {
		return "", err
	}

	if err := replaceFile(tmpPath, finalPath); err != nil {
		return "", err
	}

	m.mu.RLock()
	thumbDir := m.thumbDir
	m.mu.RUnlock()
	thumbPath, err := share.SafeJoin(thumbDir, filename+".jpg")
	if err == nil {
		_ = thumb.Generate(finalPath, thumbPath)
	}

	m.mu.Lock()
	delete(m.sessions, uploadID)
	m.mu.Unlock()
	return filename, nil
}

func (m *UploadManager) Abort(uploadID string) error {
	m.mu.Lock()
	s, ok := m.sessions[uploadID]
	if ok {
		delete(m.sessions, uploadID)
	}
	m.mu.Unlock()
	if !ok {
		return ErrSessionNotFound
	}
	return m.cleanupSession(s)
}

func (m *UploadManager) get(uploadID string) *uploadSession {
	m.mu.RLock()
	s := m.sessions[uploadID]
	m.mu.RUnlock()
	return s
}

func (m *UploadManager) UpdateLimits(maxFileSize, chunkSize int64) {
	m.mu.Lock()
	m.maxFile = normalizeMaxFile(maxFileSize)
	m.chunkSize = normalizeChunkSize(chunkSize)
	m.mu.Unlock()
}

func (m *UploadManager) UpdateStorage(root, thumbDir string) error {
	root = filepath.Clean(root)
	thumbDir = filepath.Clean(thumbDir)
	if err := os.MkdirAll(root, 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll(thumbDir, 0o755); err != nil {
		return err
	}

	m.mu.Lock()
	stale := make([]*uploadSession, 0, len(m.sessions))
	for id, s := range m.sessions {
		stale = append(stale, s)
		delete(m.sessions, id)
	}
	m.root = root
	m.thumbDir = thumbDir
	m.mu.Unlock()

	for _, s := range stale {
		_ = m.cleanupSession(s)
	}
	return nil
}

func (m *UploadManager) cleanupLoop() {
	defer m.cleanupWG.Done()
	ticker := time.NewTicker(10 * time.Minute)
	defer ticker.Stop()

	for {
		select {
		case <-m.stopCleanup:
			return
		case <-ticker.C:
			m.cleanupStale()
		}
	}
}

func (m *UploadManager) cleanupStale() {
	now := time.Now()
	var expired []*uploadSession

	m.mu.Lock()
	for id, s := range m.sessions {
		s.mu.Lock()
		expiredSession := now.Sub(s.lastSeen) > m.sessionTTL
		s.mu.Unlock()
		if expiredSession {
			expired = append(expired, s)
			delete(m.sessions, id)
		}
	}
	m.mu.Unlock()

	for _, s := range expired {
		_ = m.cleanupSession(s)
	}
}

func (m *UploadManager) cleanupSession(s *uploadSession) error {
	s.mu.Lock()
	f := s.file
	tmp := s.tempPath
	s.mu.Unlock()

	if f != nil {
		_ = f.Close()
	}
	if tmp != "" {
		_ = os.Remove(tmp)
	}
	return nil
}

func randomID(numBytes int) (string, error) {
	b := make([]byte, numBytes)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}

func normalizeChunkSize(v int64) int64 {
	if v <= 0 {
		v = 4 * 1024 * 1024
	}
	if v < 256*1024 {
		return 256 * 1024
	}
	if v > 64*1024*1024 {
		return 64 * 1024 * 1024
	}
	return v
}

func normalizeMaxFile(v int64) int64 {
	const hardLimit = int64(100) * 1024 * 1024 * 1024
	if v <= 0 {
		return hardLimit
	}
	if v > hardLimit {
		return hardLimit
	}
	return v
}

func replaceFile(src, dst string) error {
	if err := os.Rename(src, dst); err == nil {
		return nil
	}
	if err := os.Remove(dst); err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}
	return os.Rename(src, dst)
}
