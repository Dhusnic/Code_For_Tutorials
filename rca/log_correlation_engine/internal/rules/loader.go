package rules

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"sync"
	"time"

	"log_correlation_engine/internal/models"
)

type Loader interface {
	LoadRules() error
	GetRules() []models.Rule
	HotReload() error
	Close() error
}

type FileLoader struct {
	filepath      string
	watchInterval time.Duration
	logger        *slog.Logger

	mu          sync.RWMutex
	rules       []models.Rule
	lastModTime time.Time
	ticker      *time.Ticker
	done        chan struct{}
}

func NewFileLoader(filepath string, watchInterval time.Duration, logger *slog.Logger) (*FileLoader, error) {
	if filepath == "" {
		return nil, fmt.Errorf("rules filepath cannot be empty")
	}

	loader := &FileLoader{
		filepath:      filepath,
		watchInterval: watchInterval,
		logger:        logger,
		rules:         make([]models.Rule, 0),
	}
	if err := loader.LoadRules(); err != nil {
		return nil, err
	}
	return loader, nil
}

func (f *FileLoader) LoadRules() error {
	info, err := os.Stat(filepath.Clean(f.filepath))
	if err != nil {
		return fmt.Errorf("stat rules file: %w", err)
	}

	data, err := os.ReadFile(filepath.Clean(f.filepath))
	if err != nil {
		return fmt.Errorf("read rules file: %w", err)
	}

	var rules []models.Rule
	if err := json.Unmarshal(data, &rules); err != nil {
		return fmt.Errorf("parse rules JSON: %w", err)
	}

	enabledRules := make([]models.Rule, 0, len(rules))
	disabledCount := 0
	for _, rule := range rules {
		if !rule.IsEnabled {
			disabledCount++
			continue
		}
		enabledRules = append(enabledRules, rule)
	}

	f.mu.Lock()
	f.rules = enabledRules
	f.lastModTime = info.ModTime()
	f.mu.Unlock()

	if f.logger != nil {
		f.logger.Info(
			"rules loaded",
			"filepath", f.filepath,
			"count", len(enabledRules),
			"disabled_count", disabledCount,
		)
	}
	return nil
}

func (f *FileLoader) GetRules() []models.Rule {
	f.mu.RLock()
	defer f.mu.RUnlock()

	rules := make([]models.Rule, len(f.rules))
	copy(rules, f.rules)
	return rules
}

func (f *FileLoader) HotReload() error {
	if f.watchInterval <= 0 {
		return nil
	}
	if f.ticker != nil {
		return nil
	}

	f.done = make(chan struct{})
	f.ticker = time.NewTicker(f.watchInterval)

	go func() {
		for {
			select {
			case <-f.ticker.C:
				changed, err := f.reloadIfChanged()
				if err != nil {
					if f.logger != nil {
						f.logger.Warn("failed to reload rules", "error", err)
					}
					continue
				}
				if changed && f.logger != nil {
					f.logger.Info("rules reloaded", "filepath", f.filepath)
				}
			case <-f.done:
				return
			}
		}
	}()

	return nil
}

func (f *FileLoader) Close() error {
	if f.ticker != nil {
		f.ticker.Stop()
		f.ticker = nil
	}
	if f.done != nil {
		close(f.done)
		f.done = nil
	}
	return nil
}

func (f *FileLoader) reloadIfChanged() (bool, error) {
	info, err := os.Stat(filepath.Clean(f.filepath))
	if err != nil {
		return false, fmt.Errorf("stat rules file: %w", err)
	}

	f.mu.RLock()
	lastModTime := f.lastModTime
	f.mu.RUnlock()

	if !lastModTime.IsZero() && !info.ModTime().After(lastModTime) {
		return false, nil
	}

	if err := f.LoadRules(); err != nil {
		return false, err
	}
	return true, nil
}
