# Test Landscape

Date: 2026-02-09
Prompt packet: `prompt-09-tests-refactor-suite`

## Test frameworks and conventions

- Runner: `pytest` (`pytest.ini`).
- Plugin behavior: global plugin autoload disabled by default via `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`; async support loaded explicitly via `-p pytest_asyncio.plugin` (`Makefile`, `tests/conftest.py`).
- Markers: strict marker mode with repo-defined markers (`unit`, `integration`, `e2e`, `slow`, `docker`, `postgres`, `minio`, `external`, `asyncio`) in `pytest.ini`.
- CI execution (GitHub Actions):
  - `cmd-11-fast-checks` -> `make test`
  - `cmd-12-integration` -> `make test-all`
  - `smoke-test` -> compose boot + `/health` probe
  - Source: `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`.
- Naming conventions (current): mostly `test_<behavior>__<condition>__<expected>` and category folders under `tests/unit|integration|e2e`.

## Baseline measurements

Command source-path evidence:
- test entrypoints: `Makefile`
- marker policy: `pytest.ini`
- CI command mapping: `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`

Commands run (2026-02-09):
- `/usr/bin/time -p make test-unit`
  - Result: `18 passed`
  - Wall clock: `real 0.94s`
- `/usr/bin/time -p make test-all`
  - Result: `176 passed`
  - Wall clock: `real 10.55s`
- `/usr/bin/time -p make test-e2e`
  - Result: `8 passed`
  - Wall clock: `real 2.58s`
- `/usr/bin/time -p sh -c 'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_code_replication_workflow.py tests/integration/worker/test_repo_ingestion.py'`
  - Result: `8 passed`
  - Wall clock: `real 3.10s`

