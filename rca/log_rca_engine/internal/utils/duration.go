package utils

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"time"
)

func ParseDuration(raw string) (time.Duration, error) {
	value := strings.TrimSpace(raw)
	if value == "" {
		return 0, fmt.Errorf("empty duration")
	}
	if parsed, err := time.ParseDuration(value); err == nil {
		return parsed, nil
	}

	re := regexp.MustCompile(`^(\d+)([smhd])$`)
	matches := re.FindStringSubmatch(value)
	if len(matches) != 3 {
		return 0, fmt.Errorf("invalid duration %q", raw)
	}

	amount, err := strconv.Atoi(matches[1])
	if err != nil {
		return 0, fmt.Errorf("parse duration amount %q: %w", matches[1], err)
	}

	switch matches[2] {
	case "s":
		return time.Duration(amount) * time.Second, nil
	case "m":
		return time.Duration(amount) * time.Minute, nil
	case "h":
		return time.Duration(amount) * time.Hour, nil
	case "d":
		return time.Duration(amount) * 24 * time.Hour, nil
	default:
		return 0, fmt.Errorf("unsupported duration unit %q", matches[2])
	}
}
