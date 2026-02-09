# Checklist: Milestones

This checklist maps AGORA work into bounded milestones after prompt-02 shaping.

## M0 - Shape Baseline and Planning (Current)

- [x] Establish docs baseline and objective anchor.
  - AC: prompt-02 required planning docs exist in `Docs/`.
  - Verify: `find Docs/manifest Docs/implementation -maxdepth 3 -type f | sort`
  - Files: `Docs/.prompt_system.yml`, `Docs/manifest/*`, `Docs/implementation/*`

- [x] Create assumptions register and resolve/accept high-impact assumptions.
  - AC: no `high` assumptions remain `open`.
  - Verify: `rg -n "\| high \| open \|" Docs/implementation/reports/assumptions_register.md`
  - Files: `Docs/implementation/reports/assumptions_register.md`

## M1 - Core Authority and Gate Hardening

- [x] Add architecture coherence gate checklist and readiness verdict tracking.
  - AC: `Docs/implementation/checklists/00_architecture_coherence.md` exists and records `GO` / `GO_WITH_RISKS` for active architecture.
  - Verify: `test -f Docs/implementation/checklists/00_architecture_coherence.md && rg -n \"GO|GO_WITH_RISKS\" Docs/implementation/checklists/00_architecture_coherence.md` (2026-02-08)
  - Files: `Docs/implementation/checklists/00_architecture_coherence.md`, `Docs/implementation/00_status.md`

- [x] Add alignment review checklist for periodic objective drift checks.
  - AC: `Docs/implementation/checklists/07_alignment_review.md` exists and references `Docs/manifest/00_overview.md#Core Objective`.
  - Verify: `test -f Docs/implementation/checklists/07_alignment_review.md && rg -n \"Core Objective\" Docs/implementation/checklists/07_alignment_review.md` (2026-02-08)
  - Files: `Docs/implementation/checklists/07_alignment_review.md`, `Docs/implementation/00_status.md`

- [x] Validate orchestrator-only phase transitions and finalization end-to-end.
  - AC: integration tests prove agent endpoints cannot directly mutate phase/finalization state.
  - Verify: `make test-integration` (PASS, 2026-02-08) and targeted endpoint regressions for agent-token rejection on phase/finalize routes.
  - Files: `apps/core-api/phase_routes.py`, `apps/core-api/draft_routes.py`, `tests/integration/worker/test_phase_machine.py`, `tests/integration/core_api/test_drafts.py`

- [x] Expand rule-check coverage for failure persistence (`activity_runs`, `rule_checks`, `logs`).
  - AC: failure-path tests assert explicit persisted outcomes.
  - Verify: `make test-integration` (PASS, 2026-02-08) + `tests/integration/core_api/test_drafts.py::test_draft_finalize__gate_failure__persists_rule_check_and_log` (PASS).
  - Files: `apps/core-api/draft_routes.py`, `apps/worker/citation_check.py`, `tests/integration/core_api/test_drafts.py`

- [x] Automate architecture coherence validation in CI.
  - AC: architecture coherence gate runs in CI and is reproducible locally via runbook command.
  - Verify: `make PYTHON=python3 check-architecture-coherence` (PASS, 2026-02-09) and `.github/workflows/ci.yml` `architecture-coherence` job mapping to `CMD-28`.
  - Files: `scripts/check_architecture_coherence.py`, `Makefile`, `.github/workflows/ci.yml`, `Docs/manifest/09_runbook.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/checklists/00_architecture_coherence.md`

## M2 - Artifact and Evidence Reliability

- [x] Strengthen evidence resolver edge-case handling.
  - AC: deterministic errors for malformed/unsupported `location` pointers.
  - Verify: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/core_api/test_evidence_resolver.py tests/integration/worker/test_repo_ingestion.py` (PASS), `make test-integration` (PASS) (2026-02-08).
  - Files: `apps/core-api/evidence_resolver.py`, `tests/integration/core_api/test_evidence_resolver.py`, `tests/integration/worker/test_repo_ingestion.py`

- [x] Verify immutable artifact version semantics across ingestion and retrieval paths.
  - AC: overwrite attempts fail deterministically and are tested.
  - Verify: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/core_api/test_artifacts_exit.py` (PASS), `make test-integration` (PASS) (2026-02-08).
  - Files: `apps/core-api/artifact_routes.py`, `tests/integration/core_api/test_artifacts_exit.py`

## M3 - UI Audit Surface and E2E Confidence

