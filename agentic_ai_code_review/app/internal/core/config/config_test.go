package config

import "testing"

func TestDefaultUsesHybridCompatibilityMode(t *testing.T) {
	t.Parallel()

	settings := Default()
	if settings.ServiceMode != ServiceModeHybrid {
		t.Fatalf("expected default service mode %q, got %q", ServiceModeHybrid, settings.ServiceMode)
	}
	if !settings.AutoStartLegacyAPI {
		t.Fatal("expected compatibility backend auto-start to be enabled by default")
	}
}

func TestNormalizePreservesSupportedModes(t *testing.T) {
	t.Parallel()

	cases := []string{ServiceModeLegacy, ServiceModeHybrid, ServiceModeNative}
	for _, mode := range cases {
		mode := mode
		t.Run(mode, func(t *testing.T) {
			t.Parallel()
			settings := Settings{ServiceMode: mode}
			normalize(&settings)
			if settings.ServiceMode != mode {
				t.Fatalf("expected mode %q after normalize, got %q", mode, settings.ServiceMode)
			}
		})
	}
}

func TestNormalizeFallsBackToHybridOnUnknownMode(t *testing.T) {
	t.Parallel()

	settings := Settings{ServiceMode: "unsupported"}
	normalize(&settings)
	if settings.ServiceMode != ServiceModeHybrid {
		t.Fatalf("expected unsupported modes to fall back to %q, got %q", ServiceModeHybrid, settings.ServiceMode)
	}
}
