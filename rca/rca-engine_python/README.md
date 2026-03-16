# RCA Engine Python

This folder contains only the Python implementation of RCA.

Shared runtime assets are outside this folder at the repo root:

- [../config.yml](../config.yml)
- [../rules](../rules)
- [../state](../state)
- [../log_simulations](../log_simulations)

## What Is In This Folder

- [main.py](./main.py): direct Python entrypoint.
- [__init__.py](./__init__.py): legacy adapter used by external `run.py` style lifecycle.
- [appconfig.py](./appconfig.py): legacy config bridge.
- [scripts](./scripts): Python rule validation CLI.
- [src](./src): Python implementation packages.
- [tests](./tests): Python parity/reference tests.
- [requirements.txt](./requirements.txt): Python dependencies.
- [app.json](./app.json): PM2 config for the Python runtime.

## Install Python Dependencies

Create or activate a virtual environment, then install requirements.

From the repo root:

```powershell
cd "D:\Code for tutorials\rca"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\rca-engine_python\requirements.txt
```

If you already have the existing virtual environment, just activate it:

```powershell
cd "D:\Code for tutorials\rca"
.\.venv\Scripts\Activate.ps1
```

## Python Libraries Used

Direct dependencies from [requirements.txt](./requirements.txt):

- `elasticsearch`
  - Python Elasticsearch client.
  - Used for reading events, bulk writing, checkpoint index access, and index operations.
- `PyYAML`
  - Used for app config parsing and YAML rule loading.
- `pytest`
  - Used for the Python test suite.
- `redis`
  - Used by the Redis checkpoint backend.
- `psycopg[binary]`
  - Used by the PostgreSQL checkpoint backend.
- `psutil`
  - Used for local CPU and memory guardrail checks in autoscaling-related runtime logic.

## Run The Python Engine

Run once:

```powershell
cd "D:\Code for tutorials\rca\rca-engine_python"
..\.venv\Scripts\python .\main.py --config ..\config.yml --run-once
```

Run continuously:

```powershell
..\.venv\Scripts\python .\main.py --config ..\config.yml
```

## Legacy Adapter Flow

The legacy adapter still lives in [__init__.py](./__init__.py) and [appconfig.py](./appconfig.py).

If your external runner expects the package-style lifecycle, it should point at this folder and use the shared root config.

PM2 config for the Python runtime is [app.json](./app.json).

## Validate Rules

```powershell
cd "D:\Code for tutorials\rca\rca-engine_python"
..\ .venv\Scripts\python .\scripts\validate_rules.py --rules-dir ..\rules
```

## Run Tests

```powershell
cd "D:\Code for tutorials\rca\rca-engine_python"
..\ .venv\Scripts\python -m pytest -q
```

## Syslog Simulation

The shared simulator lives outside this folder in [../log_simulations](../log_simulations).

Example:

```powershell
cd "D:\Code for tutorials\rca"
.\.venv\Scripts\python .\log_simulations\syslog_simulator.py --defaults .\log_simulations\defaults.json --dry-run
```

## Notes

- The Python runtime now uses the shared root [../config.yml](../config.yml) by default.
- Shared rules and state are outside this folder on purpose so Python and Go operate against the same runtime assets.
