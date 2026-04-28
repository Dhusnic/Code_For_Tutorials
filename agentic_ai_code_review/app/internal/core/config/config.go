package config

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

const (
	ServiceModeLegacy = "legacy"
	ServiceModeHybrid = "hybrid"
	ServiceModeNative = "native"
)

type Settings struct {
	ServiceMode                 string `json:"service_mode"`
	LegacyAPIBaseURL            string `json:"legacy_api_base_url"`
	RequestTimeoutSeconds       int    `json:"request_timeout_seconds"`
	LogLevel                    string `json:"log_level"`
	AutoStartLegacyAPI          bool   `json:"auto_start_legacy_api"`
	LegacyAPIPythonBin          string `json:"legacy_api_python_bin"`
	LegacyAPIScriptPath         string `json:"legacy_api_script_path"`
	LegacyStartupTimeoutSeconds int    `json:"legacy_startup_timeout_seconds"`
	AutoInstallLegacyDeps       bool   `json:"auto_install_legacy_deps"`
}

func Default() Settings {
	return Settings{
		ServiceMode:                 ServiceModeNative,
		LegacyAPIBaseURL:            "http://127.0.0.1:8000",
		RequestTimeoutSeconds:       180,
		LogLevel:                    "info",
		AutoStartLegacyAPI:          false,
		LegacyAPIPythonBin:          "python",
		LegacyAPIScriptPath:         "web/main.py",
		LegacyStartupTimeoutSeconds: 60,
		AutoInstallLegacyDeps:       false,
	}
}

func ResolveConfigPath(explicitPath string) (string, error) {
	if strings.TrimSpace(explicitPath) != "" {
		return explicitPath, nil
	}

	appData := strings.TrimSpace(os.Getenv("APPDATA"))
	if appData == "" {
		return "", errors.New("APPDATA environment variable is not set")
	}
	return filepath.Join(appData, "AgenticAICodeReview", "config.json"), nil
}

func Load(explicitPath string) (Settings, string, error) {
	path, err := ResolveConfigPath(explicitPath)
	if err != nil {
		return Settings{}, "", err
	}

	settings := Default()
	raw, readErr := os.ReadFile(path)
	if readErr == nil && len(raw) > 0 {
		if unmarshalErr := json.Unmarshal(raw, &settings); unmarshalErr != nil {
			return Settings{}, path, unmarshalErr
		}
	}

	applyEnvOverrides(&settings)
	normalize(&settings)
	return settings, path, nil
}

func Save(path string, settings Settings) error {
	normalize(&settings)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}

	payload, err := json.MarshalIndent(settings, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(payload, '\n'), 0o600)
}

func Timeout(settings Settings) time.Duration {
	seconds := settings.RequestTimeoutSeconds
	if seconds <= 0 {
		seconds = Default().RequestTimeoutSeconds
	}
	return time.Duration(seconds) * time.Second
}

func applyEnvOverrides(settings *Settings) {
	if settings == nil {
		return
	}
	if value := strings.TrimSpace(os.Getenv("AGENTIC_SERVICE_MODE")); value != "" {
		settings.ServiceMode = value
	}
	if value := strings.TrimSpace(os.Getenv("AGENTIC_LEGACY_API_BASE_URL")); value != "" {
		settings.LegacyAPIBaseURL = value
	}
	if value := strings.TrimSpace(os.Getenv("AGENTIC_LOG_LEVEL")); value != "" {
		settings.LogLevel = value
	}
	if value := strings.TrimSpace(os.Getenv("AGENTIC_REQUEST_TIMEOUT_SECONDS")); value != "" {
		parsed, err := strconv.Atoi(value)
		if err == nil {
			settings.RequestTimeoutSeconds = parsed
		}
	}
	if value := strings.TrimSpace(os.Getenv("AGENTIC_AUTO_START_LEGACY_API")); value != "" {
		settings.AutoStartLegacyAPI = parseBool(value, settings.AutoStartLegacyAPI)
	}
	if value := strings.TrimSpace(os.Getenv("AGENTIC_LEGACY_API_PYTHON_BIN")); value != "" {
		settings.LegacyAPIPythonBin = value
	}
	if value := strings.TrimSpace(os.Getenv("AGENTIC_LEGACY_API_SCRIPT_PATH")); value != "" {
		settings.LegacyAPIScriptPath = value
	}
	if value := strings.TrimSpace(os.Getenv("AGENTIC_LEGACY_STARTUP_TIMEOUT_SECONDS")); value != "" {
		parsed, err := strconv.Atoi(value)
		if err == nil {
			settings.LegacyStartupTimeoutSeconds = parsed
		}
	}
	if value := strings.TrimSpace(os.Getenv("AGENTIC_AUTO_INSTALL_LEGACY_DEPS")); value != "" {
		settings.AutoInstallLegacyDeps = parseBool(value, settings.AutoInstallLegacyDeps)
	}
}

func normalize(settings *Settings) {
	if settings == nil {
		return
	}
	settings.ServiceMode = strings.ToLower(strings.TrimSpace(settings.ServiceMode))
	settings.ServiceMode = ServiceModeNative
	settings.AutoStartLegacyAPI = false
	settings.AutoInstallLegacyDeps = false
	if strings.TrimSpace(settings.LegacyAPIBaseURL) == "" {
		settings.LegacyAPIBaseURL = Default().LegacyAPIBaseURL
	}
	if settings.RequestTimeoutSeconds <= 0 {
		settings.RequestTimeoutSeconds = Default().RequestTimeoutSeconds
	}
	if strings.TrimSpace(settings.LogLevel) == "" {
		settings.LogLevel = Default().LogLevel
	}
	if strings.TrimSpace(settings.LegacyAPIPythonBin) == "" {
		settings.LegacyAPIPythonBin = Default().LegacyAPIPythonBin
	}
	if strings.TrimSpace(settings.LegacyAPIScriptPath) == "" {
		settings.LegacyAPIScriptPath = Default().LegacyAPIScriptPath
	}
	if settings.LegacyStartupTimeoutSeconds <= 0 {
		settings.LegacyStartupTimeoutSeconds = Default().LegacyStartupTimeoutSeconds
	}
}

func parseBool(value string, fallback bool) bool {
	normalized := strings.ToLower(strings.TrimSpace(value))
	switch normalized {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		return fallback
	}
}
