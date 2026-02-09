# Checklist: Plan (Prompt-01 PRD -> Acceptance Criteria)

Date: 2026-02-09  
Prompt packet: `prompt-01-prd-acceptance-requirements`  
Objective anchor: `Docs/manifest/00_overview.md#Core Objective`

## Now (this packet)

- [x] Produce a PRD with explicit scope, measurable outcomes, and requirement mapping.
  - AC: `Docs/implementation/reports/prd.md` exists with all required prompt-01 sections.
  - Verify: `rg -n "^## Problem statement|^## Users and jobs-to-be-done|^## In-scope workflows|^## Out-of-scope / non-goals|^## Success metrics|^## Requirements \\(functional \\+ non-functional\\)|^## Risks and assumptions|^## Acceptance criteria mapping|^## Open questions / TODOs" Docs/implementation/reports/prd.md`
  - Files: `Docs/implementation/reports/prd.md`
  - Docs: `Docs/implementation/reports/prd.md`
  - Alternatives: N/A

- [x] Keep objective docs consistent with the PRD framing.
  - AC: overview includes `Core Objective`, `Target Users`, and `Key Workflows` sections aligned to PRD scope.
  - Verify: `rg -n "^## Core Objective|^## Target Users|^## Key Workflows" Docs/manifest/00_overview.md`
  - Files: `Docs/manifest/00_overview.md`
  - Docs: `Docs/manifest/00_overview.md`, `Docs/implementation/reports/prd.md`
  - Alternatives: N/A

- [x] Convert requirements into observable pass/fail acceptance criteria.
  - AC: this plan contains checklist entries with `AC`, `Verify`, `Files`, and `Docs` fields tied to PRD criteria.
  - Verify: `rg -n "AC:|Verify:|Files:|Docs:" Docs/implementation/checklists/01_plan.md`
  - Files: `Docs/implementation/checklists/01_plan.md`
  - Docs: `Docs/implementation/checklists/01_plan.md`
  - Alternatives: N/A

## Acceptance Criteria Execution Plan

- [x] AC-02 Authority boundary remains orchestrator-only for phase/finalization mutations.
  - AC: agent-path requests cannot directly mutate `workspace.phase` or finalize drafts without gate enforcement.
  - Verify: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/worker/test_phase_machine.py tests/integration/core_api/test_drafts.py`
  - Files: `apps/core-api/phase_routes.py`, `apps/core-api/draft_routes.py`, `apps/worker/phase_machine.py`, `tests/integration/worker/test_phase_machine.py`, `tests/integration/core_api/test_drafts.py`
  - Docs: `Docs/manifest/04_api_contracts.md`, `Docs/implementation/reports/prd.md`
  - Alternatives: N/A

- [x] AC-03 Evidence resolver behavior is deterministic for malformed/unsupported pointers.
  - AC: resolver emits explicit deterministic error codes for malformed repo/log/pdf locations.
  - Verify: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/core_api/test_evidence_resolver.py`
  - Files: `apps/core-api/evidence_resolver.py`, `tests/integration/core_api/test_evidence_resolver.py`
  - Docs: `Docs/manifest/04_api_contracts.md`, `Docs/implementation/reports/prd.md`
  - Alternatives: N/A

