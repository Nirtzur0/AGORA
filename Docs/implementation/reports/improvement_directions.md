# Improvement Directions Report

Date: 2026-02-09
Prompt packet: `prompt-02-app-development-playbook`
Triggering delta: `DIR-23` / `AR-C17` command-backed enforcement is now implemented, moving residual focus to `DIR-24` troubleshooting signatures.
Objective anchor: `Docs/manifest/00_overview.md#Core Objective`

## Current-State Snapshot (Evidence-Backed)

AGORA remains aligned to the core objective. M10 sink-governance work is closed, but post-closure operability depth still needs bounded follow-through packets.

| Dimension | Current State | Evidence |
|---|---|---|
| Objective alignment | `ALIGNED_WITH_RISKS`; authority/evidence contracts remain intact | `Docs/implementation/checklists/07_alignment_review.md`, `Docs/implementation/reports/alignment_review.md` |
| Capability coverage | M9 and M10 outcomes are closed (`AR-C10`..`AR-C15`); M11 `AR-C16` and `AR-C17` are now closed | `Docs/implementation/checklists/02_milestones.md`, `Docs/implementation/checklists/06_release_readiness.md` |
| Sink governance posture | Gate-class policy and docs guardrail are implemented | `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`, `Docs/reference/release_workflow.md` |
| Evidence depth posture | Objective/snapshot sink evidence now includes both dispatch active and non-dispatch qualifying runs | `Docs/reference/release_workflow.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/checklists/06_release_readiness.md` |
| Planning hygiene | Prompt-03 checkpoint completed and explicitly routed to rerank stage | `Docs/implementation/checklists/07_alignment_review.md`, `Docs/implementation/00_status.md`, `Docs/implementation/03_worklog.md` |

## Opportunity Inventory

| ID | Direction | Type | Evidence | Gap | Impact | Confidence | Effort | Deferral Risk | Suggested Prompt Chain |
|---|---|---|---|---|---|---|---|---|---|
| DIR-20 | Capture remote active-mode sink evidence for objective/snapshot gates | Observability | run `21824083555` and job `62964694204` recorded in CI/release docs | Closed (2026-02-09 via `AR-C14`) | M | H | S | M | `prompt-02` -> `prompt-03` |
| DIR-21 | Add sink-evidence freshness guardrail for sink-routing edits | Governance | docs guardrail sink checks in `.github/workflows/ci.yml` | Closed (2026-02-09 via `AR-C15`) | M | M | M | M | `prompt-11` -> `prompt-02` -> `prompt-03` |
| DIR-22 | Capture qualifying non-dispatch objective/snapshot sink evidence | Observability | non-dispatch PR run `21824080587` objective job `62964679628` and artifacts are referenced in CI/release/readiness docs | Closed (2026-02-09 via `AR-C16`) | M | M | S | M | `prompt-02` -> `prompt-03` |
| DIR-23 | Enforce periodic sink-evidence recency policy | Governance | `CMD-41` plus CI/release enforcement wiring now exists in `.github/workflows/ci.yml`, runbook, and release docs | Closed (2026-02-09 via `AR-C17`) | H | M | M | H | `prompt-11` -> `prompt-02` -> `prompt-03` |
| DIR-24 | Add sink-failure troubleshooting signature matrix | Operability | release/CI docs define policy and routing | Open: no concrete sink-failure error-signature + first-response matrix | M | M | S | M | `prompt-11` -> `prompt-03` |

## Selected Directions (Top 3)

### DIR-22: Non-dispatch objective/snapshot sink evidence depth

- Outcome statement: record at least one qualifying non-dispatch remote run proving `objective-metrics-gate` sink publish execution with job/artifact evidence.
- Why now: current evidence depth is strong but concentrated on `workflow_dispatch`; adding non-dispatch evidence reduces release-governance blind spots.
- Implementation surface:
  - `.github/workflows/ci.yml`
  - `Docs/manifest/11_ci.md`
  - `Docs/reference/release_workflow.md`
  - `Docs/implementation/checklists/06_release_readiness.md`
  - `Docs/implementation/00_status.md`
  - `Docs/implementation/03_worklog.md`