Coverage baseline:
- Coverage tooling exists (`pytest-cov` present in `tests/requirements.txt` and `apps/core-api/requirements-dev.txt`).
- Command run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -p pytest_cov --cov=apps/core-api --cov=apps/worker --cov-report=term-missing -q tests/unit`
- Result: `18 passed`, reported aggregate coverage `4%` across all app modules.
- Interpretation: current unit coverage is concentrated in a small subset (`jwt_utils`, worker runtime deps); most coverage signal comes from integration/e2e rather than unit-level module coverage.

## Current test categories

- Unit tests:
  - `tests/unit/core_api/*`
  - `tests/unit/worker/*`
  - `tests/unit/data_contracts/*`
- Integration tests:
  - `tests/integration/core_api/*`
  - `tests/integration/worker/*`
  - `tests/integration/storage/*`
  - `tests/integration/db/*`
  - `tests/integration/external/*`
  - `tests/integration/data_contracts/*`
- E2E tests:
  - `tests/e2e/workflows/*`
  - `tests/e2e/data_contracts/*`
- Contract/API tests:
  - unit contracts: `tests/unit/data_contracts/*`
  - integration contracts: `tests/integration/data_contracts/*`
  - e2e contract sanity: `tests/e2e/data_contracts/test_end_to_end_output_sanity.py`
- Slow tests: primarily e2e (`slow` marker present in e2e contract sanity).
- Property/perf tests: none detected.

## Inventory of test files

### Core API behavior and authority boundaries (`tests/integration/core_api`)

- Targets: auth, RBAC, workspaces, artifacts, claims, drafts/finalization, evidence resolver, logs/events.
- Production modules touched: `apps/core-api/*_routes.py`, `apps/core-api/evidence_resolver.py`, `apps/core-api/rbac.py`, `apps/core-api/jwt_utils.py`.
- Type: integration.
- Health: ✅ good (high scenario coverage, deterministic failures).

### Worker activity/workflow boundaries (`tests/integration/worker`)

- Targets: pdf ingestion, repo ingestion, sandbox execution, citation checks, phase machine, workflows, search indexing.
- Production modules touched: `apps/worker/pdf_ingest.py`, `apps/worker/repo_ingest.py`, `apps/worker/sandbox_run.py`, `apps/worker/citation_check.py`, `apps/worker/phase_machine.py`, workflow modules.
- Type: integration.
- Health: ⚠️ mixed (good behavior coverage; setup duplication around temporary git repos).

### End-to-end critical flows (`tests/e2e/workflows`)

- Targets: literature grounding and code replication critical flow completion.
- Production modules touched: route handlers + worker workflows/activities + DB persistence + MinIO object storage.
- Type: e2e.
- Health: ⚠️ mixed (high-value coverage, but monolithic tests and duplicated repo/bootstrap logic reduce maintainability).

### Contract checks (`tests/unit/data_contracts`, `tests/integration/data_contracts`, `tests/e2e/data_contracts`)

- Targets: required fields, missingness, value ranges, allowed categories, uniqueness, persistence status domains.
- Production modules touched: resolver payload shape, persisted table contracts (`rule_checks`, `artifact_versions`), final e2e rule-check status sanity.
- Type: unit/integration/e2e contract tests.
- Health: ✅ good (high-signal assertions via `tests/helpers/assertions.py`).

### DB/storage/external surfaces

- `tests/integration/db/test_db_migrations.py` -> DB schema constraints and indexes.
- `tests/integration/storage/test_storage.py` -> storage URI rules, immutability, roundtrip behavior.
- `tests/integration/external/test_moltbook_adapter.py` -> adapter API/health behavior.
- Health: ✅ good (boundary-focused, explicit assertions).

## Core flows

### Flow A: Workspace and authority lifecycle

- Entry points: workspace/join/phase/finalization routes in `apps/core-api/workspace_routes.py`, `apps/core-api/phase_routes.py`, `apps/core-api/draft_routes.py`.
- Invariants:
  - only orchestrator/system paths can mutate phase/finalization authority,
  - gate outcomes persist to `rule_checks` and `logs`.
- Failure modes:
  - unauthorized token, insufficient role/reputation,
  - invalid phase transition,
  - finalization gate fail/block.
- External dependencies: Postgres.

### Flow B: Artifact ingestion and evidence resolution

- Entry points: request routes + worker activities (`pdf_ingest`, `repo_ingest`, `sandbox_run`) + resolver (`evidence_resolver.py`).
- Invariants:
  - artifact versions immutable,
  - evidence pointers deterministic and version-pinned,
  - resolver errors deterministic.
- Failure modes:
  - malformed location grammars,
  - missing artifacts/paths/ranges,
  - ingest parse failures.
- External dependencies: Postgres, MinIO.

### Flow C: Draft citation integrity

- Entry points: draft routes + rulecheck routes + `apps/worker/citation_check.py`.
- Invariants:
  - citation coverage/resolution checks persisted,
  - unresolved citations block finalization.
- Failure modes:
  - missing claim citations,
  - unresolvable locations,
  - gate persistence failures.
- External dependencies: Postgres, MinIO.

### Flow D: End-to-end workflow orchestration

- Entry points: worker workflow modules (`literature_grounding_workflow.py`, `code_replication_workflow.py`).
- Invariants:
  - workflow/activity runs persisted,
  - downstream tasks created for required review actions.
- Failure modes:
  - workflow infra startup instability,
  - activity runtime failures (script errors, parsing failures).
- External dependencies: Postgres, MinIO, Temporal.

## Current test suite issues

- [x] Duplication: temporary git repo bootstrap is reimplemented in multiple test modules (`tests/e2e/workflows/test_code_replication_workflow.py`, `tests/integration/worker/test_repo_ingestion.py`).
- [x] Monolithic e2e functions: code replication e2e tests have repeated Arrange blocks with low reuse.
- [x] Infra startup race sensitivity: immediate integration/e2e runs after `make up` can race DB/Temporal readiness.
- [x] Hidden test ordering dependency probe completed for the critical workflow cluster; no ordering-coupled failures observed.
  - Verification:
    - `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_literature_grounding.py tests/e2e/workflows/test_code_replication_workflow.py; done` -> PASS (`9 passed` per run)
    - `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_code_replication_workflow.py tests/e2e/workflows/test_literature_grounding.py; done` -> PASS (`9 passed` per run)
- [x] Active flaky assertion probe completed for critical e2e + contract clusters; no flake reproduced in repeated runs.
  - Verification:
    - `for i in 1 2 3; do make test-e2e; done` -> PASS (`10 passed` per run)
    - `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/data_contracts; done` -> PASS (`6 passed` per run)
    - `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/data_contracts; done` -> PASS (`3 passed` per run)
    - `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/data_contracts; done` -> PASS (`1 passed` per run)

## Risk areas / missing coverage

- [x] Missing shared helper boundary for git-backed test fixtures (maintainability risk).
- [x] Temporal readiness preflight is not consistently enforced before test start (operational risk, not product-behavior risk).
- [x] Critical workflow failure-path coverage added for workflow-level error persistence paths.
  - Evidence: added e2e failure-path tests:
    - `tests/e2e/workflows/test_literature_grounding.py::test_literature_grounding_workflow__missing_pdf_version__marks_workflow_and_activity_failed`
    - `tests/e2e/workflows/test_code_replication_workflow.py::test_code_replication_workflow__invalid_repo_url__records_failed_activity_and_workflow`
  - Verification: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_literature_grounding.py tests/e2e/workflows/test_code_replication_workflow.py` -> PASS (`9 passed`, 2026-02-09)
- [x] Contract ownership/change-policy table added to testing manifest in this packet (`Docs/manifest/10_testing.md`).

## Refactor opportunities

- [x] Extract git repository setup/commit logic into a shared helper module under `tests/helpers/`.
- [x] Refactor code-replication e2e tests to explicit Arrange/Act/Assert blocks with small helper functions.
- [x] Reuse existing factories/assertions (`tests/helpers/factories.py`, `tests/helpers/assertions.py`) where possible instead of in-test SQL duplication.
- [x] Split additional large integration modules into sub-flow files (`tests/integration/core_api/test_claims/`, `tests/integration/worker/test_sandbox_execution/`) and validate with targeted suite pass (`13 passed`, 2026-02-09).
- [x] Expand worker unit-depth coverage beyond lifecycle bootstrap tests (`tests/unit/worker/test_phase_machine.py`, `10 passed`, 2026-02-09).
