package logging

import (
	"bytes"
	"fmt"
	"io"
	"os"
	"reflect"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"rca/internal/rca/config"
	"rca/internal/rca/util"
)

// Field is one structured logging field in insertion order.
type Field struct {
	Key   string
	Value any
}

// Logger writes records using the package-level formatter configuration.
type Logger struct {
	name string
}

type level int

const (
	levelDebug level = iota
	levelInfo
	levelWarning
	levelError
)

type runtimeState struct {
	mu      sync.RWMutex
	minimum level
	json    bool
	output  io.Writer
	timeNow func() time.Time
}

var state = runtimeState{
	minimum: levelInfo,
	json:    true,
	output:  os.Stderr,
	timeNow: time.Now,
}

// F builds one ordered structured field.
func F(key string, value any) Field {
	return Field{Key: key, Value: value}
}

// ConfigureLogging applies the app logging configuration globally.
func ConfigureLogging(cfg config.LoggingConfig) {
	state.mu.Lock()
	defer state.mu.Unlock()
	state.minimum = parseLevel(cfg.Level)
	state.json = cfg.JSON
	if state.output == nil {
		state.output = os.Stderr
	}
	if state.timeNow == nil {
		state.timeNow = time.Now
	}
}

// GetLogger returns a named logger.
func GetLogger(name string) Logger {
	return Logger{name: name}
}

// Debug writes a DEBUG record.
func (l Logger) Debug(message string, fields ...Field) {
	l.log(levelDebug, message, "", fields...)
}

// Info writes an INFO record.
func (l Logger) Info(message string, fields ...Field) {
	l.log(levelInfo, message, "", fields...)
}

// Warning writes a WARNING record.
func (l Logger) Warning(message string, fields ...Field) {
	l.log(levelWarning, message, "", fields...)
}

// Error writes an ERROR record.
func (l Logger) Error(message string, fields ...Field) {
	l.log(levelError, message, "", fields...)
}

// Exception writes an ERROR record with exception text.
func (l Logger) Exception(message string, err error, fields ...Field) {
	l.log(levelError, message, formatException(err), fields...)
}

func (l Logger) log(recordLevel level, message string, exceptionText string, fields ...Field) {
	state.mu.RLock()
	minimum := state.minimum
	jsonMode := state.json
	output := state.output
	timeNow := state.timeNow
	state.mu.RUnlock()

	if recordLevel < minimum || output == nil {
		return
	}

	now := timeNow()
	var rendered string
	if jsonMode {
		rendered = renderJSONLog(now, levelName(recordLevel), l.name, message, exceptionText, fields)
	} else {
		rendered = renderPlainLog(now, levelName(recordLevel), l.name, message, exceptionText)
	}

	_, _ = io.WriteString(output, rendered+"\n")
}

func renderJSONLog(now time.Time, levelNameText string, loggerName string, message string, exceptionText string, fields []Field) string {
	ordered := make([]Field, 0, 4+len(fields)+1)
	ordered = append(ordered,
		F("timestamp", util.FormatUTCISO(now.UTC())),
		F("level", levelNameText),
		F("logger", loggerName),
		F("message", message),
	)
	if exceptionText != "" {
		ordered = append(ordered, F("exception", exceptionText))
	}
	ordered = append(ordered, fields...)

	var buffer bytes.Buffer
	buffer.WriteByte('{')
	for idx, field := range ordered {
		if idx > 0 {
			buffer.WriteString(", ")
		}
		appendASCIIJSONString(&buffer, field.Key)
		buffer.WriteString(": ")
		appendPythonJSONValue(&buffer, field.Value)
	}
	buffer.WriteByte('}')
	return buffer.String()
}

func renderPlainLog(now time.Time, levelNameText string, loggerName string, message string, exceptionText string) string {
	line := fmt.Sprintf(
		"%s %s %s %s",
		util.FormatPlainLogTimestamp(now.Local()),
		levelNameText,
		loggerName,
		message,
	)
	if exceptionText == "" {
		return line
	}
	return line + "\n" + exceptionText
}

