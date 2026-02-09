# Checklist: Alignment Review Gate

Date: 2026-02-09 (fresh `prompt-03` checkpoint after `prompt-02` DIR-14 remote-evidence closure)
Prompt packet: `prompt-03-alignment-review-gate`
Triggering delta: post-`prompt-02` DIR-14 follow-through captured first remote CI evidence for `release-tag-gate`, `cmd-13-nightly-full-suite`, and `cmd-37-38-dash-data-quality`; alignment checkpoint rerun required to re-rank residual risk now centered on UI smoke instability (`CMD-30`/`CMD-31`).
Verdict: `ALIGNED_WITH_RISKS`

Objective anchor: `Docs/manifest/00_overview.md#Core Objective`

## Required Questions

- [x] Are we still building the same thing defined by Core Objective?
  - Evidence: authority boundaries and evidence immutability remain unchanged in current contracts and architecture docs (`Docs/manifest/00_overview.md`, `Docs/manifest/04_api_contracts.md`, `Docs/manifest/05_data_model.md`).

- [x] Is the main user journey usable end-to-end right now?
  - Evidence: `make PYTHON=python3 test-e2e-critical` -> PASS (`1 passed`, 2026-02-09); Dash explorer slice is runnable and responds locally (`python3 dash_app/app.py` + `curl -fsS http://127.0.0.1:8050/` -> PASS, 2026-02-09).

- [x] Are we measuring the right success metrics from the objective?
  - Evidence: `make PYTHON=python3 check-objective-metrics` -> PASS and `make PYTHON=python3 check-observability-snapshot` -> PASS (2026-02-09); Dash data-quality checks pass via `python3 -m dash_app.data.validation --repo-root . --output /tmp/agora-dash-validation.json` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/test_data_validation.py tests/test_loaders_smoke.py`.

- [x] Are we spending meaningful effort on explicit non-goals?
  - Evidence: latest packet remained inside provenance/auditability scope (read-only data explorer + validation over existing outputs), without changing authority boundaries or artifact mutability behavior.

## Evidence-Backed Misalignment Checklist

- [x] Dash quality gates are now CI-enforced.
  - Evidence: `.github/workflows/ci.yml` job `cmd-37-38-dash-data-quality` runs `CMD-37` + `CMD-38` and uploads `dash-data-quality-report`; docs mapping updated in `Docs/manifest/11_ci.md`.

- [x] Critical e2e gate now enforces a warning budget.
  - Evidence: `make PYTHON=python3 test-e2e-critical` -> PASS (`37 warnings` <= budget 40), `E2E_CRITICAL_WARNING_BUDGET=0 make PYTHON=python3 test-e2e-critical` -> expected FAIL.

- [x] Alignment freshness guard is now process-enforced.
  - Evidence: docs-guardrail CI now fails when `Docs/implementation/checklists/07_alignment_review.md` changes without `Triggering delta:` and `Recommended next non-redundant packet:` metadata and corresponding status/worklog trigger context.

- [x] Tag-triggered release automation path is now implemented in CI.
  - Evidence: `.github/workflows/ci.yml` now includes `push.tags: ['v*']` and job `release-tag-gate`; `AR-C04` is checked in `Docs/implementation/checklists/02_milestones.md`.

- [x] Full `CMD-13` promotion strategy is now implemented in CI.
  - Evidence: `.github/workflows/ci.yml` now includes `schedule` + job `cmd-13-nightly-full-suite`; `AR-C05` is checked in `Docs/implementation/checklists/02_milestones.md`.

- [x] First remote GitHub Actions confirmation for the Dash CI job is captured.
  - Evidence: PR run `21811670116`, job `cmd-37-38-dash-data-quality` passed (`https://github.com/Nirtzur0/AGORA/actions/runs/21811670116/job/62924847427`).

- [x] First remote GitHub Actions confirmations for `cmd-13-nightly-full-suite` and `release-tag-gate` are captured.
  - Evidence: workflow dispatch run `21811670648` passed for `cmd-13-nightly-full-suite` (`https://github.com/Nirtzur0/AGORA/actions/runs/21811670648/job/62924827118`) and `release-tag-gate` (`https://github.com/Nirtzur0/AGORA/actions/runs/21811670648/job/62924827121`).

- [ ] PR UI smoke matrix is unstable across browsers and mobile.
  - Evidence: PR run `21811670116` failed in `cmd-30-ui-smoke-cross-browser` (`chromium`, `firefox`, `webkit`) and `cmd-31-ui-smoke-mobile` with `page.waitForURL("**/projects")` timeout in `apps/web/scripts/smoke_artifact_viewer.mjs`.

## Top 4 Next Corrections

- [ ] Correction 1: stabilize `CMD-30`/`CMD-31` UI smoke navigation across browser matrix and mobile.
  - Owner type: maintainer
  - Effort: M
  - Target files: `apps/web/scripts/smoke_artifact_viewer.mjs`, `apps/web/src/pages/LoginPage.jsx`, `.github/workflows/ci.yml`
  - Acceptance signal: one PR run shows `cmd-30-ui-smoke-cross-browser` and `cmd-31-ui-smoke-mobile` all green.
  - Milestone mapping: `Docs/implementation/checklists/02_milestones.md` (M3 UI audit surface/e2e confidence).

