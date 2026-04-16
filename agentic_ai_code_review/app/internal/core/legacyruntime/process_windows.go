//go:build windows

package legacyruntime

import (
	"os/exec"
	"syscall"
)

func applyPlatformAttrs(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{
		HideWindow: true,
	}
}
