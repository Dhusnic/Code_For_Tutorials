//go:build !windows

package legacyruntime

import "os/exec"

func applyPlatformAttrs(cmd *exec.Cmd) {}
