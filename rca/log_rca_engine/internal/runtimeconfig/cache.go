package runtimeconfig

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"sync"
	"time"

	"log_rca_engine/internal/models"
)

type RulesCache struct {
	path    string
	mu      sync.RWMutex
	rules   map[string]models.Rule
	modTime time.Time
}

func NewRulesCache(ctx context.Context, path string) (*RulesCache, error) {
	cache := &RulesCache{path: strings.TrimSpace(path)}
	if err := cache.Reload(ctx); err != nil {
		return nil, err
	}
	return cache, nil
}

func (c *RulesCache) Reload(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	payload, err := os.ReadFile(c.path)
	if err != nil {
		return fmt.Errorf("read rules file: %w", err)
	}
	info, err := os.Stat(c.path)
	if err != nil {
		return fmt.Errorf("stat rules file: %w", err)
	}

	var raw []models.Rule
	if err := json.Unmarshal(payload, &raw); err != nil {
		return fmt.Errorf("decode rules file: %w", err)
	}

	rules := make(map[string]models.Rule, len(raw))
	for _, rule := range raw {
		if strings.TrimSpace(rule.ID) == "" {
			continue
		}
		rules[rule.ID] = rule
	}

	c.mu.Lock()
	c.rules = rules
	c.modTime = info.ModTime()
	c.mu.Unlock()
	return nil
}

func (c *RulesCache) ReloadIfChanged(ctx context.Context) (bool, error) {
	if err := ctx.Err(); err != nil {
		return false, err
	}
	info, err := os.Stat(c.path)
	if err != nil {
		return false, fmt.Errorf("stat rules file: %w", err)
	}
	c.mu.RLock()
	lastModTime := c.modTime
	c.mu.RUnlock()
	if !lastModTime.IsZero() && !info.ModTime().After(lastModTime) {
		return false, nil
	}
	return true, c.Reload(ctx)
}

func (c *RulesCache) Load(ctx context.Context) (map[string]models.Rule, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	c.mu.RLock()
	defer c.mu.RUnlock()

	rules := make(map[string]models.Rule, len(c.rules))
	for id, rule := range c.rules {
		rules[id] = rule
	}
	return rules, nil
}

type TopologyCache struct {
	path     string
	mu       sync.RWMutex
	document models.TopologyDocument
	modTime  time.Time
}

func NewTopologyCache(ctx context.Context, path string) (*TopologyCache, error) {
	cache := &TopologyCache{path: strings.TrimSpace(path)}
	if err := cache.Reload(ctx); err != nil {
		return nil, err
	}
	return cache, nil
}

func (c *TopologyCache) Reload(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	payload, err := os.ReadFile(c.path)
	if err != nil {
		return fmt.Errorf("read topology file: %w", err)
	}
	info, err := os.Stat(c.path)
	if err != nil {
		return fmt.Errorf("stat topology file: %w", err)
	}

	var document models.TopologyDocument
	if err := json.Unmarshal(payload, &document); err != nil {
		return fmt.Errorf("decode topology file: %w", err)
	}
	if document.Organizations == nil {
		document.Organizations = make(map[string]map[string]models.OrganizationTopology)
	}

	c.mu.Lock()
	c.document = document
	c.modTime = info.ModTime()
	c.mu.Unlock()
	return nil
}

func (c *TopologyCache) ReloadIfChanged(ctx context.Context) (bool, error) {
	if err := ctx.Err(); err != nil {
		return false, err
	}
	info, err := os.Stat(c.path)
	if err != nil {
		return false, fmt.Errorf("stat topology file: %w", err)
	}
	c.mu.RLock()
	lastModTime := c.modTime
	c.mu.RUnlock()
	if !lastModTime.IsZero() && !info.ModTime().After(lastModTime) {
		return false, nil
	}
	return true, c.Reload(ctx)
}

func (c *TopologyCache) Load(ctx context.Context) (models.TopologyDocument, error) {
	if err := ctx.Err(); err != nil {
		return models.TopologyDocument{}, err
	}
	c.mu.RLock()
	defer c.mu.RUnlock()
	return cloneTopologyDocument(c.document)
}

func cloneTopologyDocument(input models.TopologyDocument) (models.TopologyDocument, error) {
	payload, err := json.Marshal(input)
	if err != nil {
		return models.TopologyDocument{}, err
	}
	var output models.TopologyDocument
	if err := json.Unmarshal(payload, &output); err != nil {
		return models.TopologyDocument{}, err
	}
	if output.Organizations == nil {
		output.Organizations = make(map[string]map[string]models.OrganizationTopology)
	}
	return output, nil
}
