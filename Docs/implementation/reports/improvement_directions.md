# Improvement Directions Report

Date: 2026-02-09
Prompt packet: `prompt-02-app-development-playbook` (implementation follow-through for `DIR-18` / `AR-C12`)
Triggering delta: policy-shaping for `DIR-18` was complete; implementation and first remote sink evidence had to be captured.
Objective anchor: `Docs/manifest/00_overview.md#Core Objective`

## Current-State Snapshot (Evidence-Backed)

AGORA remains aligned to the core objective. The next highest-value work is operability hardening for heavy CI/release flows, not additional feature surface.

| Dimension | Current State | Evidence |
|---|---|---|
| Objective alignment | `ALIGNED_WITH_RISKS`; residual risk is CI/release operability policy, not authority-model drift | `Docs/implementation/checklists/07_alignment_review.md`, `Docs/implementation/reports/alignment_review.md` |
| Capability coverage | M8 outcomes `AR-C06`..`AR-C09` are complete (`DIR-14` and `DIR-15` closed) | `Docs/implementation/checklists/02_milestones.md`, `Docs/implementation/checklists/03_improvement_bets.md` |
| CI posture | Release/nightly/Dash/UI-smoke gates are implemented and have passing remote evidence (`21811670648`, `21811670116`, `21812201997`) | `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`, `Docs/implementation/03_worklog.md` |
| Runtime/flake governance | Runtime/flake policy is codified for heavy jobs (`AR-C10`) with explicit timeout/retry/target rules and release-blocking enforcement | `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`, `Docs/reference/release_workflow.md`, `Docs/implementation/checklists/06_release_readiness.md` |
| Operability telemetry | Runtime/flake trend telemetry is now published per heavy run (`AR-C11`) as dashboard + JSON/JSONL artifacts for nightly/release gates | `.github/workflows/ci.yml`, `scripts/build_ci_runtime_trend.py`, `Docs/manifest/07_observability.md`, `Docs/manifest/11_ci.md` |
| External routing | External sink publish path is implemented with fail-open controls; first remote active-mode evidence is captured | `.github/workflows/ci.yml`, `scripts/publish_observability_sink.py`, `Docs/manifest/11_ci.md` |
| Planning hygiene | Trigger-aware `prompt-03` loop and docs guardrail are active; next packet should be fresh alignment rerank after `DIR-18` closure | `.github/workflows/ci.yml`, `Docs/implementation/checklists/07_alignment_review.md` |

## Opportunity Inventory

| ID | Direction | Type | Evidence | Gap | Impact | Confidence | Effort | Deferral Risk | Suggested Prompt Chain |
|---|---|---|---|---|---|---|---|---|---|
| DIR-16 | Codify runtime/flake budget policy for `cmd-13-nightly-full-suite` and `release-tag-gate` | Operability | `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`, `Docs/reference/release_workflow.md`, `Docs/implementation/checklists/06_release_readiness.md` | Closed (2026-02-09): policy codified via `AR-C10` | H | H | M | L | `prompt-02` -> `prompt-11` -> `prompt-03` |
| DIR-17 | Add CI runtime+flake trend artifact for nightly/release jobs | Observability | `.github/workflows/ci.yml`, `scripts/build_ci_runtime_trend.py`, `Docs/manifest/07_observability.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/checklists/06_release_readiness.md` | Closed (2026-02-09): trend bundle artifact (`latest.json`, `history.jsonl`, `dashboard.md`) is published for heavy nightly/release jobs via `AR-C11` | M | M | M | M | `prompt-02` -> `prompt-10` -> `prompt-03` |
| DIR-18 | Route CI/objective observability to external dashboard/paging surface | Operability | `.github/workflows/ci.yml`, `scripts/publish_observability_sink.py`, `Docs/manifest/11_ci.md`, `Docs/reference/release_workflow.md` | Closed (2026-02-09): sink delivery implemented with first remote active-mode evidence (`run 21813367976`) | M | M | L | M | `prompt-11` -> `prompt-02` -> `prompt-03` |

## Selected Directions (Top 3)

### DIR-16: Runtime/flake policy for nightly/release jobs (Completed)