- [x] Cover critical UI workflows with stable E2E checks.
  - AC: key pages (projects/workspace/artifact view + provenance drill-down) pass deterministic browser smoke and e2e checks.
  - Verify: `make up` (PASS, 2026-02-08), `npm --prefix apps/web run smoke:artifact-viewer` (PASS, 2026-02-08), `make test-e2e` (PASS, 2026-02-08), `make down` (PASS, 2026-02-08).
  - Files: `apps/web/scripts/smoke_artifact_viewer.mjs`, `apps/web/src/*`, `Docs/implementation/checklists/05_ui_verification.md`, `Docs/implementation/reports/ui_verification_final_report.md`, `tests/e2e/*`

- [x] Add deterministic cross-browser UI smoke matrix in CI.
  - AC: CI executes the UI provenance smoke flow across `chromium`, `firefox`, and `webkit`.
  - Verify: local matrix command PASS (2026-02-09), CI mapping grep PASS (2026-02-09), and remote PR run `21812201997` passed `cmd-30-ui-smoke-cross-browser` for `chromium`/`firefox`/`webkit` (`https://github.com/Nirtzur0/AGORA/actions/runs/21812201997`).
  - Files: `apps/web/scripts/smoke_artifact_viewer.mjs`, `apps/web/package.json`, `.github/workflows/ci.yml`, `Docs/manifest/09_runbook.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/checklists/05_ui_verification.md`

- [x] Add deterministic mobile-width UI smoke gate for all workspace tabs.
  - AC: CI executes mobile viewport smoke and verifies all workspace tabs remain reachable with provenance drill-down intact.
  - Verify: local mobile smoke command PASS (2026-02-09), CI mapping grep PASS (2026-02-09), and remote PR run `21812201997` passed `cmd-31-ui-smoke-mobile` (`https://github.com/Nirtzur0/AGORA/actions/runs/21812201997/job/62926452874`).
  - Files: `apps/web/scripts/smoke_artifact_viewer.mjs`, `apps/web/package.json`, `.github/workflows/ci.yml`, `Docs/manifest/09_runbook.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/checklists/05_ui_verification.md`

- [x] Add optional Dash data explorer for report/artifact quality signals.
  - AC: a runnable Dash app provides overview/datasets/outputs/data-quality pages over AGORA report artifacts, with headless validation and test coverage.
  - Verify: `python3 -m dash_app.data.validation --repo-root . --output /tmp/agora-dash-validation.json` (PASS, 2026-02-09), `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/test_data_validation.py tests/test_loaders_smoke.py` (PASS, 2026-02-09), `python3 dash_app/app.py` + `curl -fsS http://127.0.0.1:8050/` (PASS, 2026-02-09).
  - Files: `dash_app/*`, `Docs/dash_data_explorer/*`, `tests/test_data_validation.py`, `tests/test_loaders_smoke.py`, `Docs/manifest/09_runbook.md`

## M4 - Release Discipline and CI Expansion

- [x] Expand CI to enforce unit + integration checks and keep command-ID mapping current.
  - AC: CI runs at least `CMD-11`/`CMD-12` equivalents and `Docs/manifest/11_ci.md` maps jobs to runbook command IDs.
  - Verify: inspect `.github/workflows/ci.yml`; local evidence `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test` (PASS), `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test-all` (PASS) (2026-02-08).
  - Files: `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`

- [x] Define release-readiness checklist and changelog policy.
  - AC: release criteria documented and linked from docs index.
  - Verify: docs review (`Docs/INDEX.md`, `CHANGELOG.md`, `Docs/reference/versioning_policy.md`, `Docs/implementation/checklists/06_release_readiness.md`) (2026-02-08)
  - Files: `CHANGELOG.md`, `Docs/reference/versioning_policy.md`, `Docs/implementation/checklists/06_release_readiness.md`, `Docs/INDEX.md`

- [x] Expand observability gate with metrics/SLO/alerts and debug playbook details.
  - AC: `Docs/manifest/07_observability.md` documents golden signals, SLI/SLO thresholds, and severity routing.
  - Verify: docs review + command map cross-links in `Docs/manifest/09_runbook.md` (`CMD-16`/`CMD-17`/`CMD-18`).
  - Files: `Docs/manifest/07_observability.md`, `Docs/manifest/09_runbook.md`

