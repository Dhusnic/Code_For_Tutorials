package util

import (
	"bytes"
	"encoding/json"
	"fmt"
)

// MarshalJSONNoEscape marshals JSON without HTML escaping and trims the trailing newline.
func MarshalJSONNoEscape(value any) ([]byte, error) {
	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(value); err != nil {
		return nil, err
	}
	return bytes.TrimRight(buffer.Bytes(), "\n"), nil
}

// MarshalJSONNoEscapeString marshals JSON and falls back to a string payload when needed.
func MarshalJSONNoEscapeString(value any) []byte {
	encoded, err := MarshalJSONNoEscape(value)
	if err == nil {
		return encoded
	}

	fallback, fallbackErr := MarshalJSONNoEscape(fmt.Sprint(value))
	if fallbackErr == nil {
		return fallback
	}
	return []byte(`""`)
}
