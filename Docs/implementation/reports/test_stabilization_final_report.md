# Test Stabilization Final Report

Date: 2026-02-08 (includes 2026-02-06 baseline + 2026-02-08 revalidation)

## What was failing

- Pytest runs with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` could fail to collect/execute async tests unless `pytest-asyncio` was explicitly loaded.
- One Core API response schema mismatch caused Pydantic validation failures on the workspace patch response (fixed with a production change isolated to a separate commit).
- `make test-all` (via `make check-stubs`) failed due to bare `pass` statements in `apps/core-api/` (treated as stubby/unimplemented logic).

## Root causes

- The repo intentionally disables third-party pytest plugin autoloading to avoid machine-global plugin interference, but async support depended on an auto-loaded plugin.
- A route returned a shape that did not conform to the declared response model, causing runtime validation errors.
- A few defensive `try/except` blocks and type coercions used `pass` in production code, which violates the repo's "no silent fallbacks" / stub-check policy.

## Fixes applied

- Test infra: explicitly load `pytest-asyncio` even when plugin autoloading is disabled.
  - `tests/conftest.py`: `pytest_plugins = ("pytest_asyncio.plugin",)`
  - Make targets already pass `-p pytest_asyncio.plugin`
- Production bug fix (separate commit): made the workspace patch response conform to the expected response schema so FastAPI/Pydantic validation succeeds.
- Removed bare `pass` statements in Core API production code while preserving behavior:
  - `apps/core-api/rbac.py`: treat unparsable `min_reputation` as unset (`None`)
  - `apps/core-api/request_routes.py`: import and check `fastapi.params.Header` sentinel without `try/except`
  - `apps/core-api/task_routes.py`: import and check `fastapi.params.Query` sentinel without `try/except`
- Documentation/audit trail: added stabilization checklist, status, worklog, and manifests under `Docs/` (canonical spec remains in `Docs/04-system-implementation-spec.md`).
- CI guardrail: added a PR-only CI job that fails if tests/CI/runtime files change without updating:
  - `Docs/implementation/00_status.md`
  - `Docs/implementation/checklists/04_test_stabilization.md`

## Contract changes (thresholds/fields/ranges)

- Added/maintained unit-level data contract tests under `tests/unit/data_contracts/`.
- No contract threshold relaxations were required during stabilization.

## How to run

From repo root:

- Unit: `make test-unit`
- Unit data contracts: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/data_contracts`
- Integration: `make test-integration` (requires local infra via docker compose)
- E2E: `make test-e2e` (requires local infra; slower)
- Unit + integration: `make test-all`

Verification performed for this report:

- Unit: `make test-unit` (3 runs; no flakes observed)
- Unit data contracts: `... pytest ... tests/unit/data_contracts` (3 runs; no flakes observed)
- Integration: `make test-integration` (1 run; green)
- E2E: `make test-e2e` (1 run; green)

## Remaining gated tests (if any)

- Tests marked `external` may skip if externally-managed services are not reachable (for example, the Moltbook adapter).

## Notes

- Warning volume is high (not a test failure): mostly `datetime.utcnow()` deprecations and some Pydantic v2 `.dict()` deprecations. Consider addressing separately to keep future signal high.

## Revalidation Run (2026-02-08, Prompt-10)

### What was failing

- No test failures were observed in this rerun packet.
- Environment issue discovered during command replay: default shell `make` path used `/usr/bin/python3` without pytest installed.

### Root causes

- Local shell path mismatch for Python executable, not a repository test regression.
- Existing warning debt remains (`datetime.utcnow()` and Pydantic `.dict()` deprecations), but warnings did not fail tests.

### Fixes applied

- No production or test logic changes were required for test pass/fail status.
- Used explicit Python override for Make targets during verification:
  - `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test-unit`
  - `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test-integration`
  - `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test-e2e`

### Verification results

- Unit baseline: PASS (15)
- Unit contracts baseline: PASS (6)
- Integration baseline: PASS (169)
- E2E baseline: PASS (8)
- Unit reruns (3x): PASS each run
- Unit contract reruns (3x): PASS each run

