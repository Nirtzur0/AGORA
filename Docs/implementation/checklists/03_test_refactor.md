# Checklist: Test Refactor

Date: 2026-02-09
Prompt packet: `prompt-09-tests-refactor-suite`

Checked boxes imply command evidence is recorded in `Docs/implementation/03_worklog.md`.

## Bet Tracking

- [x] Appetite set: `medium`.
- [x] `Now` cluster selected: git-repo-backed workflow tests (`tests/e2e/workflows/test_code_replication_workflow.py`, `tests/integration/worker/test_repo_ingestion.py`).
- [x] `Now` cluster state: `uphill` (before implementation complete).
- [x] `Now` cluster state: `downhill` (after helper extraction + tests green).
- [x] Follow-through appetite set: `small`.
- [x] Follow-through `Now` cluster selected: ordering/flakiness probe + data-contract rerun validation (`tests/e2e/workflows/*`, `tests/*/data_contracts/*`).
- [x] Follow-through `Now` cluster state: `uphill` (before probe execution).
- [x] Follow-through `Now` cluster state: `downhill` (after repeat-order and repeat-contract runs passed).

## Deliverable 1: Test Landscape

- [x] `Docs/implementation/reports/test_landscape.md` created.
- [x] Baseline runtime commands captured with source-path evidence.
- [x] Coverage baseline captured (or explicitly scoped).

## Deliverable 2: Architecture Plan

- [x] `Docs/implementation/reports/test_architecture_plan.md` created.
- [x] Proposed folder tree and module responsibilities documented.
- [x] Old -> New mapping defined for active refactor cluster.

## Deliverable 3: Implementation (Now Cluster)

- [x] Add shared deterministic git-repo helper in `tests/helpers/`.
- [x] Refactor `tests/e2e/workflows/test_code_replication_workflow.py` to reuse helper and reduce duplicate Arrange logic.
- [x] Refactor `tests/integration/worker/test_repo_ingestion.py` fixture to reuse helper.
- [x] Keep production behavior unchanged.

## Validation

- [x] Baseline unit runtime recorded.
  - Verify: `/usr/bin/time -p make test-unit`
- [x] Baseline CI-equivalent runtime recorded.
  - Verify: `/usr/bin/time -p make test-all`
- [x] Baseline e2e runtime recorded.
  - Verify: `/usr/bin/time -p make test-e2e`
- [x] Baseline active-cluster test command recorded.
  - Verify: `/usr/bin/time -p sh -c 'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_code_replication_workflow.py tests/integration/worker/test_repo_ingestion.py'`
- [x] Post-refactor active-cluster tests pass.
  - Verify: `/usr/bin/time -p sh -c 'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_code_replication_workflow.py tests/integration/worker/test_repo_ingestion.py'` -> PASS (`8 passed`, `real 5.21s`)
- [x] Post-refactor `make test-unit` passes.
  - Verify: `/usr/bin/time -p make test-unit` -> PASS (`18 passed`, `real 0.77s`)
- [x] Post-refactor `make test-all` passes.
  - Verify: `/usr/bin/time -p make test-all` -> PASS (`176 passed`, `real 10.90s`)
- [x] Post-refactor `make test-e2e` passes.
  - Verify: `/usr/bin/time -p make test-e2e` -> PASS (`8 passed`, `real 3.45s`)
- [x] Critical workflow cluster passes in forward and reverse test-file order.
  - Verify:
    - `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_literature_grounding.py tests/e2e/workflows/test_code_replication_workflow.py; done` -> PASS (`9 passed` each run)
    - `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_code_replication_workflow.py tests/e2e/workflows/test_literature_grounding.py; done` -> PASS (`9 passed` each run)
- [x] Data-contract suites pass across repeated reruns.
  - Verify:
    - `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/data_contracts; done` -> PASS (`6 passed` each run)
    - `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/data_contracts; done` -> PASS (`3 passed` each run)
    - `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/data_contracts; done` -> PASS (`1 passed` each run)
- [x] Guarded full-suite still passes after workflow exception-handling hardening.
  - Verify: `make check-stubs` -> PASS, `make PYTHON=python3 test-all-guarded` -> PASS (`41 unit`, `176 integration`)

## Not now

- [x] Split large integration modules (`tests/integration/core_api/test_claims.py`, `tests/integration/worker/test_sandbox_execution.py`) into smaller flow files.
  - Completed 2026-02-09 with module-level splits:
    - `tests/integration/core_api/test_claims/conftest.py`
    - `tests/integration/core_api/test_claims/test_claim_create.py`
    - `tests/integration/core_api/test_claims/test_claim_evidence.py`
    - `tests/integration/core_api/test_claims/test_claim_list.py`
    - `tests/integration/worker/test_sandbox_execution/test_sandbox_activity.py`
    - `tests/integration/worker/test_sandbox_execution/test_sandbox_endpoint.py`
  - Verify: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/core_api/test_claims tests/integration/worker/test_sandbox_execution` -> PASS (`13 passed`)
- [x] Add automated infra readiness preflight helper for Postgres/Temporal startup race handling.
  - Completed 2026-02-09 via `scripts/preflight_temporal.sh` + `scripts/run_test_all_with_temporal_guard.sh` and CI `cmd-12-integration` guarded path.
- [x] Expand unit-level coverage depth for worker modules beyond lifecycle bootstrap tests.
  - Completed 2026-02-09 by adding `tests/unit/worker/test_phase_machine.py` with transition-rule and activity behavior unit coverage.
  - Verify: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/worker/test_phase_machine.py` -> PASS (`10 passed`)
  - Verify: `make test-unit` -> PASS (`28 passed`)