- [x] Add Temporal startup preflight/retry guard for integration gate reliability.
  - AC: integration gate waits for healthy Temporal and retries once on transient startup failures.
  - Verify: `make up` (PASS), `scripts/preflight_temporal.sh` (PASS), `make PYTHON=python3 test-all-guarded` (PASS), `make down` (PASS) (2026-02-09).
  - Files: `scripts/preflight_temporal.sh`, `scripts/run_test_all_with_temporal_guard.sh`, `Makefile`, `.github/workflows/ci.yml`, `Docs/manifest/09_runbook.md`

- [x] Add automated observability SLO gate checks in CI.
  - AC: CI runs command-backed SLO checks and fails on provenance/freshness breaches.
  - Verify: `make PYTHON=python3 check-observability-slos` (PASS, 2026-02-09); `.github/workflows/ci.yml` `observability-gate` job maps to `CMD-26`.
  - Files: `Makefile`, `.github/workflows/ci.yml`, `Docs/manifest/07_observability.md`, `Docs/manifest/11_ci.md`

- [x] Add automated objective-metrics gate checks in CI.
  - AC: CI runs command-backed objective metrics (citation integrity + authority boundary) and fails on regression.
  - Verify: `make up` (PASS, 2026-02-09), `scripts/preflight_temporal.sh` (PASS, 2026-02-09), `make PYTHON=python3 check-objective-metrics` (PASS, 2026-02-09), `make down` (PASS, 2026-02-09); `.github/workflows/ci.yml` `objective-metrics-gate` maps to `CMD-29`.
  - Files: `scripts/check_objective_metrics.py`, `Makefile`, `.github/workflows/ci.yml`, `Docs/manifest/07_observability.md`, `Docs/manifest/09_runbook.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/reports/objective_metrics_latest.json`

- [x] Publish objective-metrics outputs as durable CI artifacts and dashboard summary.
  - AC: objective metrics job uploads JSON + dashboard outputs and writes dashboard summary to CI job summary.
  - Verify: `rg -n "Upload objective metrics artifacts|objective-metrics-report|objective_metrics_dashboard.md|GITHUB_STEP_SUMMARY" .github/workflows/ci.yml` (PASS, 2026-02-09) and `make PYTHON=python3 check-objective-metrics` (PASS, 2026-02-09).
  - Files: `.github/workflows/ci.yml`, `scripts/check_objective_metrics.py`, `Docs/implementation/reports/objective_metrics_latest.json`, `Docs/implementation/reports/objective_metrics_dashboard.md`, `Docs/manifest/11_ci.md`

- [x] Persist objective-metrics trend history and timeline outputs.
  - AC: objective metrics gate appends run history and regenerates a queryable timeline view across runs.
  - Verify: `make PYTHON=python3 check-objective-metrics` (PASS, 2026-02-09) and `rg -n "objective_metrics_history.jsonl|objective_metrics_timeline.md" scripts/check_objective_metrics.py .github/workflows/ci.yml` (PASS, 2026-02-09).
  - Files: `scripts/check_objective_metrics.py`, `.github/workflows/ci.yml`, `Docs/implementation/reports/objective_metrics_history.jsonl`, `Docs/implementation/reports/objective_metrics_timeline.md`, `Docs/manifest/11_ci.md`

- [x] Add observability snapshot synthesis and CI artifact publication.
  - AC: observability signal snapshot (artifact freshness/provenance + objective metrics) is generated per run and published as durable CI artifact output.
  - Verify: `make PYTHON=python3 check-observability-snapshot` (PASS, 2026-02-09) and `rg -n "CMD-32|observability-snapshot-report|observability_snapshot_dashboard.md" Docs/manifest/09_runbook.md Docs/manifest/11_ci.md .github/workflows/ci.yml` (PASS, 2026-02-09).
  - Files: `scripts/check_observability_snapshot.py`, `Makefile`, `.github/workflows/ci.yml`, `Docs/implementation/reports/observability_snapshot_latest.json`, `Docs/implementation/reports/observability_snapshot_dashboard.md`, `Docs/manifest/11_ci.md`

- [x] Add deterministic e2e critical-flow gate outside release-only runs.
  - AC: CI executes at least one stable e2e critical-flow check per PR cycle.
  - Verify: `make up` (PASS), `make PYTHON=python3 test-e2e-critical` (PASS), `make down` (PASS) (2026-02-09); `.github/workflows/ci.yml` includes `cmd-13-e2e-critical-flow`.
  - Files: `Makefile`, `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`, `tests/e2e/workflows/test_literature_grounding.py`

