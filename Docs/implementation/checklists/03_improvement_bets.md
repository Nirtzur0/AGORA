# Checklist: Improvement Bets

Date: 2026-02-09
Prompt packet: `prompt-02-app-development-playbook`
Triggering delta: `DIR-18` policy-shaping was complete, so the non-redundant next slice was implementation + first remote sink evidence for `AR-C12`.
Objective anchor: `Docs/manifest/00_overview.md#Core Objective`

Checked boxes imply acceptance signals were met and verification evidence was recorded in `Docs/implementation/00_status.md` and `Docs/implementation/03_worklog.md`.

## Active Bets (Post-DIR-17 Closure)

## Bet DIR-18: External observability sink/pager integration

- [x] Define external sink ownership + severity routing + fallback policy before implementation.
  - Owner type: maintainer
  - Effort: M
  - Target files/areas: `Docs/manifest/07_observability.md`, `Docs/manifest/11_ci.md`, `Docs/reference/release_workflow.md`, `Docs/implementation/checklists/06_release_readiness.md`
  - AC: escalation owner, severity mapping, and dry-run/fallback policy are explicit and linked from CI/release docs.
  - Verify: `rg -n "External Sink Ownership and Escalation Policy|External Sink Routing Plan|External Sink Ownership and Rollout Readiness|M9 External Sink Routing Prep" Docs/manifest/07_observability.md Docs/manifest/11_ci.md Docs/reference/release_workflow.md Docs/implementation/checklists/06_release_readiness.md` (PASS, 2026-02-09).
  - Acceptance signal: `AR-C12` implementation can proceed without ambiguity about incident ownership and fallback behavior.
  - Suggested prompt chain: `prompt-11` -> `prompt-02` -> `prompt-03`

- [x] Route objective/observability CI outputs to an external dashboard/paging surface.
  - Owner type: maintainer
  - Effort: L
  - Target files/areas: `.github/workflows/ci.yml`, `scripts/publish_observability_sink.py`, `Makefile`, `Docs/manifest/07_observability.md`, `Docs/manifest/11_ci.md`, `Docs/reference/release_workflow.md`
  - AC: one external sink receives and exposes key CI observability outputs.
  - Verify: `make PYTHON=python3 check-observability-sink-dry-run` (PASS, 2026-02-09), `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/test_publish_observability_sink.py tests/unit/test_ci_runtime_trend.py` (PASS, 2026-02-09), `rg -n "publish_observability_sink.py|observability_sink_mode|observability_sink_url|cmd-13-nightly-observability-sink-report|release-tag-observability-sink-report|check-observability-sink-dry-run" .github/workflows/ci.yml scripts/publish_observability_sink.py Makefile Docs/manifest/07_observability.md Docs/manifest/11_ci.md Docs/reference/release_workflow.md` (PASS, 2026-02-09), and workflow dispatch run `21813367976` job `62929945541` PASS with sink publish step pass (`https://github.com/Nirtzur0/AGORA/actions/runs/21813367976/job/62929945541`).
  - Acceptance signal: external sink publish path is active with first remote evidence and artifacted sink report payload.
  - Suggested prompt chain: `prompt-02` -> `prompt-03`

## Completed Bets (Recent)

## Bet DIR-17: Runtime+flake trend telemetry for heavy CI jobs

- [x] Publish runtime+flake trend artifact for `release-tag-gate` and `cmd-13-nightly-full-suite`.
  - Owner type: maintainer
  - Effort: M
  - Target files/areas: `.github/workflows/ci.yml`, `scripts/*`, `Docs/manifest/07_observability.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/checklists/06_release_readiness.md`
  - AC: one artifact/report captures runtime duration and retry/flake trend for heavy jobs and is linked in docs.
  - Verify: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/test_ci_runtime_trend.py` (PASS, 2026-02-09), `rg -n "build_ci_runtime_trend.py|cmd-13-nightly-runtime-trend|release-tag-runtime-trend|runtime|duration|retry|flake|trend|artifact" .github/workflows/ci.yml scripts/build_ci_runtime_trend.py Docs/manifest/07_observability.md Docs/manifest/11_ci.md Docs/implementation/checklists/06_release_readiness.md Docs/reference/release_workflow.md` (PASS, 2026-02-09), and workflow dispatch run `21813014551` job `62928919065` PASS with `cmd-13-nightly-runtime-trend` artifact (`https://github.com/Nirtzur0/AGORA/actions/runs/21813014551/job/62928919065`).
  - Acceptance signal: operational drift in heavy CI paths is measurable over time, not only per-run.
  - Suggested prompt chain: `prompt-02` -> `prompt-10` -> `prompt-03`

