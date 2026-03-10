# Checklist: Release Readiness

Date: 2026-02-09
Packet: `prompt-02-app-development-playbook` follow-through (`AR-C17` periodic sink-evidence recency policy enforcement)

## Versioning and changelog

- [x] Version bump type selected (MAJOR/MINOR/PATCH) and justified.
  - Decision: `PATCH` (operational and documentation hardening; no public contract break).
- [x] `CHANGELOG.md` updated with release notes.
  - Evidence: `CHANGELOG.md` unreleased section includes CI/release hardening updates.
- [x] Upgrade notes completed (use `Docs/how_to/upgrade_notes_template.md`).
  - Evidence: template reviewed and linked from release workflow docs.

## Quality gates

- [x] Unit and integration checks passed using canonical command map.
  - Verify: `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test` (PASS)
  - Verify: `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test-all` (PASS)
- [x] E2E checks passed or explicitly gated with rationale.
  - Verify: `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test-e2e` (PASS)
- [x] Stub guardrail check passed.
  - Evidence: included in `make ... test` and `make ... test-all` (`check-stubs` target passed).

## Artifact-feature alignment gate

- [x] Latest artifact-feature alignment verdict is referenced before sign-off.
  - Evidence: `Docs/implementation/reports/artifact_feature_alignment.md` (`Verdict: ALIGNED_WITH_GAPS`, 2026-02-08) and `Docs/implementation/checklists/08_artifact_feature_alignment.md`.
- [x] Open artifact-feature outcomes are explicitly acknowledged in release tracking.
  - Evidence: unresolved items (`AF-O02`, `AF-O03`) remain tracked in `Docs/implementation/checklists/08_artifact_feature_alignment.md` and `Docs/implementation/checklists/02_milestones.md`.

## Contract and migration safety

- [x] API/contract changes reviewed and documented.
  - Result: N/A for this packet (no API schema changes).
- [x] DB migrations reviewed with rollback notes.
  - Result: N/A for this packet (no migration changes).
- [x] Evidence/citation invariants validated for affected workflows.
  - Result: N/A for this packet (CI/release docs and workflow only).

## CI and release workflow

- [x] CI workflow mapping in `Docs/reference/release_workflow.md` is current.
  - Evidence: current mapping includes release/promotion jobs (`CMD-11`, `CMD-25`, `CMD-27`, `CMD-13`, `CMD-30`, `CMD-31`, `CMD-37`, `CMD-38`, `CMD-01/02/04`).
- [x] Tag/release automation status documented (implemented or explicit TODO).
  - Evidence: target-state trigger spec and fail-closed policy documented in `Docs/reference/release_workflow.md`.

## M7 Release Operability Follow-Through (`AR-C04`, `AR-C05`)

- [x] Tag-triggered release policy is explicitly documented.
  - Evidence: `Docs/reference/release_workflow.md` now defines trigger spec, fail-closed behavior, and required command sequence for `v*` tags.
- [x] Tag-triggered release workflow is implemented in CI.
  - Evidence: `.github/workflows/ci.yml` includes `push.tags: ['v*']`, `workflow_dispatch` input `run_release_gate`, and `release-tag-gate` command set.
- [x] Tag-triggered release workflow has one passing remote GitHub Actions evidence run.
  - Evidence: workflow dispatch run `21811670648`, job `release-tag-gate` (ID `62924827121`) passed with release artifacts uploaded (`https://github.com/Nirtzur0/AGORA/actions/runs/21811670648/job/62924827121`).
- [x] Full `CMD-13` promotion strategy is explicitly documented.
  - Evidence: policy sections in `Docs/reference/release_workflow.md`, `Docs/manifest/10_testing.md`, and `Docs/manifest/11_ci.md` define trigger matrix, ownership, and promotion criteria.
- [x] Nightly full `CMD-13` automation is implemented in CI.
  - Evidence: `.github/workflows/ci.yml` includes `schedule` trigger and `cmd-13-nightly-full-suite` job; manual trigger path uses `workflow_dispatch` input `run_full_e2e`.
- [x] Full `CMD-13` warning-budget policy is enforced in promotion/release paths.
  - Evidence: `.github/workflows/ci.yml` runs `E2E_FULL_WARNING_BUDGET=200 make PYTHON=python test-e2e` in `cmd-13-nightly-full-suite` and `release-tag-gate`; local verification shows expected pass/fail behavior (`E2E_FULL_WARNING_BUDGET=200` PASS, `E2E_FULL_WARNING_BUDGET=0` expected FAIL).
