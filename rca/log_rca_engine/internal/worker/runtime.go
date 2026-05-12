package worker

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type Runtime struct {
	Count int
	Index int
}

func Resolve() (Runtime, error) {
	count, err := readFirstIntEnv([]string{"RCA_WORKER_COUNT", "WORKER_COUNT", "PM2_INSTANCES", "INSTANCE_COUNT"})
	if err != nil {
		return Runtime{}, err
	}
	index, err := readFirstIntEnv([]string{"RCA_WORKER_ID", "WORKER_ID", "NODE_APP_INSTANCE", "PM2_INSTANCE_ID", "pm_id"})
	if err != nil {
		return Runtime{}, err
	}

	if count <= 0 {
		count = 1
	}
	if index < 0 {
		index = 0
	}
	if count == 1 {
		return Runtime{Count: 1, Index: 0}, nil
	}
	if index >= count {
		return Runtime{}, fmt.Errorf("worker index %d must be less than worker count %d", index, count)
	}

	return Runtime{
		Count: count,
		Index: index,
	}, nil
}

func (r Runtime) Enabled() bool {
	return r.Count > 1
}

func (r Runtime) ScopedPath(path string) string {
	trimmed := strings.TrimSpace(path)
	if trimmed == "" || !r.Enabled() {
		return trimmed
	}

	extension := filepath.Ext(trimmed)
	base := strings.TrimSuffix(trimmed, extension)
	return fmt.Sprintf("%s.worker-%d%s", base, r.Index, extension)
}

func readFirstIntEnv(keys []string) (int, error) {
	for _, key := range keys {
		raw, ok := os.LookupEnv(key)
		if !ok {
			continue
		}
		trimmed := strings.TrimSpace(raw)
		if trimmed == "" {
			continue
		}
		value, err := strconv.Atoi(trimmed)
		if err != nil {
			return 0, fmt.Errorf("%s must be an integer: %w", key, err)
		}
		return value, nil
	}
	return 0, nil
}