func appendPythonJSONValue(buffer *bytes.Buffer, value any) {
	if value == nil {
		buffer.WriteString("null")
		return
	}

	switch typed := value.(type) {
	case string:
		appendASCIIJSONString(buffer, typed)
		return
	case bool:
		if typed {
			buffer.WriteString("true")
		} else {
			buffer.WriteString("false")
		}
		return
	case int:
		buffer.WriteString(strconv.Itoa(typed))
		return
	case int8, int16, int32, int64:
		buffer.WriteString(strconv.FormatInt(reflect.ValueOf(typed).Int(), 10))
		return
	case uint:
		buffer.WriteString(strconv.FormatUint(uint64(typed), 10))
		return
	case uint8, uint16, uint32, uint64, uintptr:
		buffer.WriteString(strconv.FormatUint(reflect.ValueOf(typed).Uint(), 10))
		return
	case float32:
		buffer.WriteString(strconv.FormatFloat(float64(typed), 'g', -1, 32))
		return
	case float64:
		buffer.WriteString(strconv.FormatFloat(typed, 'g', -1, 64))
		return
	case error:
		appendASCIIJSONString(buffer, typed.Error())
		return
	case fmt.Stringer:
		appendASCIIJSONString(buffer, typed.String())
		return
	case []Field:
		appendFieldSliceAsObject(buffer, typed)
		return
	case Field:
		appendFieldSliceAsObject(buffer, []Field{typed})
		return
	case []any:
		appendSlice(buffer, typed)
		return
	case []string:
		converted := make([]any, 0, len(typed))
		for _, item := range typed {
			converted = append(converted, item)
		}
		appendSlice(buffer, converted)
		return
	case map[string]any:
		appendStringMap(buffer, typed)
		return
	}

	rv := reflect.ValueOf(value)
	if !rv.IsValid() {
		buffer.WriteString("null")
		return
	}
	if rv.Kind() == reflect.Pointer {
		if rv.IsNil() {
			buffer.WriteString("null")
			return
		}
		appendPythonJSONValue(buffer, rv.Elem().Interface())
		return
	}
	if rv.Kind() == reflect.Slice || rv.Kind() == reflect.Array {
		appendReflectedSlice(buffer, rv)
		return
	}
	if rv.Kind() == reflect.Map && rv.Type().Key().Kind() == reflect.String {
		keys := rv.MapKeys()
		sortedKeys := make([]string, 0, len(keys))
		for _, key := range keys {
			sortedKeys = append(sortedKeys, key.String())
		}
		sort.Strings(sortedKeys)

		buffer.WriteByte('{')
		for idx, key := range sortedKeys {
			if idx > 0 {
				buffer.WriteString(", ")
			}
			appendASCIIJSONString(buffer, key)
			buffer.WriteString(": ")
			appendPythonJSONValue(buffer, rv.MapIndex(reflect.ValueOf(key)).Interface())
		}
		buffer.WriteByte('}')
		return
	}

	appendASCIIJSONString(buffer, fmt.Sprint(value))
}

func appendSlice(buffer *bytes.Buffer, values []any) {
	buffer.WriteByte('[')
	for idx, item := range values {
		if idx > 0 {
			buffer.WriteString(", ")
		}
		appendPythonJSONValue(buffer, item)
	}
	buffer.WriteByte(']')
}

func appendReflectedSlice(buffer *bytes.Buffer, value reflect.Value) {
	buffer.WriteByte('[')
	for idx := 0; idx < value.Len(); idx++ {
		if idx > 0 {
			buffer.WriteString(", ")
		}
		appendPythonJSONValue(buffer, value.Index(idx).Interface())
	}
	buffer.WriteByte(']')
}

func appendFieldSliceAsObject(buffer *bytes.Buffer, fields []Field) {
	buffer.WriteByte('{')
	for idx, field := range fields {
		if idx > 0 {
			buffer.WriteString(", ")
		}
		appendASCIIJSONString(buffer, field.Key)
		buffer.WriteString(": ")
		appendPythonJSONValue(buffer, field.Value)
	}
	buffer.WriteByte('}')
}

func appendStringMap(buffer *bytes.Buffer, values map[string]any) {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)

	buffer.WriteByte('{')
	for idx, key := range keys {
		if idx > 0 {
			buffer.WriteString(", ")
		}
		appendASCIIJSONString(buffer, key)
		buffer.WriteString(": ")
		appendPythonJSONValue(buffer, values[key])
	}
	buffer.WriteByte('}')
}

func appendASCIIJSONString(buffer *bytes.Buffer, value string) {
	buffer.WriteString(strconv.QuoteToASCII(value))
}

func formatException(err error) string {
	if err == nil {
		return ""
	}
	return strings.TrimSpace(err.Error())
}

func parseLevel(raw string) level {
	switch strings.ToUpper(strings.TrimSpace(raw)) {
	case "DEBUG":
		return levelDebug
	case "WARNING", "WARN":
		return levelWarning
	case "ERROR":
		return levelError
	default:
		return levelInfo
	}
}

func levelName(value level) string {
	switch value {
	case levelDebug:
		return "DEBUG"
	case levelWarning:
		return "WARNING"
	case levelError:
		return "ERROR"
	default:
		return "INFO"
	}
}

// ResetForTests restores package state between tests.
func ResetForTests() {
	state.mu.Lock()
	defer state.mu.Unlock()
	state.minimum = levelInfo
	state.json = true
	state.output = os.Stderr
	state.timeNow = time.Now
}

// SetOutput overrides the package output writer for tests.
func SetOutput(output io.Writer) {
	state.mu.Lock()
	defer state.mu.Unlock()
	state.output = output
}

// SetTimeNowForTests overrides the current-time function for tests.
func SetTimeNowForTests(nowFn func() time.Time) {
	state.mu.Lock()
	defer state.mu.Unlock()
	state.timeNow = nowFn
}
