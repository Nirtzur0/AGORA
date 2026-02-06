# Checklist: Test Stabilization

Checked boxes imply the verification commands were run and relevant notes were captured in `docs/implementation/03_worklog.md`.

## Phase 0: Identify Test Interface

- [x] Map test runner + CI entrypoints and environment needs.
  - AC: command map exists; markers documented; CI mapping documented.
  - Verify: read `pytest.ini`, `Makefile`, `.github/workflows/*`.
  - Files: `docs/manifest/10_testing.md`, `docs/manifest/11_ci.md`, `docs/implementation/00_status.md`

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

- [ ] Bucket A fixes: test infrastructure (fixtures/imports/markers/nondeterminism/cleanup).
  - AC: failures eliminated without weakening behavior.
  - Verify: rerun affected tests 5x; rerun impacted suites.

- [ ] Bucket B fixes: data contract violations (ranges/missingness/enums/shape).
  - AC: hard bounds never violated; soft bounds justified and documented.
  - Verify: rerun contract suites 3x; rerun impacted suites.

- [ ] Bucket C fixes: behavioral mismatches (product bug/spec mismatch).
  - AC: fix is correct per spec; tests prove it.
  - Verify: rerun failing test 5x; rerun impacted suite.

- [ ] Bucket D fixes: brittle/over-specified tests.
  - AC: tests assert stable behavior; failures actionable.
  - Verify: rerun rewritten tests 5x; rerun impacted suite.

## Phase 4: CI + Guardrails

- [x] Add CI guardrail: PRs that change tests/CI/runtime must update status + checklist docs.
  - AC: CI fails if guardrail violated; docs explain policy.
  - Verify: update `.github/workflows/ci.yml` and test locally (best-effort).
  - Docs: `docs/manifest/11_ci.md`

## Phase 5: Final Verification (No Flakes)

- [x] Unit suite green 3x.
  - Verify: `make test-unit` (3 runs)

- [x] Unit data contracts green 3x.
  - Verify: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/data_contracts` (3 runs)

- [x] Integration suite green (or intended skips documented).
  - Verify: `make test-integration`

- [x] E2E suite green (or gated/opt-in documented).
  - Verify: `make test-e2e`

## Phase 6: Final Report

- [x] Write final stabilization report.
  - AC: report includes failures/root causes/fixes/contracts/how-to-run/gated tests.
  - File: `docs/implementation/reports/test_stabilization_final_report.md`
