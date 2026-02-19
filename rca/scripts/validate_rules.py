"""Validate all YAML rule files under the configured rules directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rules.schema_validator import RuleSchemaValidator


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Validate RCA rule YAML files")
    parser.add_argument("--rules-dir", default="rules", help="Directory containing YAML rule files")
    return parser.parse_args()


def main() -> int:
    """Validate all rule files and return process exit code."""
    args = parse_args()
    rules_dir = Path(args.rules_dir)
    validator = RuleSchemaValidator()
    failed = False

    for path in sorted(rules_dir.rglob("*.yml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            print(f"[FAIL] {path}: file root must be an object")
            failed = True
            continue

        try:
            validator.validate(payload, str(path))
            print(f"[OK]   {path}")
        except ValueError as exc:
            print(f"[FAIL] {exc}")
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