No active failing test cluster remained, so 5x previously-failing-test reruns were not applicable for this packet.

## Revalidation Run (2026-02-09, Prompt-10 Post-DIR07)

### What was failing

- `make test-integration` failed on first pass with 2 failures in `tests/integration/worker/test_workflows.py`.
- Failure signal was Temporal connectivity (`localhost:7233` connection refused), not an assertion regression in workflow logic.

### Root causes

- Local Temporal container (`agora-temporal`) was down/crashed after `make up`.
- Container logs showed runtime crash: `fatal error: concurrent map read and map write`.

### Fixes applied

- No product code or test code changes were needed for this packet.
- Recovered infrastructure by restarting Temporal container:
  - `docker start agora-temporal`
- Revalidated the failed scope before full-suite rerun:
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/worker/test_workflows.py`

### Verification results

- `make up` -> PASS
- Unit baseline: `make test-unit` -> PASS (18)
- Unit contracts baseline: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/data_contracts` -> PASS (6)
- Integration baseline (first run): `make test-integration` -> FAIL (Temporal unavailable)
- Targeted workflow rerun after Temporal restart: PASS (6)
- Integration rerun: `make test-integration` -> PASS (176)
- E2E baseline: `make test-e2e` -> PASS (8)
- Unit reruns (3x): PASS each run
- Unit contract reruns (3x): PASS each run
- UI smoke regression check: `npm --prefix apps/web run smoke:artifact-viewer` -> PASS
- `make down` -> PASS

Conclusion: no active test-behavior regression was found; the only red run was an infra startup failure recovered by Temporal restart and confirmed stable via targeted + full reruns.

## Revalidation Run (2026-02-09, Prompt-10 Warning-Noise Stabilization)

### What was failing

- No assertion failures were present; the active stabilization cluster was warning-noise that reduced signal quality.
- Unit and integration output still contained first-party deprecation warnings from:
  - `datetime.utcnow()` usage in Core API + worker modules
  - Pydantic v2 `.dict()` usage in route serialization paths

### Root causes

- Legacy timestamp call sites used naive UTC timestamps (`datetime.utcnow()`), which now emit deprecation warnings.
- Several route paths still used Pydantic v1-era `.dict()` instead of `.model_dump()`.

### Fixes applied

- Replaced first-party `datetime.utcnow()` call sites with timezone-aware `datetime.now(timezone.utc)` in:
  - `apps/core-api/artifact_routes.py`
  - `apps/core-api/log_event_routes.py`
  - `apps/core-api/task_routes.py`
  - `apps/core-api/jwt_utils.py`
  - `apps/worker/pdf_ingest.py`
  - `apps/worker/repo_ingest.py`
  - `apps/worker/sandbox_run.py`
  - `tests/unit/core_api/test_jwt_utils.py` (expired-token fixture timestamp)
- Removed debug `print` token payload traces from `apps/core-api/jwt_utils.py`.
- Replaced first-party Pydantic `.dict()` calls with `.model_dump()` in:
  - `apps/core-api/claim_routes.py`
  - `apps/core-api/draft_routes.py`
  - `apps/core-api/critique_routes.py`

### Verification results

- Unit suite rerun 3x: PASS (`28 passed` each run).
- Affected unit cluster rerun 5x: PASS (`19 passed` each run):
  - `tests/unit/core_api/test_jwt_utils.py`
  - `tests/unit/worker/test_phase_machine.py`
- Targeted integration pack: PASS (`56 passed`).
- Full guarded suite:
  - `make PYTHON=python3 test-all-guarded` -> PASS (`28 unit`, `176 integration`).

### Residual warning note

- Remaining warning volume is now predominantly third-party:
  - botocore auth internals
  - sqlalchemy schema internals
  - reportlab internals
  - CPython importlib swig-related warning families
- No first-party `datetime.utcnow()` or `.dict()` call sites remain under `apps/core-api`, `apps/worker`, and `tests/unit` for this packet scope.

## Revalidation Run (2026-02-09, Prompt-10 Failure-Path Persistence Packet)

### What was failing