## Bet DIR-16: Runtime/flake policy for nightly + release jobs

- [x] Codify runtime/flake budget policy and fallback path for `cmd-13-nightly-full-suite` and `release-tag-gate`.
  - Owner type: maintainer
  - Effort: M
  - Target files/areas: `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`, `Docs/reference/release_workflow.md`, `Docs/implementation/checklists/06_release_readiness.md`
  - AC: explicit policy states runtime targets, timeout/retry budget, flake thresholds, and promotion-blocking behavior.
  - Verify: `rg -n "cmd-13-nightly-full-suite|release-tag-gate|timeout-minutes|NIGHTLY_FLAKE_RETRY_BUDGET|RELEASE_FLAKE_RETRY_BUDGET|runtime_policy_summary|Runtime and Flake Budget Policy|M9 Release Operability Follow-Through" .github/workflows/ci.yml Docs/manifest/11_ci.md Docs/reference/release_workflow.md Docs/implementation/checklists/06_release_readiness.md` (PASS, 2026-02-09).
  - Acceptance signal: nightly/release job reliability expectations are explicit, auditable, and referenced in release-readiness sign-off.
  - Suggested prompt chain: `prompt-02` -> `prompt-11` -> `prompt-03`

## Bet DIR-14: Remote CI evidence closure for newly added jobs

- [x] Record first remote pass evidence for `release-tag-gate`, `cmd-13-nightly-full-suite`, and `cmd-37-38-dash-data-quality`.
  - Owner type: maintainer
  - Effort: S
  - Target files/areas: `Docs/manifest/11_ci.md`, `Docs/reference/release_workflow.md`, `Docs/implementation/checklists/06_release_readiness.md`, `Docs/implementation/00_status.md`, `Docs/implementation/03_worklog.md`
  - AC: docs include run IDs/URLs (or equivalent references) and artifact names for all three jobs.
  - Verify: `rg -n "21811670648|21811670116|release-tag-gate|cmd-13-nightly-full-suite|cmd-37-38-dash-data-quality|actions/runs" Docs/manifest/11_ci.md Docs/reference/release_workflow.md Docs/implementation/00_status.md Docs/implementation/03_worklog.md` (PASS, 2026-02-09).
  - Acceptance signal: remote run evidence is now recorded for all three jobs (`release-tag-gate`, `cmd-13-nightly-full-suite`, `cmd-37-38-dash-data-quality`).
  - Suggested prompt chain: `prompt-02` -> `prompt-11` -> `prompt-03`

## Bet DIR-15: Warning-signal hardening beyond `CMD-27`

- [x] Define and implement bounded warning governance for broader suites (`CMD-25` and/or `CMD-13`).
  - Owner type: maintainer
  - Effort: M
  - Target files/areas: `Makefile`, `.github/workflows/ci.yml`, `scripts/*`, `Docs/manifest/10_testing.md`, `Docs/manifest/11_ci.md`
  - AC: warning policy is explicit (budget or bounded exception policy), with at least one automated enforcement path outside `CMD-27`.
  - Verify: `E2E_FULL_WARNING_BUDGET=200 make PYTHON=python3 test-e2e` (PASS, 2026-02-09), `E2E_FULL_WARNING_BUDGET=0 make PYTHON=python3 test-e2e` (expected FAIL, 2026-02-09), and `rg -n "E2E_FULL_WARNING_BUDGET|check_full_e2e_warning_budget.py|CMD-13" Makefile .github/workflows/ci.yml Docs/manifest/10_testing.md Docs/manifest/11_ci.md Docs/manifest/09_runbook.md` (PASS, 2026-02-09).
  - Acceptance signal: full e2e warning noise is now bounded by policy with explicit budget ownership.
  - Suggested prompt chain: `prompt-10` -> `prompt-02` -> `prompt-03`

## Bet DIR-08: CI automation for Dash data-quality gates

