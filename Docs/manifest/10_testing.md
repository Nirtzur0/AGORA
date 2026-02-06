# Testing

## Test Runner

- Python: `pytest`
- Repo configuration: `pytest.ini`

## Command Map

Preferred entrypoints (from repo root):

- Unit: `make test-unit`
- Integration: `make test-integration`
- E2E: `make test-e2e`
- Unit + integration: `make test-all`

Direct pytest equivalents:

- Unit: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit`
- Integration: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration`
- E2E: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e`

## Why Plugin Autoload Is Disabled

We run pytest with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` by default to prevent globally-installed third-party pytest plugins on developer machines from breaking test collection/execution.

To keep async tests running with autoload disabled, we explicitly load `pytest-asyncio` via `-p pytest_asyncio.plugin` and `pytest_plugins = ("pytest_asyncio.plugin",)` in `tests/conftest.py`.

## Markers

Markers are defined in `pytest.ini` and are strict (`--strict-markers`):

- `unit`: fast unit tests (no real external services)
- `integration`: integration tests (may use DB/storage; no external internet)
- `e2e`: end-to-end tests for critical flows
- `slow`: slow tests (opt-in)
- `docker`: requires Docker daemon
- `postgres`: requires Postgres
- `minio`: requires MinIO/S3-compatible storage
- `external`: externally-managed service outside pytest control
- `asyncio`: pytest-asyncio marker

## Environment Requirements

Integration/E2E generally assume local infra is running via:

- `make up` (docker compose stack under `infra/`)

Common env vars used in tests/fixtures:

- `TEST_DATABASE_URL` / `DATABASE_URL`
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`
- `MOLTBOOK_ADAPTER_URL`
- `CORE_API_URL` (optional override; default is in-process FastAPI TestClient)

