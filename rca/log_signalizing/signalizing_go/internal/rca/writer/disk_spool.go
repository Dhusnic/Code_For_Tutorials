package writer

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"

	"rca/internal/rca/logging"
)

// DiskSpoolStore persists saturated bulk batches to disk and replays them later.
type DiskSpoolStore struct {
	directory    string
	maxBytes     int64
	logger       logging.Logger
	mu           sync.Mutex
	currentBytes int64
}

// NewDiskSpoolStore creates the disk-backed spool store.
func NewDiskSpoolStore(directory string, maxBytes int64, logger logging.Logger) (*DiskSpoolStore, error) {
	if err := os.MkdirAll(directory, 0o755); err != nil {
		return nil, err
	}
	store := &DiskSpoolStore{
		directory: directory,
		maxBytes:  maxBytes,
		logger:    logger,
	}
	store.currentBytes = store.scanCurrentBytes()
	return store, nil
}

// Directory returns the on-disk spool directory.
func (s *DiskSpoolStore) Directory() string {
	return s.directory
}

// EnqueueBatch persists one batch using an atomic file move.
func (s *DiskSpoolStore) EnqueueBatch(actions []map[string]any) error {
	payload, err := json.Marshal(actions)
	if err != nil {
		return err
	}
	payloadSize := int64(len(payload))
	readyName := buildSpoolFileName()
	readyPath := filepath.Join(s.directory, readyName)
	tmpPath := readyPath + ".tmp"

	s.mu.Lock()
	defer s.mu.Unlock()

	nextTotal := s.currentBytes + payloadSize
	if nextTotal > s.maxBytes {
		return fmt.Errorf("Disk spool capacity exceeded; increase bulk_spool_max_bytes or improve drain throughput")
	}

	file, err := os.OpenFile(tmpPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if err != nil {
		return err
	}
	if _, err := file.Write(payload); err != nil {
		_ = file.Close()
		return err
	}
	if err := file.Sync(); err != nil {
		_ = file.Close()
		return err
	}
	if err := file.Close(); err != nil {
		return err
	}
	if err := os.Rename(tmpPath, readyPath); err != nil {
		return err
	}

	s.currentBytes = nextTotal
	s.logger.Warning(
		"Bulk batch spooled to disk",
		logging.F("spool_file", readyPath),
		logging.F("spool_batch_actions", len(actions)),
		logging.F("spool_file_bytes", payloadSize),
		logging.F("spool_total_bytes", s.currentBytes),
		logging.F("spool_max_bytes", s.maxBytes),
	)
	return nil
}

// DequeueOldestBatch loads and removes the oldest ready spool file.
func (s *DiskSpoolStore) DequeueOldestBatch() ([]map[string]any, error) {
	s.mu.Lock()
	files := s.readyFiles()
	if len(files) == 0 {
		s.mu.Unlock()
		return nil, nil
	}
	path := files[0]
	info, err := os.Stat(path)
	if err != nil {
		s.mu.Unlock()
		return nil, err
	}
	size := info.Size()
	content, err := os.ReadFile(path)
	if err != nil {
		s.mu.Unlock()
		return nil, err
	}
	if err := os.Remove(path); err != nil {
		s.mu.Unlock()
		return nil, err
	}
	s.currentBytes -= size
	if s.currentBytes < 0 {
		s.currentBytes = 0
	}
	s.mu.Unlock()

	var payload []map[string]any
	if err := json.Unmarshal(content, &payload); err != nil {
		s.logger.Exception(
			"Failed reading spooled batch; removing corrupt file",
			err,
			logging.F("spool_file", path),
		)
		return nil, nil
	}
	return payload, nil
}

// HasPendingBatches returns true when the spool contains at least one ready batch.
func (s *DiskSpoolStore) HasPendingBatches() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.readyFiles()) > 0
}

// PendingBytes returns the total bytes occupied by ready spool files.
func (s *DiskSpoolStore) PendingBytes() int64 {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.currentBytes
}

func (s *DiskSpoolStore) scanCurrentBytes() int64 {
	var total int64
	for _, path := range s.readyFiles() {
		info, err := os.Stat(path)
		if err == nil {
			total += info.Size()
		}
	}
	return total
}

func (s *DiskSpoolStore) readyFiles() []string {
	matches, _ := filepath.Glob(filepath.Join(s.directory, "*.json"))
	sort.Strings(matches)
	return matches
}

func buildSpoolFileName() string {
	return fmt.Sprintf("%d-%d.json", time.Now().UnixNano(), time.Now().UnixNano()%100000000)
}