## M5 - Improvement Direction Bets (Prompt-14)

- [x] DIR-01: CI quality matrix + docs guardrail hardening packet.
  - AC: CI runs unit + integration jobs mapped to runbook command IDs, and docs guardrail checks the active implementation checklist for the packet.
  - Verify: local `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test` (PASS) and `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test-all` (PASS) with `.github/workflows/ci.yml` mapping updates (2026-02-08).
  - Files: `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`, `Docs/manifest/09_runbook.md`, `Docs/implementation/checklists/03_improvement_bets.md`
  - Prompt chain: `prompt-02` -> `prompt-10` -> `prompt-11` -> `prompt-03`

- [x] DIR-06: Release-readiness checklist execution on one release candidate.
  - AC: release checklist entries have command evidence (or explicit gated deferral rationale) and changelog/release workflow docs are synchronized.
  - Verify: `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test` (PASS), `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test-all` (PASS), `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test-e2e` (PASS) (2026-02-08).
  - Files: `Docs/implementation/checklists/06_release_readiness.md`, `Docs/reference/release_workflow.md`, `CHANGELOG.md`
  - Prompt chain: `prompt-11` -> `prompt-03`

- [x] DIR-02: Observability gate expansion (golden signals + SLI/SLO + severity routing).
  - AC: critical workflows list signal definitions, thresholds, and incident routing with runbook links.
  - Verify: docs review + command-map cross-link checks (`Docs/manifest/07_observability.md`, `Docs/manifest/09_runbook.md`, `Docs/manifest/11_ci.md`) (2026-02-08).
  - Files: `Docs/manifest/07_observability.md`, `Docs/manifest/09_runbook.md`, `Docs/manifest/11_ci.md`
  - Prompt chain: `prompt-02` -> `prompt-11` -> `prompt-03`

- [x] DIR-03: Orchestrator authority and failure-persistence regression pack.
  - AC: integration/e2e tests explicitly assert orchestrator-only phase/finalization authority and persisted failure outcomes.
  - Verify: `make test-integration` (PASS), `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/core_api/test_drafts.py tests/integration/worker/test_phase_machine.py` (PASS), `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/e2e/workflows/test_literature_grounding.py` (PASS).
  - Files: `apps/core-api/phase_routes.py`, `apps/core-api/draft_routes.py`, `apps/worker/citation_check.py`, `tests/integration/worker/test_phase_machine.py`, `tests/integration/core_api/test_drafts.py`, `tests/e2e/workflows/test_literature_grounding.py`
  - Prompt chain: `prompt-02` -> `prompt-09` -> `prompt-10` -> `prompt-03`