- Outcome statement: release/nightly CI jobs have explicit runtime targets, retry/flake budget, and promotion-blocking/fallback policy.
- Why now: this is the highest residual risk after `DIR-14`/`DIR-15` closure and UI smoke stabilization.
- Implementation surface:
  - `.github/workflows/ci.yml`
  - `Docs/manifest/11_ci.md`
  - `Docs/reference/release_workflow.md`
  - `Docs/implementation/checklists/06_release_readiness.md`
  - `Docs/implementation/checklists/02_milestones.md`
- Integration dependencies: existing `release-tag-gate` and `cmd-13-nightly-full-suite` jobs plus release-readiness sign-off flow.
- Testing strategy: policy-level grep checks + workflow YAML validation + one remote run reference that demonstrates policy fields are applied.
- Observability/release/doc updates needed: CI job sections include timeout/retry/flake notes; release checklist requires policy compliance before sign-off.
- Done signal: runtime/flake policy is explicit, auditable, and linked from both CI and release-readiness docs. (Met on 2026-02-09 via `AR-C10`.)

### DIR-17: Runtime+flake trend telemetry for heavy jobs (Completed)

- Outcome statement: nightly/release runs publish a compact runtime/flake trend artifact and dashboard summary for operational drift review.
- Why now: policy tuning for `DIR-16` is weak without trend data from actual runs.
- Implementation surface:
  - `.github/workflows/ci.yml`
  - `scripts/` trend synthesis helper
  - `Docs/manifest/07_observability.md`
  - `Docs/manifest/11_ci.md`
  - `Docs/implementation/checklists/06_release_readiness.md`
- Integration dependencies: stable artifact publication path and deterministic parsing of job durations/retries.
- Testing strategy: deterministic fixture test for trend synthesis + CI artifact upload assertion + docs command mapping update.
- Observability/release/doc updates needed: add trend signal ownership and escalation threshold to observability/release docs.
- Done signal: release/nightly runs emit a queryable trend artifact with documented interpretation and ownership. (Met on 2026-02-09 via `AR-C11`.)

### DIR-18: External observability sink/paging integration

- Outcome statement: key CI observability outputs are mirrored to at least one external dashboard/paging destination.
- Why now: remaining maturity gap once in-repo policy and trend signals are stable.
- Implementation surface:
  - `.github/workflows/ci.yml`
  - observability publish scripts
  - `Docs/manifest/07_observability.md`
  - `Docs/manifest/11_ci.md`
  - `Docs/reference/release_workflow.md`
- Integration dependencies: destination selection and scoped credentials (incident routing policy is now documented).
- Testing strategy: dry-run publish path with deterministic payload + first remote evidence run.
- Observability/release/doc updates completed in shaping packet:
  - owner roles + severity mapping + fallback policy are documented in:
    - `Docs/manifest/07_observability.md`
    - `Docs/manifest/11_ci.md`
    - `Docs/reference/release_workflow.md`
    - `Docs/implementation/checklists/06_release_readiness.md`
- Done signal: one external sink receives CI signals and is referenced by remote run evidence in release-readiness docs. (Met on 2026-02-09 via run `21813367976`.)

## Packeting Plan

### Now (appetite: small)

1. Fresh `prompt-03` checkpoint to rerank residual risk after `DIR-18` closure.

### Next (appetite: medium)

1. None (await `prompt-03` rerank output).

### Not now (appetite: medium)

1. None.

Execution update (2026-02-09):

- `prompt-02` follow-through implemented external sink publishing in:
  - `objective-metrics-gate`
  - `cmd-13-nightly-full-suite`
  - `release-tag-gate`
- first remote active-mode sink evidence is captured in run `21813367976` (`cmd-13-nightly-full-suite`, job `62929945541`) with report status `pass`.
- next non-redundant execution packet is `prompt-03-alignment-review-gate` for post-`DIR-18` rerank.

## Assumptions and Constraints

- Assumption: runtime/flake policy can be documented and enforced without introducing new infrastructure.
- Assumption: trend telemetry can start with CI artifact retention before external sink integration.
- Constraint: no authority-boundary or evidence-immutability changes are in scope for this planning packet.