- Workflow failure paths could leave `activity_runs.status='running'` when workflow exceptions occurred before explicit activity completion updates.
- This weakens observability and violates explicit-failure persistence expectations.

### Root causes

- `literature_grounding_workflow` and `code_replication_workflow` updated `workflow_runs` to `failed` in `except`, but did not always mark the in-flight `activity_runs` row as `failed`.

### Fixes applied

- `apps/worker/literature_grounding_workflow.py`:
  - tracked active `pdf_ingest` activity run id and marked it `failed` on workflow exceptions.
- `apps/worker/code_replication_workflow.py`:
  - tracked currently active activity run id (`repo_ingest` or `sandbox_run`) and marked it `failed` on workflow exceptions.
- Added critical e2e failure-path coverage:
  - `tests/e2e/workflows/test_literature_grounding.py::test_literature_grounding_workflow__missing_pdf_version__marks_workflow_and_activity_failed`
  - `tests/e2e/workflows/test_code_replication_workflow.py::test_code_replication_workflow__invalid_repo_url__records_failed_activity_and_workflow`

### Verification results

- `make up` -> PASS
- Targeted new failure-path tests:
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_literature_grounding.py::test_literature_grounding_workflow__missing_pdf_version__marks_workflow_and_activity_failed tests/e2e/workflows/test_code_replication_workflow.py::test_code_replication_workflow__invalid_repo_url__records_failed_activity_and_workflow` -> PASS (`2 passed`)
- Full workflow e2e packet rerun:
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_literature_grounding.py tests/e2e/workflows/test_code_replication_workflow.py` -> PASS (`9 passed`)
- `make down` -> PASS

Conclusion: workflow exceptions now persist explicit failure states for both workflow and in-flight activity records in the exercised critical paths.

## Revalidation Run (2026-02-09, Prompt-09 Ordering + Contract Stability Follow-Through)

### What was failing

- No assertion failures were reproduced in the targeted probe scope.
- Guarded full-suite command exposed a guardrail regression from prior workflow hardening:
  - `make PYTHON=python3 test-all-guarded` initially failed at `make check-stubs` because bare `pass` statements remained in workflow exception handlers.

### Root causes

- New best-effort failure-state persistence handlers in:
  - `apps/worker/literature_grounding_workflow.py`
  - `apps/worker/code_replication_workflow.py`
  used `except ...: pass` for secondary update failures, which violates the repo's explicit no-silent-fallback guardrail.

### Fixes applied

- Replaced both bare `pass` handlers with explicit exception logging (`logger.exception(...)`) so secondary persistence failures are auditable.
- Revalidated critical order/flakiness and data-contract stability probes:
  - repeated forward/reverse test-file order runs for workflow e2e cluster
  - repeated e2e and contract-suite reruns

### Verification results

- `make check-stubs` -> PASS (no bare `pass` in production code).
- `make PYTHON=python3 test-all-guarded` -> PASS (`41 unit`, `176 integration`).
- `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_literature_grounding.py tests/e2e/workflows/test_code_replication_workflow.py; done` -> PASS (`9 passed` each run).
- `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_code_replication_workflow.py tests/e2e/workflows/test_literature_grounding.py; done` -> PASS (`9 passed` each run).
- `for i in 1 2 3; do make test-e2e; done` -> PASS (`10 passed` each run).
- `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/data_contracts; done` -> PASS (`6 passed` each run).
- `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/data_contracts; done` -> PASS (`3 passed` each run).
- `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/data_contracts; done` -> PASS (`1 passed` each run).
- Targeted failure-path regressions remain green after handler change:
  - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_literature_grounding.py::test_literature_grounding_workflow__missing_pdf_version__marks_workflow_and_activity_failed tests/e2e/workflows/test_code_replication_workflow.py::test_code_replication_workflow__invalid_repo_url__records_failed_activity_and_workflow` -> PASS (`2 passed`).

Conclusion: ordering/flakiness was not reproduced in the probed critical clusters, data-contract stability remained green across repeated reruns, and the no-silent-fallback guardrail regression introduced by prior hardening was corrected.
