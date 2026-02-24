"""Legacy run.py appconfig bridge for RCA engine."""

from __future__ import annotations

import os

_BASE_DIR = os.path.dirname(__file__)

# Can be overridden by run.py args: -config <path>
config = os.path.join(_BASE_DIR, "config.yml")

# Can be overridden by run.py args: -run_once true
run_once = "false"
