package utils

import (
	"fmt"
	"regexp"
	"strconv"
	"time"
)

func ParseDuration(s string) (time.Duration, error) {
	if s == "" {
		return 0, fmt.Errorf("empty duration string")
	}

	if parsed, err := time.ParseDuration(s); err == nil {
		return parsed, nil
	}

	re := regexp.MustCompile(`^(\d+)([smhd])$`)
	matches := re.FindStringSubmatch(s)
	if len(matches) == 0 {
		return 0, fmt.Errorf("invalid duration format: %s", s)
	}

	value, err := strconv.Atoi(matches[1])
	if err != nil {
		return 0, fmt.Errorf("invalid duration value: %s", matches[1])
	}

	switch matches[2] {
	case "s":
		return time.Duration(value) * time.Second, nil
	case "m":
		return time.Duration(value) * time.Minute, nil
	case "h":
		return time.Duration(value) * time.Hour, nil
	case "d":
		return time.Duration(value) * 24 * time.Hour, nil
	default:
		return 0, fmt.Errorf("unknown duration unit: %s", matches[2])
	}
}

func FormatDuration(d time.Duration) string {
	if d < time.Minute {
		return fmt.Sprintf("%ds", int(d.Seconds()))
	}
	if d < time.Hour {
		return fmt.Sprintf("%dm", int(d.Minutes()))
	}
	return fmt.Sprintf("%dh", int(d.Hours()))
}
