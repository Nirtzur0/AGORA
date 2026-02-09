# Test Architecture Plan

Date: 2026-02-09
Prompt packet: `prompt-09-tests-refactor-suite`

## Proposed folder tree

```text
tests/
  unit/
    core_api/
    worker/
    data_contracts/
  integration/
    core_api/
    worker/
    storage/
    db/
    external/
    data_contracts/
  e2e/
    workflows/
    data_contracts/
  helpers/
    assertions.py
    factories.py
    git_repo.py        # new in this packet
    http.py
  conftest.py
```

## Module responsibilities

- `tests/unit/`
  - belongs: pure logic and narrow module contracts.
  - never: real DB/storage/Temporal orchestration.
  - markers: `unit`.
- `tests/integration/`
  - belongs: DB/storage/API/worker boundary checks with real local dependencies.
  - never: browser/UI-driven end-to-end checks.
  - markers: `integration`, plus `postgres`/`minio`/`external` as needed.
- `tests/e2e/`
  - belongs: minimal critical path scenario tests that cross route/activity/workflow boundaries.
  - never: exhaustive permutation testing.
  - markers: `e2e`, optionally `slow`.
- `tests/helpers/`
  - belongs: small, reusable test-only utilities (assertions, fixtures/factories, deterministic repo builders).
  - never: ad-hoc mini-framework abstractions.

## Old -> New mapping table

| Old path | New path | Change type | Reason |
|---|---|---|---|
| repeated inline git init/commit blocks in `tests/e2e/workflows/test_code_replication_workflow.py` | `tests/helpers/git_repo.py` helper + imports in existing file | extraction | remove duplication and centralize deterministic git fixture setup |
| repeated inline git init/commit blocks in `tests/integration/worker/test_repo_ingestion.py` | `tests/helpers/git_repo.py` helper + simplified `repo_fixture` | extraction | keep repo fixture behavior while reducing maintenance cost |
| `tests/e2e/workflows/test_code_replication_workflow.py` monolithic Arrange sections | same file with local helper functions and clearer AAA sequencing | internal refactor | improve readability without changing behavior |
| `tests/integration/core_api/test_claims.py` | `tests/integration/core_api/test_claims/{conftest.py,test_claim_create.py,test_claim_evidence.py,test_claim_list.py}` | split | reduce monolithic integration module size and align one-flow-per-file |
| `tests/integration/worker/test_sandbox_execution.py` | `tests/integration/worker/test_sandbox_execution/{test_sandbox_activity.py,test_sandbox_endpoint.py}` | split | separate activity behavior checks from API endpoint contract checks |
| worker unit coverage concentrated in `tests/unit/worker/test_main_runtime_deps.py` | `tests/unit/worker/test_phase_machine.py` | add | deepen worker unit signal beyond lifecycle bootstrap helpers |

## Fixture strategy

- Global fixtures remain in `tests/conftest.py` (DB session wrapper, storage wrapper, test client).
- Feature-local fixtures stay near usage (`repo_fixture`, e2e workflow setup fixtures).
- Shared builders:
  - keep using `tests/helpers/factories.py` for workspace/agent/artifact seeds where useful.
  - add `tests/helpers/git_repo.py` for deterministic local git repo creation.
- Cleanup:
  - temporary repos via context-managed helper with guaranteed teardown,
  - DB remains transaction-scoped via `db_session` nested transaction pattern,
  - object storage cleanup remains inside `test_storage` wrapper.

## Dependency strategy

- Real dependency boundaries (integration/e2e): Postgres + MinIO + Temporal where required.
- Unit tests stay dependency-light and avoid container requirements.
- Determinism:
  - no network access in helper-generated repos,
  - fixed git user config in helper,
  - no sleeps added in refactor.

## Test pyramid + selection policy

- Target ratio: majority unit + integration; minimal e2e.
- Must-have e2e: literature grounding and code replication critical flows.
- Selection commands (source: `Makefile`, `pytest.ini`):
  - unit: `make test-unit`
  - integration: `make test-integration`
  - e2e: `make test-e2e`
  - full CI-equivalent: `make test-all`
  - active cluster slice: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_code_replication_workflow.py tests/integration/worker/test_repo_ingestion.py`

## Coverage goals

- Core flow must-cover areas:
  - workflow-run persistence and artifact outputs,
  - citation coverage/resolution pass and fail paths,
  - deterministic evidence resolver edge cases,
  - authority/finalization gate enforcement.
- Per-feature minimum:
  - happy path + representative failure path,
  - contract checks for key persisted fields/status domains,
  - integration check for any DB/storage boundary interaction.

## Small-commit implementation strategy

- [x] Commit batch 1 (this packet): add helper scaffolding + test refactor in one active cluster (`git-repo-backed workflow tests`).
- [x] Commit batch 2: split additional large worker/core_api integration modules (`test_claims.py`, `test_sandbox_execution.py`).
- [x] Commit batch 3: add readiness-preflight helper for infra startup races (`scripts/preflight_temporal.sh`, `scripts/run_test_all_with_temporal_guard.sh`).
- [x] Commit batch 4: expand worker unit coverage depth with `phase_machine` behavior tests.
- [x] Commit batch 5: run ordering/flakiness probe for critical e2e flow files and repeated data-contract reruns; close open landscape flags with command evidence.

## Acceptance criteria for this packet

- [x] Shared deterministic git-repo helper exists and is reused by both target modules.
- [x] No production code behavior changes.
- [x] Target cluster tests pass after refactor.
- [x] Unit + CI-equivalent suite still pass after refactor.
- [x] Status/worklog/checklist docs reflect `Now` vs `Not now` with explicit verification commands.
- [x] Large integration modules are split by behavior boundary and validated with targeted + guarded suite runs.
- [x] Worker unit coverage expands beyond runtime bootstrap helpers and remains green in `make test-unit`.
- [x] Critical workflow tests are stable across forward/reverse file-order execution and repeated e2e/data-contract reruns.
