# Improvement Directions Report

Date: 2026-02-09
Prompt packet: `prompt-14-improvement-direction-bet-loop`
Triggering delta: fresh `prompt-03` checkpoint confirmed M7 `AR-C01`..`AR-C05` are implemented locally; remaining risk shifted to remote CI evidence freshness and warning-noise signal quality.
Objective anchor: `Docs/manifest/00_overview.md#Core Objective`

## Current-State Snapshot (Evidence-Backed)

AGORA remains aligned to the core objective. The highest-value next work is now post-implementation closure: remote CI evidence capture for newly added jobs, plus warning-signal quality hardening across broader suites.

| Dimension | Current State | Evidence |
|---|---|---|
| Objective alignment | `ALIGNED_WITH_RISKS` with residual risk focused on evidence freshness, not architecture drift | `Docs/implementation/checklists/07_alignment_review.md`, `Docs/implementation/reports/alignment_review.md` |
| Capability coverage | M7 corrections `AR-C01`..`AR-C05` are implemented locally | `Docs/implementation/checklists/02_milestones.md` |
| CI posture | Release tag and nightly full-e2e jobs exist; mappings are documented | `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`, `Docs/reference/release_workflow.md` |
| Evidence freshness | First remote pass evidence is still missing for `release-tag-gate`, `cmd-13-nightly-full-suite`, and Dash quality job | `Docs/implementation/checklists/07_alignment_review.md`, `Docs/manifest/11_ci.md` |
| Test signal quality | `CMD-27` and `CMD-13` warning budgets are now enforced; integration warning volume (`CMD-25` path) remains comparatively noisy and unbounded | `Docs/implementation/03_worklog.md`, `Docs/manifest/10_testing.md`, local command evidence in status/worklog |
| Release posture | Fail-closed release path implemented with evidence artifact upload | `.github/workflows/ci.yml` (`release-tag-gate`), `Docs/reference/release_workflow.md` |
| Planning hygiene | Trigger-aware `prompt-03` loop discipline exists and is CI-guarded | `.github/workflows/ci.yml` docs-guardrail, `Docs/implementation/checklists/07_alignment_review.md` |

## Opportunity Inventory

| ID | Direction | Type | Evidence | Gap | Impact | Confidence | Effort | Deferral Risk | Suggested Prompt Chain |
|---|---|---|---|---|---|---|---|---|---|
| DIR-14 | Capture first remote CI evidence for release/nightly/Dash jobs | Evidence freshness | `Docs/implementation/checklists/07_alignment_review.md`, `Docs/manifest/11_ci.md` | No remote run references are recorded for newly added jobs | H | H | S | H | `prompt-02` -> `prompt-11` -> `prompt-03` |
| DIR-15 | Expand warning-signal governance beyond `CMD-27` | Test signal quality | `Docs/implementation/00_status.md`, `Docs/implementation/03_worklog.md`, `Docs/manifest/10_testing.md` | `CMD-13` is now budgeted, but broader integration warning noise (`CMD-25`) remains unbounded | M | H | M | M | `prompt-10` -> `prompt-02` -> `prompt-03` |
| DIR-16 | Add CI runtime/flake budget policy for heavy nightly/release jobs | Operability | `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md` | New heavy jobs exist, but runtime/flake budget and fallback policy are not explicit | M | M | M | M | `prompt-02` -> `prompt-11` -> `prompt-03` |
| DIR-17 | External observability sink + paging integration | Operability | `Docs/manifest/07_observability.md`, `Docs/manifest/11_ci.md` | CI artifacts exist, but external dashboards/pager remain manual | M | M | L | M | `prompt-02` -> `prompt-11` -> `prompt-03` |

## Selected Directions (Top 4)

### DIR-14: Remote CI evidence closure for newly added jobs

- Outcome statement: docs include first remote passing run evidence for `release-tag-gate`, `cmd-13-nightly-full-suite`, and `cmd-37-38-dash-data-quality`.
- Why now: this is the only remaining high-impact gap after M7 implementation and is currently the top residual risk in alignment.
- Implementation surface:
  - `Docs/manifest/11_ci.md`
  - `Docs/reference/release_workflow.md`
  - `Docs/implementation/checklists/06_release_readiness.md`
  - `Docs/implementation/00_status.md`
  - `Docs/implementation/03_worklog.md`