- [x] Nightly full `CMD-13` job has one passing remote GitHub Actions evidence run.
  - Evidence: workflow dispatch run `21811670648`, job `cmd-13-nightly-full-suite` (ID `62924827118`) passed (`https://github.com/Nirtzur0/AGORA/actions/runs/21811670648/job/62924827118`).

## M9 Release Operability Follow-Through (`AR-C10`)

- [x] Runtime and retry/flake budgets are explicitly documented for heavy nightly/release jobs.
  - Evidence: `Docs/reference/release_workflow.md` `Runtime and Flake Budget Policy (AR-C10)` section defines runtime targets, hard timeouts, and retry budgets for `cmd-13-nightly-full-suite` and `release-tag-gate`.
- [x] Runtime/flake policy is encoded in CI workflow job configuration.
  - Evidence: `.github/workflows/ci.yml` now sets `timeout-minutes` + policy env vars (`NIGHTLY_FLAKE_RETRY_BUDGET`, `RELEASE_FLAKE_RETRY_BUDGET`) and emits `runtime_policy_summary` output for heavy gates.
- [x] Release promotion is fail-closed on runtime/flake policy breaches.
  - Evidence: `.github/workflows/ci.yml` `Enforce release runtime and flake budget policy` step blocks release when runtime target is exceeded or retry policy is violated.
- [x] Runtime policy evidence is retained as release artifacts.
  - Evidence: `release-tag-gate-artifacts` now includes `/tmp/release-tag-runtime-policy.txt`; nightly publishes the same policy file inside `cmd-13-nightly-runtime-trend`.

## M9 Runtime Trend Telemetry Follow-Through (`AR-C11`)

- [x] Heavy nightly/release jobs publish runtime+flake trend artifact bundle.
  - Evidence: `.github/workflows/ci.yml` now runs `scripts/build_ci_runtime_trend.py` in both `cmd-13-nightly-full-suite` and `release-tag-gate`, producing `*-runtime-trend-latest.json`, `*-runtime-trend-history.jsonl`, and `*-runtime-trend-dashboard.md`.
- [x] Trend artifacts include runtime duration plus retry/flake usage signals.
  - Evidence: script output schema includes `elapsed_seconds`, `runtime_target_minutes`, `attempts_used`, `retry_budget`, `retries_used`, and derived delta/target flags.
- [x] Runtime trend dashboards are retained in CI evidence artifacts and job summaries.
  - Evidence: `cmd-13-nightly-runtime-trend` artifact upload path includes dashboard markdown; `release-tag-gate-artifacts` includes release dashboard markdown and both jobs append dashboard content to `$GITHUB_STEP_SUMMARY`.
- [x] First remote runtime-trend artifact evidence is captured.
  - Evidence: workflow dispatch run `21813014551`, job `cmd-13-nightly-full-suite` (`62928919065`) passed and published artifact `cmd-13-nightly-runtime-trend` (`https://github.com/Nirtzur0/AGORA/actions/runs/21813014551/job/62928919065`).

## M9 External Sink Routing Prep (`AR-C12`)

- [x] External sink escalation ownership is defined before implementation.
  - Evidence: `Docs/manifest/07_observability.md` now includes owner roles + severity mapping in `External Sink Ownership and Escalation Policy`.
- [x] Dry-run rollout and fallback behavior are explicitly documented.
  - Evidence: `Docs/manifest/07_observability.md`, `Docs/manifest/11_ci.md`, and `Docs/reference/release_workflow.md` all define dry-run/fail-open rollout and in-repo fallback signals (`CMD-29`, `CMD-32`, `CMD-39`).
- [x] First external-sink publish evidence is captured from a remote CI run.
  - Evidence: workflow dispatch run `21813367976`, job `cmd-13-nightly-full-suite` (`62929945541`) includes sink publish step pass (`active`, host `httpbin.org`, response `200`) and artifacted sink report files (`cmd-13-nightly-observability-sink-report.json`, `cmd-13-nightly-observability-sink-summary.md`).

## M10 External Sink Governance Follow-Through (`AR-C13`)

- [x] Gate-class sink failure posture is explicitly documented for objective, nightly, and release publish paths.
  - Evidence: `Docs/manifest/07_observability.md` now includes `Failure-Mode Decision Matrix (AR-C13)` covering `objective-metrics-gate`, `cmd-13-nightly-full-suite`, and `release-tag-gate`.
