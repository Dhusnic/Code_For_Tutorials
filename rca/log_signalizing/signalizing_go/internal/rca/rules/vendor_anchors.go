package rules

import (
	"fmt"
	"strings"

	"rca/internal/rca/util"
)

var ruleTagToVendor = map[string]string{
	"cisco":                      "cisco",
	"ios":                        "cisco",
	"nxos":                       "cisco",
	"juniper":                    "juniper",
	"junos":                      "juniper",
	"arista":                     "arista",
	"eos":                        "arista",
	"aruba":                      "aruba",
	"hpe":                        "aruba",
	"hewlett_packard_enterprise": "aruba",
	"aos":                        "aruba",
	"aoscx":                      "aruba",
	"aos_switch":                 "aruba",
	"procurve":                   "aruba",
	"huawei":                     "huawei",
	"vrp":                        "huawei",
	"cloudengine":                "huawei",
	"netengine":                  "huawei",
	"quidway":                    "huawei",
	"dell":                       "dell",
	"os10":                       "dell",
	"powerswitch":                "dell",
	"smartfabric":                "dell",
	"dellos":                     "dell",
	"fortinet":                   "fortinet",
	"fortios":                    "fortinet",
	"fortigate":                  "fortinet",
	"checkpoint":                 "checkpoint",
	"paloalto":                   "paloalto",
	"panos":                      "paloalto",
	"f5":                         "f5",
	"bigip":                      "f5",
	"mikrotik":                   "mikrotik",
	"routeros":                   "mikrotik",
}

var vendorTokens = map[string][]string{
	"cisco":     {"cisco", "nx-os", "nxos", "ios", "cat9k", "c9300", "isr"},
	"juniper":   {"juniper", "junos", "srx", "qfx", "mx", "ex"},
	"arista":    {"arista", "eos"},
	"aruba":     {"aruba", "aruba networks", "aruba networking", "hpe", "hpe aruba", "hpe aruba networking", "hewlett packard enterprise", "arubaos", "aos-cx", "aoscx", "aos-switch", "aos switch", "procurve", "aruba central"},
	"huawei":    {"huawei", "huawei technologies", "vrp", "cloudengine", "ce12800", "ce6800", "ce5800", "netengine", "ne40e", "quidway"},
	"dell":      {"dell", "dell emc", "powerswitch", "smartfabric", "smartfabric os10", "os10", "dellos", "n-series", "s-series", "z-series"},
	"fortinet":  {"fortinet", "fortigate", "fortios", "fgt"},
	"checkpoint": {"checkpoint", "check point", "cplogexporter", "gaia"},
	"paloalto":  {"paloalto", "palo alto", "pan-os", "panos", "pa-vm"},
	"f5":        {"f5", "big-ip", "bigip", "ltm", "mcpd", "tmm"},
	"mikrotik":  {"mikrotik", "routeros", "ros", "mtk"},
}

var strictHintFields = []string{
	"observer.vendor",
	"observer.product",
	"observer.type",
	"observer.name",
	"observer.hostname",
	"event.module",
	"event.dataset",
	"data_stream.dataset",
	"device.vendor",
	"device.type",
	"device.model",
	"host.name",
	"host.hostname",
	"agent.name",
	"agent.type",
}

var softHintFields = []string{
	"message",
	"msg",
	"event.original",
}

// VendorAnchorSnapshot is the normalized vendor hint cache for one event.
type VendorAnchorSnapshot struct {
	StrictValues []string
	SoftValues   []string
}

// HasStrictHints returns true when event includes explicit vendor metadata.
func (s VendorAnchorSnapshot) HasStrictHints() bool {
	return len(s.StrictValues) > 0
}

// MatchesVendor returns true when the event hints align with the vendor.
func (s VendorAnchorSnapshot) MatchesVendor(vendor string) bool {
	tokens := vendorTokens[vendor]
	if len(tokens) == 0 {
		return false
	}

	values := s.SoftValues
	if len(s.StrictValues) > 0 {
		values = s.StrictValues
	}

	for _, value := range values {
		for _, token := range tokens {
			if strings.Contains(value, token) {
				return true
			}
		}
	}
	return false
}

// InferRuleVendor returns the canonical vendor inferred from rule tags.
func InferRuleVendor(tags []string) string {
	for _, rawTag := range tags {
		tag := strings.TrimSpace(strings.ToLower(rawTag))
		if tag == "" {
			continue
		}
		if vendor, ok := ruleTagToVendor[tag]; ok {
			return vendor
		}
	}
	return ""
}

// VendorAnchorSnapshotFromEvent builds a snapshot by normalizing vendor-hint fields.
func VendorAnchorSnapshotFromEvent(event map[string]any) VendorAnchorSnapshot {
	return VendorAnchorSnapshot{
		StrictValues: collectFieldValues(event, strictHintFields),
		SoftValues:   collectFieldValues(event, softHintFields),
	}
}

func collectFieldValues(event map[string]any, fields []string) []string {
	values := make([]string, 0)
	for _, field := range fields {
		raw := util.GetNested(event, field)
		if raw == nil && !strings.Contains(field, ".") {
			raw = event[field]
		}
		values = append(values, normalizeVendorValue(raw)...)
	}
	return values
}

func normalizeVendorValue(raw any) []string {
	switch typed := raw.(type) {
	case nil:
		return nil
	case string:
		text := strings.TrimSpace(strings.ToLower(typed))
		if text == "" {
			return nil
		}
		return []string{text}
	case int, int8, int16, int32, int64, uint, uint8, uint16, uint32, uint64, float32, float64, bool:
		text := strings.TrimSpace(strings.ToLower(fmt.Sprint(typed)))
		if text == "" {
			return nil
		}
		return []string{text}
	case []any:
		values := make([]string, 0)
		for _, item := range typed {
			values = append(values, normalizeVendorValue(item)...)
		}
		return values
	case []string:
		values := make([]string, 0, len(typed))
		for _, item := range typed {
			values = append(values, normalizeVendorValue(item)...)
		}
		return values
	default:
		return nil
	}
}
