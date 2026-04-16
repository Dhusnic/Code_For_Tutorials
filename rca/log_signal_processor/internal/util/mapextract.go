// Package util provides utility functions for nested map extraction and timestamp parsing.
// Handles data extraction from Elasticsearch JSON documents with flexible parsing.
package util

import (
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"
)

// timestampLayouts defines common Elasticsearch timestamp formats in priority order.
// Used by ParseTimestamp to attempt parsing in order until one succeeds.
//
// Formats:
//   - RFC3339Nano: "2006-01-02T15:04:05.999999999Z07:00" (universal, most precise)
//   - RFC3339: "2006-01-02T15:04:05Z07:00" (no nanoseconds)
//   - RFC3339Nano-like: Alternative formats with different separators
//   - ISO8601: "2006-01-02 15:04:05" (space separator)
var timestampLayouts = []string{
	time.RFC3339Nano,
	time.RFC3339,
	"2006-01-02T15:04:05.999999999Z07:00",
	"2006-01-02T15:04:05.999999999",
	"2006-01-02 15:04:05",
	"2006-01-02 15:04:05Z07:00",
}

// LookupPath retrieves a value from nested maps using dot-notation field path.
// Enables access to nested Elasticsearch _source fields without intermediate variables.
//
// Dot-Notation:
//   - "signal": Direct key lookup
//   - "event.organization": Nested lookup (→ source["event"]["organization"])
//   - "level.severity.code": Multi-level nesting
//
// Parameters:
//   - source: Root map (typically Elasticsearch _source)
//   - fieldPath: Dot-separated path (e.g., "event.organization")
//
// Returns:
//   - any: Retrieved value (could be any JSON type)
//   - bool: True if found, false if missing or type mismatch
//
// Behavior:
//   - Empty fieldPath: Returns (nil, false)
//   - Missing intermediate: Returns (nil, false) - no errors
//   - Type mismatch: Returns (nil, false) - expects maps at each level
//   - Returns value as-is: Caller must type-assert as needed
//
// Example:
//
//	hit.Source = {"event": {"organization": "acme"}, "signal": "auth_failed"}
//	value, ok := LookupPath(hit.Source, "event.organization")
//	// value = "acme", ok = true
//	value, ok := LookupPath(hit.Source, "missing.field")
//	// value = nil, ok = false
func LookupPath(source map[string]any, fieldPath string) (any, bool) {
	if fieldPath == "" {
		return nil, false
	}
	current := any(source)
	for _, part := range strings.Split(fieldPath, ".") {
		next, ok := current.(map[string]any)
		if !ok {
			return nil, false
		}
		value, exists := next[part]
		if !exists {
			return nil, false
		}
		current = value
	}
	return current, true
}

// StringValue converts generic JSON values to string with normalization.
// Used to extract log-level and organization fields from Elasticsearch documents.
//
// Conversion Rules (in priority order):
//  1. nil: Returns ("", false) - no value
//  2. string: Returns if non-empty, ("", false) if whitespace-only
//  3. fmt.Stringer: Calls String() method (UUID, enum, custom types support)
//  4. json.Number: Parses as number string
//  5. float64/32: Formats with natural representation (no padding)
//  6. int/int64/int32: Base-10 string
//  7. uint64/uint32: Base-10 unsigned string
//  8. bool: "true" or "false"
//  9. default: fmt.Sprint(value) if non-empty
//
// Whitespace Handling:
//   - Trims leading/trailing space before checking empty
//   - Empty after trim returns ("", false)
//   - Enables handling of JSON nulls encoded as "" or "  "
//
// Parameters:
//   - value: Any JSON-serializable value
//
// Returns:
//   - string: Converted value
//   - bool: True if converted successfully, false if value was nil/empty
//
// Examples:
//
//	StringValue("auth_failed") → ("auth_failed", true)
//	StringValue(42) → ("42", true)
//	StringValue(3.14) → ("3.14", true)
//	StringValue(true) → ("true", true)
//	StringValue("") → ("", false)
//	StringValue("   ") → ("", false)
//	StringValue(nil) → ("", false)
func StringValue(value any) (string, bool) {
	switch typed := value.(type) {
	case nil:
		return "", false
	case string:
		if strings.TrimSpace(typed) == "" {
			return "", false
		}
		return typed, true
	case fmt.Stringer:
		text := strings.TrimSpace(typed.String())
		if text == "" {
			return "", false
		}
		return text, true
	case json.Number:
		return typed.String(), true
	case float64:
		return strconv.FormatFloat(typed, 'f', -1, 64), true
	case float32:
		return strconv.FormatFloat(float64(typed), 'f', -1, 32), true
	case int:
		return strconv.Itoa(typed), true
	case int64:
		return strconv.FormatInt(typed, 10), true
	case int32:
		return strconv.FormatInt(int64(typed), 10), true
	case uint64:
		return strconv.FormatUint(typed, 10), true
	case uint32:
		return strconv.FormatUint(uint64(typed), 10), true
	case bool:
		return strconv.FormatBool(typed), true
	default:
		text := strings.TrimSpace(fmt.Sprint(value))
		if text == "" {
			return "", false
		}
		return text, true
	}
}

