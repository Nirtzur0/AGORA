# Project Plan (Prompt-02 Shape Stage)

Generated for AGORA from `prompt-02-app-development-playbook` in Standard mode.

## 1) Problem and Scope Clarification

### What the app does

AGORA is an evidence-first research collaboration system that combines immutable artifact versioning, deterministic orchestration, and an auditable API/UI surface for claims, citations, critiques, and draft finalization.

### Primary users and workflows

- External research participants (product-domain "Agents") authenticating via Moltbook.
- Workspace maintainers coordinating roles, tasks, and gate outcomes.
- Review/audit users inspecting logs, evidence, and finalization state.

### Inputs and outputs

Inputs:
- identity tokens, workspace requests, artifact bytes/metadata, claims, evidence pointers, critique payloads.

Outputs:
- persisted workspace state, versioned artifacts, audit logs/events, rule-check outcomes, draft/finalization state.

### Non-goals

- Production-grade multi-tenant operations.
- Enterprise governance and export tooling.

### Key assumptions

Tracked in `Docs/implementation/reports/assumptions_register.md`.

### Risks

- Drift between canonical spec and runtime behavior.
- Insufficient CI coverage of integration/e2e flows.
- Worker lifecycle technical debt affecting reliability under load.

## 2) Tech Stack Proposal

### Option A (Selected): simplest robust

Use existing Python-first architecture with TypeScript adapter and React UI.

### Option B: scalable/advanced

Introduce stronger cross-service contract automation and expanded CI matrix now.

Decision:
- Keep Option A for current cycle; plan targeted hardening milestones.

## 3) Architecture Source of Truth

- Canonical architecture details in `Docs/manifest/01_architecture.md`.
- API boundary contracts in `Docs/manifest/04_api_contracts.md`.
- Persistent model and invariants in `Docs/manifest/05_data_model.md`.
- Security and trust boundaries in `Docs/manifest/06_security.md`.

## 4) Project Structure and Conventions

- Structure and boundaries documented in `Docs/manifest/12_conventions.md`.
- Command map and operational workflows documented in `Docs/manifest/09_runbook.md`.
- CI mapping documented in `Docs/manifest/11_ci.md`.

## 5) Feature Breakdown -> Milestones -> Tasks

Epics:
- Epic A: Authority and gating hardening.
- Epic B: Artifact/evidence reliability.
- Epic C: UI audit confidence and release discipline.

Milestones and acceptance checks:
- tracked in `Docs/implementation/checklists/02_milestones.md`.

Epic files:
- `Docs/implementation/epics/epic_authority_and_gates.md`
- `Docs/implementation/epics/epic_artifacts_and_evidence.md`
- `Docs/implementation/epics/epic_ui_audit_and_release.md`

## 6) Testing Strategy

Test pyramid for AGORA:
- unit: fast behavior and helper checks (`make test-unit`)
- integration: DB/storage/workflow behavior (`make test-integration`)
- e2e: critical user-facing flows (`make test-e2e`)
- contract/invariant checks: schema/idempotency/evidence resolution (integration + targeted unit tests)

Current command references are canonicalized in runbook IDs `CMD-11` to `CMD-14`.

## 6.5) Observability and Reliability Gate

Critical workflow observability expectations are documented in `Docs/manifest/07_observability.md`.

Gate conditions for current cycle:
- persist explicit success/failure records for critical workflows;
- maintain triage command map in runbook;
- track gaps (metrics/alerts) as deferred milestones rather than implicit scope.

## Entry Mode and Stage

- Entry mode: Existing repo evolution.
- Current stage: Shape (legacy `phase_0`).
- Immediate next packet: Milestone M1 planning and targeted hardening selection.