- [x] Release governance fail-closed rules for sink publish failures are documented.
  - Evidence: `Docs/reference/release_workflow.md` now defines fail-closed release impact for objective/release gate classes and explicit waiver requirements.
- [x] CI routing docs are synchronized with the same gate-class policy model.
  - Evidence: `Docs/manifest/11_ci.md` `External Sink Routing Plan` now documents identical gate-class policy mapping.
- [x] Objective/snapshot remote active sink evidence depth is captured (`AR-C14`).
  - Evidence: workflow dispatch run `21824083555`, job `objective-metrics-gate` (`62964694204`) includes sink publish step pass (`observability_sink_publish status=pass`, mode `active`, response `200`) and artifacts `objective-metrics-report` + `observability-snapshot-report` with sink report/summary payload files.
- [x] Sink-evidence freshness guardrail is enforced for sink-routing edits (`AR-C15`).
  - Evidence: `.github/workflows/ci.yml` `docs-guardrail` now enforces `sink_routing_changes` with required doc updates (`00_status`, `03_worklog`, `06_release_readiness`, `07_alignment_review`) plus added run/job/artifact/date freshness checks (`sink_run_url`, `sink_job_ref`, `sink_artifact_ref`, `sink_cutoff_date`).

## M11 Sink Operability Maturity Follow-Through (`AR-C16`)

- [x] Qualifying non-dispatch objective/snapshot sink evidence is captured.
  - Evidence: pull request run `21824080587`, objective job `62964679628`, sink publish log line `observability_sink_publish status=dry_run mode=dry_run`, and artifacts `objective-metrics-report` + `observability-snapshot-report` (`https://github.com/Nirtzur0/AGORA/actions/runs/21824080587/job/62964679628`).

## M11 Periodic Recency Policy Enforcement (`AR-C17`)

- [x] Standing sink-evidence recency thresholds are explicitly documented.
  - Evidence: policy defines objective <=14 days, nightly <=7 days, and release-tag <=30 days (or fresh release-candidate run) in `Docs/reference/release_workflow.md` and `Docs/manifest/11_ci.md`.
- [x] Periodic review cadence and ownership are explicitly documented.
  - Evidence: weekly Monday UTC review + release sign-off checks are assigned to maintainer on-call and release owner in `Docs/reference/release_workflow.md`.
- [x] Waiver constraints are explicitly documented for stale evidence exceptions.
  - Evidence: 72-hour capped waiver model with dual-owner acknowledgement + remediation timing is documented in `Docs/reference/release_workflow.md`.
- [x] CI/runtime enforcement for `AR-C17` is implemented.
  - Evidence: `.github/workflows/ci.yml` now includes weekly `sink-evidence-recency-gate` (`schedule` Monday UTC `0 8 * * 1`) and `release-tag-gate` preflight step `Enforce periodic sink-evidence recency policy for release sign-off`; both execute `scripts/check_sink_evidence_recency.py` (`CMD-41`).
  - Evidence: release artifacts now include `/tmp/release-sink-evidence-recency-report.json` and `/tmp/release-sink-evidence-recency-summary.md` inside `release-tag-gate-artifacts`.
  - Evidence continuity reference (2026-02-09): run `https://github.com/Nirtzur0/AGORA/actions/runs/21824083555`, job `https://github.com/Nirtzur0/AGORA/actions/runs/21824083555/job/62964694204`, artifacts `objective-metrics-report` and `observability-snapshot-report`.

## Documentation completeness

- [x] `Docs/INDEX.md` links all release-relevant docs.
- [x] `Docs/reference/versioning_policy.md` reviewed for current release.
- [x] Troubleshooting and upgrade guidance updated if behavior changed.
  - Result: release-operability behavior changed (runtime/flake policy codified); release workflow docs and checklist evidence were updated accordingly.
- [x] Release readiness references the active literature-backed risk context.
  - Verify: `rg -n "20_literature_review|literature" Docs/INDEX.md Docs/implementation/checklists/06_release_readiness.md Docs/implementation/checklists/20_literature_review.md`
  - Evidence: `Docs/INDEX.md` links `Docs/manifest/20_literature_review.md` and this checklist is now referenced by `Docs/manifest/20_literature_review.md` validation item 7 (`PASS`, 2026-02-09).
