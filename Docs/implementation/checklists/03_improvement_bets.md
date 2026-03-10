# Checklist: Improvement Bets

Date: 2026-02-09
Prompt packet: `prompt-02-app-development-playbook`
Triggering delta: `DIR-23` / `AR-C17` enforcement is now closed, so `DIR-24` troubleshooting signatures became the next non-redundant packet.
Objective anchor: `Docs/manifest/00_overview.md#Core Objective`

Checked boxes imply acceptance signals were met and verification evidence was recorded in `Docs/implementation/00_status.md` and `Docs/implementation/03_worklog.md`.

## Active Bets (Post-M10 Rerank)

## Bet DIR-24: Sink-failure troubleshooting signature matrix

- [ ] Add concrete sink-failure error signatures and first-response actions.
  - Owner type: maintainer
  - Effort: S
  - Target files/areas: `Docs/reference/release_workflow.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/checklists/06_release_readiness.md`
  - AC: docs include a troubleshooting matrix with representative error signatures, likely causes, and first-response owners/actions.
  - Verify: `rg -n "Troubleshooting|signature|response|sink publish|CMD-40|objective-observability-sink-report|cmd-13-nightly-observability-sink-report" Docs/reference/release_workflow.md Docs/manifest/11_ci.md Docs/implementation/checklists/06_release_readiness.md`.
  - Acceptance signal: sink incidents can be triaged with deterministic playbook guidance instead of policy-only references.
  - Suggested prompt chain: `prompt-11` -> `prompt-03`

## Completed Bets (Recent)

## Bet DIR-23: Periodic sink-evidence recency policy enforcement (`AR-C17`)

- [x] Enforce periodic recency policy for sink evidence outside sink-routing code-change paths.
  - Evidence summary: `.github/workflows/ci.yml` now includes weekly `sink-evidence-recency-gate` plus release-tag recency preflight enforcement; command path `CMD-41` (`make check-sink-evidence-recency`) is mapped in runbook/CI/release docs and covered by `tests/unit/test_sink_evidence_recency.py`.

## Bet DIR-23: Periodic sink-evidence recency policy shaping (`AR-C17` pre-implementation)

- [x] Define periodic recency policy terms (cadence + thresholds + owners + waiver constraints) across CI/release/readiness docs.
  - Evidence summary: policy wording now exists in `Docs/reference/release_workflow.md`, `Docs/manifest/11_ci.md`, and `Docs/implementation/checklists/06_release_readiness.md`; enforcement implementation is queued for `prompt-02`.

## Bet DIR-22: Non-dispatch objective/snapshot sink evidence depth (`AR-C16`)

- [x] Capture one qualifying non-dispatch remote sink publish evidence run for `objective-metrics-gate`.
  - Evidence summary: pull request run `21824080587`, objective job `62964679628`, sink publish line `observability_sink_publish status=dry_run mode=dry_run`, artifacts `objective-metrics-report` + `observability-snapshot-report`.

## Bet DIR-21: Sink-evidence freshness guardrail (`AR-C15`)

- [x] Add docs/CI guardrail requiring current sink evidence references when sink-routing behavior changes.
  - Evidence summary: `.github/workflows/ci.yml` now enforces run URL + job + artifact + <=30-day date checks for sink-routing file diffs.

## Bet DIR-20: Remote objective/snapshot sink evidence depth (`AR-C14`)

- [x] Capture first remote active-mode sink publish evidence for `objective-metrics-gate` (`CMD-29` / `CMD-32`).
  - Evidence summary: run `21824083555`, objective job `62964694204`, artifacts `objective-metrics-report` + `observability-snapshot-report`.

## Execution Packet Recommendations

- [x] Completed packet (`small` appetite): `DIR-23` (`prompt-11`) policy shaping.
- [x] Completed packet (`medium` appetite): `DIR-23` enforcement (`prompt-02`).
- [ ] Now packet (`small` appetite): `DIR-24` (`prompt-11`).
- [ ] Next packet (`small` appetite): `prompt-03-alignment-review-gate` rerank checkpoint after `DIR-24` docs follow-through.
- [ ] Not now packet (`small` appetite): additional governance expansion beyond `AR-C18` until troubleshooting signatures are documented.