- [x] Add CI enforcement for `CMD-37` + `CMD-38`.
  - Owner type: maintainer
  - Effort: M
  - Target files/areas: `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`, `Docs/manifest/09_runbook.md`, `dash_app/data/validation.py`, `tests/test_data_validation.py`, `tests/test_loaders_smoke.py`
  - AC: CI runs Dash validation and Dash loader/validation regression tests with explicit pass/fail status and report artifact upload.
  - Verify: local `CMD-37`/`CMD-38` passes + CI mapping grep (`cmd-37-38-dash-data-quality`) (PASS, 2026-02-09).
  - Acceptance signal: Dash checks are CI-enforced.
  - Suggested prompt chain: `prompt-02` -> `prompt-11` -> `prompt-03`

## Bet DIR-09: Warning-budget guard for deterministic critical e2e

- [x] Add warning-budget threshold around `CMD-27`.
  - Owner type: maintainer
  - Effort: M
  - Target files/areas: `Makefile`, `.github/workflows/ci.yml`, `Docs/manifest/10_testing.md`, `Docs/manifest/11_ci.md`
  - AC: warning growth above budget fails deterministic critical e2e.
  - Verify: `make PYTHON=python3 test-e2e-critical` (PASS) + budget breach run with `E2E_CRITICAL_WARNING_BUDGET=0` (expected FAIL) (2026-02-09).
  - Acceptance signal: warning debt has measurable guardrails.
  - Suggested prompt chain: `prompt-09` -> `prompt-10` -> `prompt-03`

## Bet DIR-10: Delta-based alignment freshness guard

- [x] Enforce trigger-aware `prompt-03` reruns.
  - Owner type: maintainer
  - Effort: S
  - Target files/areas: `Docs/implementation/checklists/07_alignment_review.md`, `Docs/implementation/00_status.md`, `Docs/implementation/03_worklog.md`, `.github/workflows/ci.yml`
  - AC: each alignment rerun records concrete triggering delta and next non-redundant packet.
  - Verify: required fields present and docs-guardrail enforcement in CI (PASS, 2026-02-09).
  - Acceptance signal: prompt-03 reruns are intentional and non-repetitive.
  - Suggested prompt chain: `prompt-11` -> `prompt-03`

## Bet DIR-11: Tag-triggered release automation

- [x] Add release-tag CI automation path.
  - Owner type: maintainer
  - Effort: M
  - Target files/areas: `.github/workflows/ci.yml`, `Docs/reference/release_workflow.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/checklists/06_release_readiness.md`
  - AC: release workflow is triggerable by `v*` tags with explicit command coverage mapping.
  - Verify: `rg -n "tags: \\[ 'v\\*' \\]|release-tag-gate|run_release_gate" .github/workflows/ci.yml Docs/reference/release_workflow.md Docs/manifest/11_ci.md` (PASS, 2026-02-09).
  - Acceptance signal: release path is fail-closed and automated in CI.
  - Suggested prompt chain: `prompt-11` -> `prompt-02` -> `prompt-03`

## Bet DIR-13: Full `CMD-13` suite promotion strategy

- [x] Define and adopt staged full-e2e promotion policy.
  - Owner type: maintainer
  - Effort: M
  - Target files/areas: `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`, `Docs/manifest/10_testing.md`, `Docs/implementation/checklists/06_release_readiness.md`
  - AC: policy defines nightly/manual `CMD-13` coverage and promotion criteria.
  - Verify: `rg -n "cmd-13-nightly-full-suite|run_full_e2e|schedule|CMD-13" .github/workflows/ci.yml Docs/manifest/10_testing.md Docs/manifest/11_ci.md` (PASS, 2026-02-09).
  - Acceptance signal: full e2e promotion has an automated run path.
  - Suggested prompt chain: `prompt-02` -> `prompt-10` -> `prompt-03`

## Execution Packet Recommendations

- [x] Completed packet (`medium` appetite): DIR-08 + DIR-09 + DIR-10.
- [x] Completed packet (`medium` appetite): DIR-11 + DIR-13.
- [x] Completed packet (`small` appetite): DIR-14.
- [x] Completed packet (`small` appetite): DIR-15.
- [x] Completed packet (`medium` appetite): DIR-16.
- [x] Completed packet (`medium` appetite): DIR-17.
- [x] Completed packet (`large` appetite): DIR-18.
