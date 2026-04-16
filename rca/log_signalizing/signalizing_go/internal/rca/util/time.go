package util

import "time"

const (
	utcISOLayout   = "2006-01-02T15:04:05.000000+00:00"
	plainLogLayout = "2006-01-02 15:04:05,000"
)

// FormatUTCISO formats time like Python's datetime.now(timezone.utc).isoformat().
func FormatUTCISO(value time.Time) string {
	return value.UTC().Format(utcISOLayout)
}

// FormatPlainLogTimestamp formats time like Python logging's default asctime.
func FormatPlainLogTimestamp(value time.Time) string {
	return value.Local().Format(plainLogLayout)
}