- Integration dependencies:
  - existing objective gate path (`CMD-29`, `CMD-32`, sink publish path `CMD-40`)
  - remote workflow run capture via GitHub Actions/`gh`
- Testing strategy:
  - remote evidence capture (`gh run list/view` + objective job log grep + artifact listing)
  - docs sync grep validation across CI/release/status/worklog paths
- Observability/release/doc updates needed:
  - add non-dispatch run/job/artifact references to CI/release/readiness docs
  - record packet evidence in status/worklog
- Done signal: one qualifying non-dispatch run is documented with sink publish evidence and artifact references.

### DIR-23: Periodic sink-evidence recency policy

- Outcome statement: define and enforce a periodic recency requirement for sink evidence, independent of sink-routing file edits.
- Why now: current `AR-C15` guardrail is change-triggered; operational recency can still drift silently without a standing policy.
- Implementation surface:
  - `Docs/manifest/11_ci.md`
  - `Docs/reference/release_workflow.md`
  - `Docs/implementation/checklists/06_release_readiness.md`
  - `.github/workflows/ci.yml`
- Integration dependencies:
  - existing docs guardrail patterns
  - release-readiness evidence checks
- Testing strategy:
  - guardrail/verification command path for recency threshold
  - explicit pass/fail examples in status/worklog evidence
- Observability/release/doc updates needed:
  - add recency threshold and escalation ownership to release policy docs
  - map verification command(s) into CI/release-readiness documentation
- Done signal: recency policy is explicit, testable, and referenced by release sign-off flow.

### DIR-24: Sink-failure troubleshooting signatures

- Outcome statement: add concrete sink-failure signatures and first-response actions for maintainers/release owners.
- Why now: policy is documented, but failure triage remains overly implicit and can slow incident resolution.
- Implementation surface:
  - `Docs/reference/release_workflow.md`
  - `Docs/manifest/11_ci.md`
  - `Docs/implementation/checklists/06_release_readiness.md`
- Integration dependencies:
  - existing severity/ownership policy (`AR-C13`)
  - sink publish report artifacts (`CMD-40` outputs)
- Testing strategy:
  - docs grep verification for required signature categories and response steps
- Observability/release/doc updates needed:
  - add troubleshooting table with error signatures, likely causes, and first actions
  - cross-link from release-readiness checks
- Done signal: troubleshooting matrix exists and is linked from release-readiness references.

## Packeting Plan

### Now (appetite: small)

1. `DIR-24` via `prompt-11` (publish sink-failure troubleshooting signature matrix and first-response playbook).

### Next (appetite: small)

1. `prompt-03-alignment-review-gate` checkpoint after `DIR-24` docs follow-through.

### Not now (appetite: small)

1. Additional governance hardening beyond `AR-C18` until troubleshooting signatures are in place.

## Execution Update (2026-02-09)

- Executed `prompt-02-app-development-playbook` follow-through to enforce `DIR-23` / `AR-C17` periodic sink-evidence recency policy.
- Enforcement now runs through:
  - weekly CI job `sink-evidence-recency-gate` (`schedule` Monday UTC `0 8 * * 1`)
  - release sign-off preflight step in `release-tag-gate`
  - runbook command path `CMD-41` (`make check-sink-evidence-recency`) backed by `scripts/check_sink_evidence_recency.py` and `tests/unit/test_sink_evidence_recency.py`
- Active roadmap now: `Now=DIR-24`, `Next=prompt-03 checkpoint`, `Not now=post-AR-C18 expansion`.
- Next non-redundant execution packet is `prompt-11-docs-diataxis-release` for `DIR-24` / `AR-C18`.

## Assumptions and Constraints

- Assumption: remote GitHub Actions runs remain accessible for objective/snapshot evidence capture.
- Assumption: release governance continues treating objective/release sink evidence as fail-closed at sign-off level.
- Constraint: no authority-boundary or evidence-immutability changes are in scope.