- [x] AC-04 Artifact version immutability remains enforced.
  - AC: attempts to overwrite immutable artifact-version content fail explicitly (409 path) and do not create version rows.
  - Verify: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/core_api/test_artifacts_exit.py`
  - Files: `apps/core-api/artifact_routes.py`, `tests/integration/core_api/test_artifacts_exit.py`
  - Docs: `Docs/manifest/05_data_model.md`, `Docs/implementation/reports/prd.md`
  - Alternatives: N/A

- [x] AC-05 Reliability gates remain executable and mapped.
  - AC: guarded integration, observability, and architecture-coherence commands are runnable and CI-mapped.
  - Verify: `make PYTHON=python3 test-all-guarded && make PYTHON=python3 check-observability-slos && make PYTHON=python3 check-architecture-coherence`
  - Files: `Makefile`, `.github/workflows/ci.yml`, `scripts/preflight_temporal.sh`, `scripts/check_artifact_freshness.py`, `scripts/check_architecture_coherence.py`
  - Docs: `Docs/manifest/09_runbook.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/reports/prd.md`
  - Alternatives: N/A

- [x] AC-06 Deterministic critical e2e path remains green.
  - AC: one stable critical flow is enforced by command and CI.
  - Verify: `make PYTHON=python3 test-e2e-critical`
  - Files: `tests/e2e/workflows/test_literature_grounding.py`, `Makefile`, `.github/workflows/ci.yml`
  - Docs: `Docs/manifest/11_ci.md`, `Docs/implementation/reports/prd.md`
  - Alternatives: N/A

- [x] AC-08 Objective metrics automation beyond command/manual review.
  - AC: objective success metrics (citation integrity and authority-boundary regression trends) are produced automatically in CI/report output.
  - Verify: `make PYTHON=python3 check-objective-metrics`
  - Files: `scripts/check_objective_metrics.py`, `Makefile`, `.github/workflows/ci.yml`, `tests/integration/worker/test_citation_checks.py`, `tests/integration/core_api/test_evidence_resolver.py`, `tests/integration/worker/test_phase_machine.py`, `tests/integration/core_api/test_drafts.py`
  - Docs: `Docs/manifest/07_observability.md`, `Docs/manifest/09_runbook.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/reports/prd.md`
  - Alternatives: N/A

## Next (open acceptance gaps)

- [x] AC-09 Objective metrics dashboard automation.
  - AC: objective-metrics JSON output is published as a durable CI artifact and summarized in an auto-updated dashboard/report page.
  - Verify: `make PYTHON=python3 check-objective-metrics` and `rg -n "Upload objective metrics artifacts|objective-metrics-report|objective_metrics_dashboard.md" .github/workflows/ci.yml`
  - Files: `.github/workflows/ci.yml`, `scripts/check_objective_metrics.py`, `Docs/implementation/reports/objective_metrics_latest.json`, `Docs/implementation/reports/objective_metrics_dashboard.md`
  - Docs: `Docs/manifest/07_observability.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/reports/prd.md`
  - Alternatives: N/A

- [x] AC-10 Objective metrics long-term trend history.
  - AC: trend history is retained across runs in a durable in-repo or external store with queryable timeline views.
  - Verify: `make PYTHON=python3 check-objective-metrics` and `rg -n "objective_metrics_history.jsonl|objective_metrics_timeline.md" scripts/check_objective_metrics.py .github/workflows/ci.yml`
  - Files: `scripts/check_objective_metrics.py`, `.github/workflows/ci.yml`, `Docs/implementation/reports/objective_metrics_history.jsonl`, `Docs/implementation/reports/objective_metrics_timeline.md`
  - Docs: `Docs/manifest/07_observability.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/reports/prd.md`
  - Alternatives: N/A

- [x] AC-11 Observability snapshot synthesis automation.
  - AC: observability signal synthesis (artifact freshness/provenance + objective metrics) is auto-generated as JSON/dashboard and published as CI artifacts.
  - Verify: `make PYTHON=python3 check-observability-snapshot` and `rg -n "CMD-32|observability-snapshot-report|observability_snapshot_dashboard.md" Docs/manifest/09_runbook.md Docs/manifest/11_ci.md .github/workflows/ci.yml`
  - Files: `scripts/check_observability_snapshot.py`, `Makefile`, `.github/workflows/ci.yml`, `Docs/implementation/reports/observability_snapshot_latest.json`, `Docs/implementation/reports/observability_snapshot_dashboard.md`
  - Docs: `Docs/manifest/07_observability.md`, `Docs/manifest/09_runbook.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/reports/prd.md`
  - Alternatives: N/A

## Not now

- [x] Cross-browser UI smoke matrix in CI (Chromium-only smoke gap closed).
  - AC: add deterministic WebKit/Firefox smoke coverage with clear flake budget and ownership.
  - Verify: `AGORA_CORE_API_URL=http://localhost:8000 AGORA_WEB_BASE_URL=http://localhost:3100 npm --prefix apps/web run smoke:artifact-viewer:matrix` and `rg -n "cmd-30-ui-smoke-cross-browser|matrix:|firefox|webkit" .github/workflows/ci.yml apps/web/package.json`
  - Files: `apps/web/scripts/smoke_artifact_viewer.mjs`, `apps/web/package.json`, `.github/workflows/ci.yml`
  - Docs: `Docs/implementation/checklists/05_ui_verification.md`, `Docs/implementation/reports/prd.md`, `Docs/manifest/11_ci.md`
  - Alternatives: N/A

- [x] Mobile-width workspace tab verification automation.
  - AC: mobile viewport smoke validates all workspace tabs remain reachable and provenance drill-down flows stay healthy.
  - Verify: `AGORA_CORE_API_URL=http://localhost:8000 AGORA_WEB_BASE_URL=http://localhost:3100 npm --prefix apps/web run smoke:artifact-viewer:mobile` and `rg -n "cmd-31-ui-smoke-mobile|AGORA_SMOKE_VIEWPORT|smoke:artifact-viewer:mobile" .github/workflows/ci.yml apps/web/scripts/smoke_artifact_viewer.mjs apps/web/package.json`
  - Files: `apps/web/scripts/smoke_artifact_viewer.mjs`, `apps/web/package.json`, `.github/workflows/ci.yml`
  - Docs: `Docs/implementation/checklists/05_ui_verification.md`, `Docs/implementation/reports/ui_verification_final_report.md`, `Docs/manifest/11_ci.md`
  - Alternatives: N/A
