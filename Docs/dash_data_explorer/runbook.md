# Dash Data Explorer Runbook

Date: 2026-02-09
Prompt packet: `prompt-08-dash-data-explorer`

## Prerequisites

- Python 3.11+ (same environment used for repo tests)
- Repository root with generated report artifacts:
  - `Docs/artifacts/index.json`
  - `Docs/implementation/reports/objective_metrics_latest.json`
  - `Docs/implementation/reports/objective_metrics_history.jsonl`
  - `Docs/implementation/reports/observability_snapshot_latest.json`
  - `paper/artifacts/verification_snapshot.json`

## Install

```bash
python3 -m pip install -r dash_app/requirements.txt
```

Command source path evidence:
- `dash_app/requirements.txt`

## Run the app locally

```bash
python3 dash_app/app.py
```

Then open: `http://localhost:8050`

Command source path evidence:
- `dash_app/app.py`

## Run data-quality validation headlessly

```bash
python3 -m dash_app.data.validation --repo-root . --output /tmp/agora-dash-validation.json
```

Command source path evidence:
- `dash_app/data/validation.py`

## Run Dash explorer tests

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/test_data_validation.py tests/test_loaders_smoke.py
```

Command source path evidence:
- `tests/test_data_validation.py`
- `tests/test_loaders_smoke.py`

## Pointing at real data vs fixtures

- Real data mode (default): `--repo-root .` from repo root.
- Fixture mode: tests use temporary fixture files and temporary repo roots.

## Troubleshooting

- Symptom: `ModuleNotFoundError: No module named 'dash'`
  - Cause: Dash dependencies are not installed.
  - Fix: run install command above.

- Symptom: dataset appears as missing in Overview
  - Cause: required report artifact not generated yet.
  - Fix: run relevant producers:
    - `make PYTHON=python3 check-objective-metrics`
    - `make PYTHON=python3 check-observability-snapshot`
    - `python3 scripts/generate_paper_verification_snapshot.py --output paper/artifacts/verification_snapshot.json`

- Symptom: data-quality page shows freshness failures
  - Cause: latest snapshots older than the expected 72-hour window.
  - Fix: regenerate latest report artifacts with command map gates above.

- Symptom: cross-dataset referential-integrity failure
  - Cause: observability snapshot metric IDs do not match objective metrics IDs.
  - Fix: rerun objective metrics and observability snapshot in sequence.