- Integration dependencies: one pushed/tagged/dispatch CI cycle that exercises the three jobs.
- Testing strategy: evidence capture via run IDs/artifact names + command-map cross-check in docs.
- Observability/release/doc updates needed: CI verification snapshot and known-gap lines updated with concrete run refs.
- Done signal: each job has at least one recorded remote pass reference and residual-risk notes are updated.

### DIR-15: Warning-signal hardening beyond `CMD-27`

- Outcome statement: define and enforce warning-budget policy for broader suites (`CMD-25` and/or `CMD-13`) or reduce baseline warnings to an agreed threshold.
- Why now: current warning volumes reduce regression signal quality even when tests are green.
- Implementation surface:
  - `scripts/` (budget parser/check helper, if adopted)
  - `Makefile`
  - `.github/workflows/ci.yml`
  - `Docs/manifest/10_testing.md`
  - `Docs/manifest/11_ci.md`
- Integration dependencies: stable warning extraction and explicit ownership for warning policy changes.
- Testing strategy: prove both threshold-pass and threshold-fail paths with deterministic command evidence.
- Observability/release/doc updates needed: testing policy + CI known-gap section with budget rationale.
- Done signal: broader warning governance exists with automated enforcement or documented bounded exceptions.

### DIR-16: Runtime/flake budget policy for nightly/release jobs

- Outcome statement: codify runtime and retry/flake budget for `cmd-13-nightly-full-suite` and `release-tag-gate`.
- Why now: heavier jobs can become unreliable/slow without explicit budget ownership and escalation policy.
- Implementation surface:
  - `.github/workflows/ci.yml`
  - `Docs/manifest/11_ci.md`
  - `Docs/reference/release_workflow.md`
  - `Docs/implementation/checklists/06_release_readiness.md`
- Integration dependencies: CI artifact publication and observability snapshot signals.
- Testing strategy: add policy checks and verify behavior on timeout/retry scenarios where applicable.
- Observability/release/doc updates needed: release workflow section for runtime SLAs and fallback decision path.
- Done signal: explicit runtime/flake policy is documented and reflected in CI job behavior.

### DIR-17: External observability sink/paging integration

- Outcome statement: wire CI/objective/observability outputs into an external dashboard/paging channel.
- Why now: final operability maturity gap after major CI hardening.
- Implementation surface:
  - observability scripts and CI publish steps
  - `Docs/manifest/07_observability.md`
  - `Docs/manifest/11_ci.md`
- Integration dependencies: destination system selection and credentials management.
- Testing strategy: dry-run notification path and incident-playbook verification.
- Observability/release/doc updates needed: on-call routing and escalation docs.
- Done signal: at least one external sink receives and displays/publishes the key signals.

## Packeting Plan

### Now (appetite: small)

1. DIR-14: remote CI evidence closure (`AR-C06` + `AR-C07` + `AR-C08`).
2. DIR-15: warning-signal hardening design + first bounded implementation slice (`AR-C09`).

### Next (appetite: medium)

1. DIR-16: runtime/flake policy for nightly/release jobs.

### Not now (appetite: large)

1. DIR-17: external observability sink/paging integration.

Execution update (2026-02-09):

- Previous `Now` packet (`DIR-08` + `DIR-09` + `DIR-10`) is complete.
- Previous `Next` packet (`DIR-11` + `DIR-13`) is now complete via M7 implementation.
- New active `Now` packet is remote evidence closure + warning-signal hardening (`DIR-14` + `DIR-15`).
- `prompt-02` follow-through completed `DIR-15` (`AR-C09`) by enforcing a full-e2e warning budget (`E2E_FULL_WARNING_BUDGET=200`) in Make + CI.
- Active `Now` packet is now narrowed to `DIR-14` (remote CI evidence closure).

## Assumptions and Constraints

- Assumption: remote CI evidence can be captured in the next push/dispatch cycle without additional architecture changes.
- Assumption: warning-budget expansion should be incremental to avoid brittle false positives.
- Constraint: no authority-boundary or evidence immutability changes are proposed in this planning packet.
