# Checklist: Test Stabilization

Checked boxes imply the verification commands were run and relevant notes were captured in `Docs/implementation/03_worklog.md`.

## Bet Tracking (2026-02-09 Post-DIR07 Revalidation Packet)

- [x] Appetite set (`medium`) for this rerun packet.
  - Now: prove the suite remains green after DIR-07 UI smoke changes and capture explicit triage for infra-only failures.
  - Not now (at that checkpoint): warning-volume cleanup (`datetime.utcnow()` / Pydantic `.dict()` deprecations), CI matrix expansion.
  - Follow-up: warning-volume cleanup completed later in the 2026-02-09 warning-noise stabilization packet below.

## Bet Tracking (2026-02-09 Warning-Noise Stabilization Packet)

- [x] Appetite set (`small`) for this rerun packet.
  - Now: remove high-frequency deprecation noise from first-party code paths to improve test signal quality.
  - Not now: third-party library deprecation warnings (`botocore`, `sqlalchemy`, `reportlab`, CPython importlib warning families).

## Bet Tracking (2026-02-09 Prompt-09 Ordering/Contract Probe Packet)

- [x] Appetite set (`small`) for this follow-through packet.
  - Now: close remaining stabilization uncertainty around hidden ordering and active flaky assertions in critical workflow and data-contract clusters.
  - Not now: broad randomized full-suite order permutation infrastructure (can be introduced later if flake signals return).

## Phase 0: Identify Test Interface

- [x] Map test runner + CI entrypoints and environment needs.
  - AC: command map exists; markers documented; CI mapping documented.
  - Verify: read `pytest.ini`, `Makefile`, `.github/workflows/*`.
  - Files: `Docs/manifest/10_testing.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/00_status.md`

## Phase 1: Establish Baseline Signal

- [x] Run unit suite once (baseline).
  - AC: unit suite green.
  - Verify: `make test-unit`
  - Reruns: later in Phase 5 (3x total).

- [x] Run unit data contract tests once (baseline).
  - AC: `tests/unit/data_contracts` green.
  - Verify: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/data_contracts`
  - Reruns: later in Phase 5 (3x total).

- [x] Run integration suite once (baseline) in intended environment.
  - AC: integration suite green OR explicit documented skips with markers/reasons.
  - Verify: `make test-integration`

- [x] Run e2e suite once (baseline) for critical flows.
  - AC: e2e suite green OR explicit gating behind opt-in markers with documented env needs.
  - Verify: `make test-e2e`

## Phase 2-3: Triage + Debug Loop

- [x] Transient integration infra failure triaged in 2026-02-09 rerun.
  - AC: initial failure was isolated to Temporal container startup instability; post-recovery integration/e2e/unit/contract baselines all green.
  - Verify: see run evidence in `Docs/implementation/reports/test_stabilization_final_report.md` (2026-02-09 revalidation section).

- [x] Bucket A fixes: test infrastructure (fixtures/imports/markers/nondeterminism/cleanup).
  - AC: warning-noise cluster from first-party code reduced without weakening behavior.
  - Verify:
    - `for i in 1 2 3; do make test-unit; done` -> PASS (3/3)
    - `for i in 1 2 3 4 5; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/core_api/test_jwt_utils.py tests/unit/worker/test_phase_machine.py; done` -> PASS (5/5)
    - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/core_api/test_artifacts_exit.py tests/integration/core_api/test_logs_events.py tests/integration/core_api/test_drafts.py tests/integration/core_api/test_critiques.py tests/integration/core_api/test_claims tests/integration/worker/test_pdf_ingestion.py tests/integration/worker/test_repo_ingestion.py tests/integration/worker/test_sandbox_execution` -> PASS (`56 passed`)
    - `make PYTHON=python3 test-all-guarded` -> PASS (`28 unit`, `176 integration`)

- [x] Bucket B fixes: data contract violations (ranges/missingness/enums/shape).
  - AC: hard bounds never violated; soft bounds justified and documented.
  - Verify:
    - `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/data_contracts; done` -> PASS (`6 passed` each run)
    - `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/data_contracts; done` -> PASS (`3 passed` each run)
    - `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/data_contracts; done` -> PASS (`1 passed` each run)

- [x] Bucket C fixes: behavioral mismatches (product bug/spec mismatch).
  - AC: workflow failure paths persist explicit terminal states in both `workflow_runs` and `activity_runs` (no stranded `running` records on workflow exceptions).
  - Verify:
    - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_literature_grounding.py::test_literature_grounding_workflow__missing_pdf_version__marks_workflow_and_activity_failed tests/e2e/workflows/test_code_replication_workflow.py::test_code_replication_workflow__invalid_repo_url__records_failed_activity_and_workflow` -> PASS (`2 passed`)
    - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_literature_grounding.py tests/e2e/workflows/test_code_replication_workflow.py` -> PASS (`9 passed`)

- [x] Bucket D fixes: brittle/over-specified tests.
  - AC: tests assert stable behavior; failures actionable.
  - Verify:
    - `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_literature_grounding.py tests/e2e/workflows/test_code_replication_workflow.py; done` -> PASS (`9 passed` each run)
    - `for i in 1 2 3; do PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_code_replication_workflow.py tests/e2e/workflows/test_literature_grounding.py; done` -> PASS (`9 passed` each run)
    - `for i in 1 2 3; do make test-e2e; done` -> PASS (`10 passed` each run)

## Phase 4: CI + Guardrails

- [x] Add CI guardrail: PRs that change tests/CI/runtime must update status + checklist docs.
  - AC: CI fails if guardrail violated; docs explain policy.
  - Verify: update `.github/workflows/ci.yml` and test locally (best-effort).
  - Docs: `Docs/manifest/11_ci.md`

## Phase 5: Final Verification (No Flakes)

- [x] Unit suite green 3x.
  - Verify: `make test-unit` (2026-02-09, baseline + 3 reruns)

- [x] Unit data contracts green 3x.
  - Verify: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/data_contracts` (2026-02-09, baseline + 3 reruns)

- [x] Integration suite green (or intended skips documented).
  - Verify: `make test-integration` (2026-02-09 baseline failed once due Temporal unavailable, then PASS after `docker start agora-temporal` + targeted workflow rerun)

- [x] E2E suite green (or gated/opt-in documented).
  - Verify: `make test-e2e` (2026-02-09)

- [x] UI smoke remains green after stabilization reruns.
  - Verify: `npm --prefix apps/web run smoke:artifact-viewer` (2026-02-09)

## Phase 6: Final Report

- [x] Write final stabilization report.
  - AC: report includes failures/root causes/fixes/contracts/how-to-run/gated tests.
  - File: `Docs/implementation/reports/test_stabilization_final_report.md`
