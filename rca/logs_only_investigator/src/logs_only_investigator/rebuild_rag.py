from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def main() -> int:
    """Run the canonical RAG JSON plus vector DB rebuild workflow.

    This wraps the existing repository script as a package entrypoint so operators
    can use one stable command instead of remembering the script path.
    """
    module = _load_converter_module()
    return int(module.main())


def _load_converter_module() -> ModuleType:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "convert_signal_rules_to_rag.py"
    spec = importlib.util.spec_from_file_location("logs_only_investigator_convert_signal_rules_to_rag", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load rebuild script from {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    raise SystemExit(main())