- [ ] Correction 2: ensure UI smoke failure paths always publish debug artifacts.
  - Owner type: maintainer
  - Effort: S
  - Target files: `apps/web/scripts/smoke_artifact_viewer.mjs`, `.github/workflows/ci.yml`
  - Acceptance signal: failed smoke runs upload at least one screenshot/log artifact per failing job.
  - Milestone mapping: `Docs/implementation/checklists/02_milestones.md` (M3 UI verification operability).

- [ ] Correction 3: codify runtime/flake budget policy for nightly + release jobs (`DIR-16`).
  - Owner type: maintainer
  - Effort: M
  - Target files: `Docs/manifest/11_ci.md`, `Docs/reference/release_workflow.md`, `Docs/implementation/checklists/06_release_readiness.md`
  - Acceptance signal: explicit runtime/retry policy exists and is referenced by release-readiness criteria.
  - Milestone mapping: `Docs/implementation/checklists/02_milestones.md` (M8 `AR-C09` follow-through extension).

- [ ] Correction 4: re-rank improvement directions after M7 closure and remote-evidence gating.
  - Owner type: maintainer
  - Effort: S
  - Target files: `Docs/implementation/reports/improvement_directions.md`, `Docs/implementation/checklists/03_improvement_bets.md`, `Docs/implementation/checklists/02_milestones.md`
  - Acceptance signal: updated `Now`/`Next` packet ranking reflects `DIR-14` closure and foregrounds UI smoke + runtime/flake policy risks.
  - Milestone mapping: planning follow-through (post-M7 backlog grooming).

## Next Execution Packet Mapping

- [x] Corrections are mapped into milestone checklist references (`M8`).
- [x] Recommended next non-redundant packet: `prompt-10-tests-stabilization-loop` to close `CMD-30`/`CMD-31` CI smoke instability before another policy-only pass.

## Latest Checkpoint

- [x] 2026-02-09 post-`prompt-08` alignment checkpoint completed; verdict remains `ALIGNED_WITH_RISKS`.
- [x] 2026-02-09 objective and observability checks pass (`CMD-29`, `CMD-32`).
- [x] 2026-02-09 critical e2e gate passes (`CMD-27`) with warning budget enforcement (`budget=40`, observed `37`).
- [x] 2026-02-09 Dash validation and loader tests pass (`CMD-37`, `CMD-38`) and CI gate wiring is complete (`cmd-37-38-dash-data-quality`).
- [x] 2026-02-09 post-`prompt-14` planning refresh recorded; next non-redundant implementation packet is `prompt-02-app-development-playbook` targeting `AR-C01`..`AR-C03`.
- [x] 2026-02-09 post-`prompt-02` follow-through completed for `AR-C01`..`AR-C03`; next non-redundant packet is a fresh `prompt-03` checkpoint.
- [x] 2026-02-09 fresh `prompt-03` checkpoint completed; residual risk now focused on `AR-C04` + `AR-C05` and remote confirmation of the new Dash CI job.
- [x] 2026-02-09 `prompt-11-docs-diataxis-release` follow-through completed for `AR-C04`/`AR-C05` policy shaping; next non-redundant packet is `prompt-02-app-development-playbook` for CI implementation.
- [x] 2026-02-09 `prompt-02-app-development-playbook` follow-through completed for `AR-C04`/`AR-C05` implementation (`release-tag-gate` + `cmd-13-nightly-full-suite`); next non-redundant packet is a fresh `prompt-03` checkpoint.
- [x] 2026-02-09 fresh `prompt-03` checkpoint completed after M7 closure; residual risk now focused on remote CI evidence freshness, and next non-redundant packet is `prompt-14-improvement-direction-bet-loop`.
- [x] 2026-02-09 `prompt-14-improvement-direction-bet-loop` refresh completed after M7 closure; new active `Now` packet is `DIR-14` + `DIR-15`, and next non-redundant packet is `prompt-02-app-development-playbook`.
- [x] 2026-02-09 `prompt-02-app-development-playbook` follow-through completed `DIR-15` (`AR-C09`) via full `CMD-13` warning-budget enforcement; remaining active `Now` scope is `DIR-14` remote evidence capture.
- [x] 2026-02-09 `prompt-02-app-development-playbook` follow-through closed `DIR-14` with remote evidence: dispatch run `21811670648` passed (`release-tag-gate`, `cmd-13-nightly-full-suite`) and PR run `21811670116` passed `cmd-37-38-dash-data-quality`.
- [x] 2026-02-09 fresh `prompt-03` checkpoint rerun after `DIR-14` closure; residual risk moved to UI smoke instability in `CMD-30`/`CMD-31`, and next non-redundant packet is `prompt-10-tests-stabilization-loop`.
