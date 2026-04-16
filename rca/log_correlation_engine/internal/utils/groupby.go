package utils

import (
	"fmt"
	"net"
	"regexp"
	"sort"
	"strings"
)

var ipv4Pattern = regexp.MustCompile(`\b(?:\d{1,3}\.){3}\d{1,3}\b`)

const topologyIdentitySeparator = "::"

func ExtractGroupByValues(metadata map[string]interface{}, fields []string) map[string]string {
	result := make(map[string]string)
	for _, field := range fields {
		result[field] = ExtractGroupByValue(metadata, field)
	}
	return result
}

func ExtractGroupByValue(metadata map[string]interface{}, field string) string {
	switch strings.TrimSpace(field) {
	case "host.ip":
		return firstIP(ExtractIPAddresses(metadata, field))
	case "service.identity":
		return resolveServiceIdentity(metadata)
	case "host.identity":
		return resolveHostIdentity(metadata)
	case "topology.identity":
		return resolveTopologyIdentity(metadata)
	}
	return normalizeStringValue(extractNestedRawValue(metadata, field))
}

func ExtractIPAddresses(metadata map[string]interface{}, field string) []string {
	return extractIPv4Strings(extractNestedRawValue(metadata, field))
}

func extractNestedRawValue(m map[string]interface{}, path string) interface{} {
	if m == nil || path == "" {
		return nil
	}

	if value, ok := m[path]; ok {
		return value
	}

	parts := strings.Split(path, ".")
	var current interface{} = m

	for _, part := range parts {
		switch mp := current.(type) {
		case map[string]interface{}:
			current = mp[part]
		default:
			return ""
		}
	}

	if current == nil {
		return nil
	}

	return current
}

func normalizeStringValue(value interface{}) string {
	if value == nil {
		return ""
	}
	switch typed := value.(type) {
	case []string:
		return strings.Join(typed, ",")
	case []interface{}:
		parts := make([]string, 0, len(typed))
		for _, item := range typed {
			part := strings.TrimSpace(fmt.Sprint(item))
			if part != "" && part != "<nil>" {
				parts = append(parts, part)
			}
		}
		return strings.Join(parts, ",")
	default:
		text := strings.TrimSpace(fmt.Sprint(value))
		if text == "<nil>" {
			return ""
		}
		return text
	}
}

func extractIPv4Strings(value interface{}) []string {
	text := normalizeStringValue(value)
	if text == "" {
		return nil
	}

	matches := ipv4Pattern.FindAllString(text, -1)
	if len(matches) == 0 {
		return nil
	}

	seen := make(map[string]struct{}, len(matches))
	result := make([]string, 0, len(matches))
	for _, match := range matches {
		parsed := net.ParseIP(match)
		if parsed == nil || parsed.To4() == nil {
			continue
		}
		normalized := parsed.To4().String()
		if _, ok := seen[normalized]; ok {
			continue
		}
		seen[normalized] = struct{}{}
		result = append(result, normalized)
	}
	return result
}

func GroupByKey(groupByValues map[string]string) string {
	if len(groupByValues) == 0 {
		return ""
	}

	keys := make([]string, 0, len(groupByValues))
	for key := range groupByValues {
		keys = append(keys, key)
	}
	sort.Strings(keys)

	parts := make([]string, 0, len(keys))
	for _, key := range keys {
		parts = append(parts, fmt.Sprintf("%s=%s", key, groupByValues[key]))
	}
	return strings.Join(parts, "|")
}

func resolveServiceIdentity(metadata map[string]interface{}) string {
	for _, field := range []string{"service.name", "event.module", "host.name"} {
		if value := normalizeStringValue(extractNestedRawValue(metadata, field)); value != "" {
			return value
		}
	}
	return ""
}

func resolveHostIdentity(metadata map[string]interface{}) string {
	if ip := firstIP(ExtractIPAddresses(metadata, "host.ip")); ip != "" {
		return ip
	}
	return normalizeStringValue(extractNestedRawValue(metadata, "host.name"))
}

func resolveTopologyIdentity(metadata map[string]interface{}) string {
	hostIdentity := resolveHostIdentity(metadata)
	serviceIdentity := resolveServiceIdentity(metadata)
	switch {
	case hostIdentity != "" && serviceIdentity != "":
		return hostIdentity + topologyIdentitySeparator + serviceIdentity
	case hostIdentity != "":
		return hostIdentity
	default:
		return serviceIdentity
	}
}

func firstIP(values []string) string {
	for _, value := range values {
		trimmed := strings.TrimSpace(value)
		if trimmed != "" {
			return trimmed
		}
	}
	return ""
}