// ParseTimestamp converts generic timestamp values to UTC time.Time.
// Handles Elasticsearch timestamp formats (ISO8601 strings, Unix timestamps, numeric types).
// Always returns UTC-normalized time (no timezone ambiguity).
//
// Input Types:
//  1. time.Time: Returned as-is but converted to UTC
//  2. json.Number: Parsed into int/float, then to Unix timestamp
//  3. string: If all digits, treated as numeric; else tried against all formats
//  4. int/int64: Interpreted as Unix timestamp (auto-detects milliseconds vs seconds)
//  5. float64/float32: Unix timestamp with fractional seconds support
//
// String Format Detection:
//   - All digits: Numeric timestamp (int or float string)
//   - Contains non-digits: Try predefined ISO8601 patterns in order
//   - Empty string: Error ("empty timestamp string")
//
// Unix Timestamp Detection:
//   - > 1_000_000_000_000: Interpreted as milliseconds (UnixMilli)
//   - ≤ 1_000_000_000_000: Interpreted as seconds (Unix)
//
// Float Precision:
//   - Splits into seconds + fractional nanoseconds
//   - Preserves sub-second precision for high-resolution timestamps
//
// Parameters:
//   - value: Any JSON value that might represent a timestamp
//
// Returns:
//   - time.Time: UTC-normalized timestamp
//   - error: If conversion fails or unsupported type
//
// Errors Returned:
//   - "empty timestamp string" - String value with no content
//   - "unsupported timestamp format: ..." - String didn't match formats
//   - "unsupported timestamp type: ..." - Type cannot be converted
//   - "strconv errors" - Failed to parse numeric string
//
// Examples:
//
//	ParseTimestamp("2024-01-15T10:30:45Z") → 2024-01-15 10:30:45 UTC
//	ParseTimestamp(1705316445) → 2024-01-15 10:34:05 UTC (Unix seconds)
//	ParseTimestamp(1705316445000) → 2024-01-15 10:34:05 UTC (Unix millis)
//	ParseTimestamp(1705316445.123) → 2024-01-15 10:34:05.123 UTC (with nanos)
//	ParseTimestamp("") → time.Time{}, error ("empty timestamp string")
func ParseTimestamp(value any) (time.Time, error) {
	switch typed := value.(type) {
	case time.Time:
		return typed.UTC(), nil
	case json.Number:
		return parseNumericTimestamp(typed.String())
	case string:
		text := strings.TrimSpace(typed)
		if text == "" {
			return time.Time{}, fmt.Errorf("empty timestamp string")
		}
		if allDigits(text) {
			return parseNumericTimestamp(text)
		}
		for _, layout := range timestampLayouts {
			if parsed, err := time.Parse(layout, text); err == nil {
				return parsed.UTC(), nil
			}
		}
		return time.Time{}, fmt.Errorf("unsupported timestamp format: %q", typed)
	case int:
		return parseUnixInt(int64(typed)), nil
	case int64:
		return parseUnixInt(typed), nil
	case float64:
		return parseUnixFloat(typed), nil
	case float32:
		return parseUnixFloat(float64(typed)), nil
	default:
		return time.Time{}, fmt.Errorf("unsupported timestamp type: %T", value)
	}
}

// parseNumericTimestamp parses a string representation of Unix timestamp (int or float).
// Tries int64 first (common JSON numbers), then falls back to float64 (with fractional seconds).
//
// Parameters:
//   - value: String containing numeric timestamp
//
// Returns:
//   - time.Time: Parsed UTC timestamp
//   - error: If string doesn't parse as int or float
//
// Used by: ParseTimestamp for json.Number and numeric strings
func parseNumericTimestamp(value string) (time.Time, error) {
	intValue, err := strconv.ParseInt(value, 10, 64)
	if err == nil {
		return parseUnixInt(intValue), nil
	}
	floatValue, err := strconv.ParseFloat(value, 64)
	if err != nil {
		return time.Time{}, err
	}
	return parseUnixFloat(floatValue), nil
}

// parseUnixInt converts Unix timestamp (int64) to time.Time with millisecond/second auto-detection.
// Threshold 1_000_000_000_000 (Sep 2001) distinguishes milliseconds from seconds.
//
// Parameters:
//   - value: Unix timestamp (seconds or milliseconds since epoch)
//
// Returns:
//   - time.Time: UTC timestamp
//
// Logic:
//   - > 1_000_000_000_000: time.UnixMilli (milliseconds since epoch)
//   - ≤ 1_000_000_000_000: time.Unix (seconds since epoch)
func parseUnixInt(value int64) time.Time {
	switch {
	case value > 1_000_000_000_000:
		return time.UnixMilli(value).UTC()
	default:
		return time.Unix(value, 0).UTC()
	}
}

// parseUnixFloat converts Unix timestamp (float64) to time.Time with nanosecond precision.
// Preserves fractional seconds by computing nanosecond field separately.
//
// Parameters:
//   - value: Unix timestamp with fractional seconds (seconds.nanoseconds since epoch)
//
// Returns:
//   - time.Time: UTC timestamp preserving fractional precision
//
// Logic:
//  1. > 1_000_000_000_000: Treat as milliseconds (convert to UnixMilli)
//  2. Otherwise: Extract whole seconds, compute fractional nanoseconds
//  3. Combine into time.Unix(sec, nsec)
func parseUnixFloat(value float64) time.Time {
	if value > 1_000_000_000_000 {
		return time.UnixMilli(int64(value)).UTC()
	}
	seconds := int64(value)
	nanos := int64((value - float64(seconds)) * float64(time.Second))
	return time.Unix(seconds, nanos).UTC()
}

// allDigits checks if a string contains only ASCII digits 0-9.
// Used to distinguish numeric timestamps from ISO8601 strings.
//
// Parameters:
//   - value: String to check
//
// Returns:
//   - bool: True if all characters are digits and string is non-empty, false otherwise
func allDigits(value string) bool {
	for _, r := range value {
		if r < '0' || r > '9' {
			return false
		}
	}
	return value != ""
}