- [x] DIR-04: Worker dependency lifecycle hardening.
  - AC: placeholder dependency-injection comments are replaced by explicit lifecycle handling and doc updates.
  - Verify: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/worker/test_main_runtime_deps.py` (PASS), `make up` (PASS), `PYTHONPATH=packages/db:packages/shared-types:apps/worker python3 - <<'PY' ... wm._load_runtime_dependencies(); wm._validate_runtime_dependencies(deps) ... PY` (PASS), `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/worker/test_pdf_ingestion.py` (PASS), `make down` (PASS) (2026-02-08).
  - Files: `apps/worker/main.py`, `tests/unit/worker/test_main_runtime_deps.py`, `Docs/manifest/01_architecture.md`, `Docs/implementation/checklists/00_architecture_coherence.md`, `Docs/implementation/reports/architecture_coherence_report.md`
  - Prompt chain: `prompt-04` -> `prompt-02` -> `prompt-10`

- [x] DIR-05: Artifact -> feature alignment gate adoption.
  - AC: artifact-feature alignment checklist/report exists with verdict and milestone-mapped corrections/opportunities.
  - Verify: `test -f Docs/implementation/checklists/08_artifact_feature_alignment.md && test -f Docs/implementation/reports/artifact_feature_alignment.md && rg -n 'Verdict: .*ALIGNED_WITH_GAPS|AF-C01|AF-O01' Docs/implementation/reports/artifact_feature_alignment.md Docs/implementation/checklists/02_milestones.md` (PASS, 2026-02-08).
  - Files: `Docs/implementation/checklists/08_artifact_feature_alignment.md`, `Docs/implementation/reports/artifact_feature_alignment.md`, `Docs/implementation/checklists/02_milestones.md`, `Docs/implementation/00_status.md`, `Docs/implementation/03_worklog.md`
  - Prompt chain: `prompt-15` -> `prompt-03` -> `prompt-00`

## M6 - Artifact-Feature Alignment Follow-Through

- [x] AF-C01: External artifact registry is seeded with load-bearing sources and retrieval metadata.
  - AC: `Docs/artifacts/index.json` contains >=5 load-bearing artifacts with stable IDs, URL/permalink, and `retrieved_at`.
  - Verify: `test -f Docs/artifacts/index.json && rg -n '"id"|"url"|"retrieved_at"' Docs/artifacts/index.json && python3 packages/project-prompts/scripts/web_artifacts.py --repo-root . --store-root Docs/artifacts validate` (PASS, 2026-02-08).
  - Files: `Docs/artifacts/index.json`, `Docs/artifacts/README.md`, `Docs/implementation/reports/artifact_feature_alignment.md`
  - Prompt chain: `prompt-02` -> `prompt-11` -> `prompt-03`

- [x] AF-C02: Worker dependency lifecycle is deterministic at startup and documented.
  - AC: placeholder lifecycle comments are removed and replaced by explicit dependency lifecycle handling with smoke/integration evidence.
  - Verify: `make up` (PASS), `PYTHONPATH=packages/db:packages/shared-types:apps/worker python3 - <<'PY' ... wm._load_runtime_dependencies(); wm._validate_runtime_dependencies(deps) ... PY` (PASS), `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/worker/test_pdf_ingestion.py` (PASS), `make down` (PASS) (2026-02-08).
  - Files: `apps/worker/main.py`, worker bootstrap helpers, `Docs/manifest/01_architecture.md`, `Docs/manifest/09_runbook.md`
  - Prompt chain: `prompt-04` -> `prompt-02` -> `prompt-10`

- [x] AF-C03: M2 evidence/artifact reliability gaps are closed with deterministic edge-case tests.
  - AC: milestone M2 items are checked with reproducible failure-path tests for unsupported/malformed locations and immutability semantics.
  - Verify: `make test-unit` (PASS), `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/core_api/test_evidence_resolver.py tests/integration/core_api/test_artifacts_exit.py tests/integration/worker/test_repo_ingestion.py` (PASS), `make test-integration` (PASS) (2026-02-08).
  - Files: `apps/core-api/evidence_resolver.py`, `apps/core-api/artifact_routes.py`, `tests/integration/core_api/test_evidence_resolver.py`, `tests/integration/core_api/test_artifacts_exit.py`, `tests/integration/worker/test_repo_ingestion.py`
  - Prompt chain: `prompt-02` -> `prompt-09` -> `prompt-10` -> `prompt-03`

- [x] AF-C04: CI/docs guardrail enforces artifact-alignment freshness for reliability-critical changes.
  - AC: CI fails when reliability-critical changes omit alignment/status/worklog updates.
  - Verify: `rg -n "required_alignment|reliability_changes|test_repo_ingestion|Docs/artifacts" .github/workflows/ci.yml` (PASS, 2026-02-08) and `make test` (PASS, 2026-02-08).
  - Files: `.github/workflows/ci.yml`, docs guardrail logic, `Docs/implementation/checklists/08_artifact_feature_alignment.md`, `Docs/implementation/00_status.md`
  - Prompt chain: `prompt-02` -> `prompt-11` -> `prompt-03`

- [x] AF-O01: Release-readiness requires latest artifact-feature alignment verdict before sign-off.
  - AC: release checklist references latest alignment report/checklist and unresolved AF outcomes.
  - Verify: `rg -n "artifact[- ]feature alignment|08_artifact_feature_alignment|alignment verdict" Docs/implementation/checklists/06_release_readiness.md Docs/reference/release_workflow.md` (PASS, 2026-02-08).
  - Files: `Docs/implementation/checklists/06_release_readiness.md`, `Docs/reference/release_workflow.md`, `Docs/implementation/checklists/08_artifact_feature_alignment.md`
  - Prompt chain: `prompt-11` -> `prompt-03`

- [x] AF-O02: Audit UI exposes claim/citation provenance drill-down to artifact-version evidence metadata.
  - AC: UI flow supports deterministic navigation from claim/citation to evidence metadata and is covered by e2e checks.
  - Verify: `npm --prefix apps/web run build` (PASS, 2026-02-08), `make up` (PASS, 2026-02-08), `make test-e2e` (PASS, 2026-02-08), `make down` (PASS, 2026-02-08).
  - Files: `apps/web/src/components/EvidenceDrawer.jsx`, `apps/web/src/pages/WorkspacePage.jsx`, `apps/web/src/components/EvidenceDrawer.css`, `apps/web/src/pages/WorkspacePage.css`, `tests/e2e/*`
  - Prompt chain: `prompt-02` -> `prompt-06` -> `prompt-10`

- [x] AF-O03: Observability includes artifact freshness and provenance-coverage signals.
  - AC: observability docs define SLI/SLO + severity routing for stale/missing artifact metadata.
  - Verify: `python3 scripts/check_artifact_freshness.py --index Docs/artifacts/index.json --warn-age-days 75 --max-age-days 90` (PASS, 2026-02-08), docs review (`Docs/manifest/07_observability.md`, `Docs/manifest/09_runbook.md`), and `make test-integration` (PASS, 2026-02-08).
  - Files: `Docs/manifest/07_observability.md`, `Docs/manifest/09_runbook.md`, `scripts/check_artifact_freshness.py`
  - Prompt chain: `prompt-02` -> `prompt-11` -> `prompt-03`

## M7 - Alignment Follow-Through (Post Prompt-08)

- [x] AR-C01: Add CI automation for Dash data-quality checks.
  - AC: CI executes `CMD-37` + `CMD-38` (scheduled or non-blocking PR gate initially) and publishes validation report artifacts.
  - Verify: local Dash checks pass (2026-02-09) and remote evidence exists: PR run `21811670116`, job `cmd-37-38-dash-data-quality` PASS (`https://github.com/Nirtzur0/AGORA/actions/runs/21811670116/job/62924847427`) with `dash-data-quality-report` artifact publication.
  - Files: `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`, `Docs/manifest/09_runbook.md`, `dash_app/data/validation.py`, `tests/test_data_validation.py`, `tests/test_loaders_smoke.py`
  - Prompt chain: `prompt-14` -> `prompt-02` -> `prompt-03`

- [x] AR-C02: Add warning-budget guard for deterministic critical e2e flow.
  - AC: warning growth on `CMD-27` is bounded by an explicit budget/threshold and can fail checks when exceeded.
  - Verify: `make PYTHON=python3 test-e2e-critical` (PASS, 2026-02-09), `E2E_CRITICAL_WARNING_BUDGET=0 make PYTHON=python3 test-e2e-critical` (expected FAIL, 2026-02-09), and `rg -n "E2E_CRITICAL_WARNING_BUDGET=40|check_critical_e2e_warning_budget.py" .github/workflows/ci.yml Makefile Docs/manifest/11_ci.md Docs/manifest/10_testing.md` (PASS, 2026-02-09).
  - Files: `Makefile`, `.github/workflows/ci.yml`, `Docs/manifest/10_testing.md`, `Docs/manifest/11_ci.md`, `tests/e2e/workflows/test_literature_grounding.py`
  - Prompt chain: `prompt-09` -> `prompt-10` -> `prompt-03`

- [x] AR-C03: Add delta-based alignment freshness guard.
  - AC: each prompt-03 rerun records a concrete triggering delta and next non-redundant packet; redundant reruns are blocked by process/guardrail.
  - Verify: `rg -n "Triggering delta:|Recommended next non-redundant packet:" Docs/implementation/checklists/07_alignment_review.md` (PASS, 2026-02-09), `rg -n "triggering delta" Docs/implementation/00_status.md Docs/implementation/03_worklog.md` (PASS, 2026-02-09), and docs-guardrail CI now enforces these fields when alignment checklist changes.
  - Files: `Docs/implementation/checklists/07_alignment_review.md`, `Docs/implementation/00_status.md`, `Docs/implementation/03_worklog.md`, `Docs/manifest/03_decisions.md`
  - Prompt chain: `prompt-14` -> `prompt-03`

- [x] AR-C04: Add tag-triggered release automation path.
  - AC: CI/release workflow supports tag-triggered release validation/execution path with explicit command coverage mapping.
  - Verify: `rg -n "on:|tags: \\[ 'v\\*' \\]|workflow_dispatch|release-tag-gate" .github/workflows/ci.yml Docs/reference/release_workflow.md Docs/manifest/11_ci.md` (PASS, 2026-02-09), local dry-run command path passes (all PASS, 2026-02-09), and remote evidence pass exists: workflow dispatch run `21811670648`, job `release-tag-gate` (`https://github.com/Nirtzur0/AGORA/actions/runs/21811670648/job/62924827121`).
  - Files: `.github/workflows/ci.yml`, `Docs/reference/release_workflow.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/checklists/06_release_readiness.md`
  - Prompt chain: `prompt-14` -> `prompt-11` -> `prompt-02` -> `prompt-03`

- [x] AR-C05: Define and adopt full `CMD-13` suite promotion strategy.
  - AC: policy defines where/when full e2e suite runs (nightly/protected branch), ownership, and promotion criteria from critical-only coverage.
  - Verify: `rg -n "CMD-13|nightly|schedule|run_full_e2e|cmd-13-nightly-full-suite|release-tag-gate" .github/workflows/ci.yml Docs/manifest/10_testing.md Docs/manifest/11_ci.md Docs/implementation/checklists/06_release_readiness.md` (PASS, 2026-02-09), local `make PYTHON=python3 test-e2e` (PASS, 2026-02-09), and remote nightly evidence pass exists: workflow dispatch run `21811670648`, job `cmd-13-nightly-full-suite` (`https://github.com/Nirtzur0/AGORA/actions/runs/21811670648/job/62924827118`).
  - Files: `.github/workflows/ci.yml`, `Docs/manifest/10_testing.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/checklists/06_release_readiness.md`
  - Prompt chain: `prompt-14` -> `prompt-11` -> `prompt-02` -> `prompt-03`

## M8 - Post-M7 Evidence and Signal Hardening

- [x] AR-C06: Capture first remote pass evidence for `release-tag-gate`.
  - AC: one remote GitHub Actions run shows `release-tag-gate` passing with release gate artifacts uploaded.
  - Verify: workflow dispatch run `21811670648`, job `release-tag-gate` passed and uploaded release artifacts (`https://github.com/Nirtzur0/AGORA/actions/runs/21811670648/job/62924827121`); docs references present via `rg -n "21811670648|release-tag-gate|release-tag-gate-artifacts|actions/runs/21811670648" Docs/manifest/11_ci.md Docs/reference/release_workflow.md Docs/implementation/00_status.md Docs/implementation/03_worklog.md`.
  - Files: `Docs/manifest/11_ci.md`, `Docs/reference/release_workflow.md`, `Docs/implementation/00_status.md`, `Docs/implementation/03_worklog.md`
  - Prompt chain: `prompt-02` -> `prompt-11` -> `prompt-03`

- [x] AR-C07: Capture first remote pass evidence for `cmd-13-nightly-full-suite`.
  - AC: one remote GitHub Actions run shows `cmd-13-nightly-full-suite` passing.
  - Verify: workflow dispatch run `21811670648`, job `cmd-13-nightly-full-suite` passed (`https://github.com/Nirtzur0/AGORA/actions/runs/21811670648/job/62924827118`); docs references present via `rg -n "21811670648|cmd-13-nightly-full-suite|actions/runs/21811670648" Docs/manifest/11_ci.md Docs/reference/release_workflow.md Docs/implementation/00_status.md Docs/implementation/03_worklog.md`.
  - Files: `Docs/manifest/11_ci.md`, `Docs/reference/release_workflow.md`, `Docs/implementation/00_status.md`, `Docs/implementation/03_worklog.md`
  - Prompt chain: `prompt-02` -> `prompt-11` -> `prompt-03`

- [x] AR-C08: Capture first remote pass evidence for `cmd-37-38-dash-data-quality`.
  - AC: one remote GitHub Actions run shows Dash data-quality gate passing and artifact publication.
  - Verify: pull-request run `21811670116`, job `cmd-37-38-dash-data-quality` passed (`https://github.com/Nirtzur0/AGORA/actions/runs/21811670116/job/62924847427`) with `dash-data-quality-report` artifact publication; docs references present via `rg -n "21811670116|cmd-37-38-dash-data-quality|dash-data-quality-report|actions/runs/21811670116" Docs/manifest/11_ci.md Docs/implementation/00_status.md Docs/implementation/03_worklog.md`.
  - Files: `Docs/manifest/11_ci.md`, `Docs/implementation/00_status.md`, `Docs/implementation/03_worklog.md`
  - Prompt chain: `prompt-02` -> `prompt-11` -> `prompt-03`

- [x] AR-C09: Expand warning-signal governance beyond `CMD-27`.
  - AC: warning policy is defined and automated for broader suites (`CMD-25` and/or `CMD-13`) with explicit thresholds or bounded-exception rules.
  - Verify: `E2E_FULL_WARNING_BUDGET=200 make PYTHON=python3 test-e2e` (PASS, 2026-02-09), `E2E_FULL_WARNING_BUDGET=0 make PYTHON=python3 test-e2e` (expected FAIL, 2026-02-09), and `rg -n "E2E_FULL_WARNING_BUDGET|check_full_e2e_warning_budget.py|CMD-13" Makefile .github/workflows/ci.yml Docs/manifest/10_testing.md Docs/manifest/11_ci.md Docs/manifest/09_runbook.md` (PASS, 2026-02-09).
  - Files: `Makefile`, `.github/workflows/ci.yml`, `Docs/manifest/10_testing.md`, `Docs/manifest/11_ci.md`
  - Prompt chain: `prompt-10` -> `prompt-02` -> `prompt-03`

## M9 - CI Operability Policy and Trend Hardening

- [x] AR-C10: Codify runtime/flake policy for nightly + release jobs.
  - AC: explicit runtime target, timeout/retry budget, and promotion-blocking fallback path are documented and cross-linked in CI + release-readiness docs.
  - Verify: `rg -n "cmd-13-nightly-full-suite|release-tag-gate|timeout-minutes|NIGHTLY_FLAKE_RETRY_BUDGET|RELEASE_FLAKE_RETRY_BUDGET|runtime_policy_summary|Runtime and Flake Budget Policy|M9 Release Operability Follow-Through" .github/workflows/ci.yml Docs/manifest/11_ci.md Docs/reference/release_workflow.md Docs/implementation/checklists/06_release_readiness.md` (PASS, 2026-02-09).
  - Files: `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`, `Docs/reference/release_workflow.md`, `Docs/implementation/checklists/06_release_readiness.md`
  - Prompt chain: `prompt-14` -> `prompt-02` -> `prompt-11` -> `prompt-03`

- [x] AR-C11: Publish runtime+flake trend artifact for heavy CI jobs.
  - AC: nightly/release runs produce a durable trend artifact/dashboard summarizing job duration and retry/flake signals.
  - Verify: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/test_ci_runtime_trend.py` (PASS, 2026-02-09), `rg -n "build_ci_runtime_trend.py|cmd-13-nightly-runtime-trend|release-tag-runtime-trend|runtime|duration|retry|flake|trend|artifact" .github/workflows/ci.yml scripts/build_ci_runtime_trend.py Docs/manifest/07_observability.md Docs/manifest/11_ci.md Docs/implementation/checklists/06_release_readiness.md Docs/reference/release_workflow.md` (PASS, 2026-02-09), and workflow dispatch run `21813014551` job `62928919065` PASS with `cmd-13-nightly-runtime-trend` artifact (`https://github.com/Nirtzur0/AGORA/actions/runs/21813014551/job/62928919065`).
  - Files: `.github/workflows/ci.yml`, `scripts/*`, `Docs/manifest/07_observability.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/checklists/06_release_readiness.md`
  - Prompt chain: `prompt-14` -> `prompt-02` -> `prompt-10` -> `prompt-03`

- [x] AR-C12: Route observability outputs to an external dashboard/pager.
  - AC: one external operational sink receives objective/observability CI outputs with documented escalation ownership.
  - Verify: `make PYTHON=python3 check-observability-sink-dry-run` (PASS, 2026-02-09), `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/test_publish_observability_sink.py tests/unit/test_ci_runtime_trend.py` (PASS, 2026-02-09), `rg -n "publish_observability_sink.py|observability_sink_mode|observability_sink_url|cmd-13-nightly-observability-sink-report|release-tag-observability-sink-report|check-observability-sink-dry-run" .github/workflows/ci.yml scripts/publish_observability_sink.py Makefile Docs/manifest/07_observability.md Docs/manifest/11_ci.md Docs/reference/release_workflow.md` (PASS, 2026-02-09), and workflow dispatch run `21813367976` job `62929945541` PASS with sink publish step pass (`https://github.com/Nirtzur0/AGORA/actions/runs/21813367976/job/62929945541`).
  - Files: `.github/workflows/ci.yml`, `scripts/publish_observability_sink.py`, `tests/unit/test_publish_observability_sink.py`, `Makefile`, `Docs/manifest/07_observability.md`, `Docs/manifest/11_ci.md`, `Docs/reference/release_workflow.md`
  - Prompt chain: `prompt-14` -> `prompt-11` -> `prompt-02` -> `prompt-03`
