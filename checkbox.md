# Repo Audit Checklist (Prompt-07)

## Project Intent vs Reality

- [x] What the project claims to be.
  - AGORA claims to be an evidence-first, auditable research system with immutable artifacts and deterministic orchestration (`README.md`, `Docs/04-system-implementation-spec.md`).
- [x] What it actually provides.
  - Core API with auth/RBAC/workspace/artifact/claim/draft/rule/task/search routes (`apps/core-api/main.py`, `apps/core-api/*_routes.py`).
  - Temporal worker and workflows for ingestion and orchestration activities (`apps/worker/*.py`).
  - Moltbook adapter service for token verification (`apps/moltbook-adapter/src/server.ts`, `apps/moltbook-adapter/src/verifier.ts`).
  - Read-oriented web UI (`apps/web/src/App.jsx`, `apps/web/src/main.jsx`).
  - Persistent schema and migrations for core objects (`packages/db/migrations/001_initial_schema.py`).
- [ ] Top 3 alignment risks.
  - Risk 1: CI does not enforce full test matrix (`.github/workflows/ci.yml`, `Makefile`).
  - Risk 2: Architecture coherence and alignment gate checklists are missing (`Docs/implementation/checklists/00_architecture_coherence.md`, `Docs/implementation/checklists/07_alignment_review.md`).
  - Risk 3: Release discipline artifacts are incomplete (no `CHANGELOG.md`, no explicit release-readiness checklist in place).

## Logic / Algorithm Alignment & Output Quality

- [x] Identify the core logic entry points and where they live.
  - HTTP entrypoint: `apps/core-api/main.py`
  - Workflow/activity runtime: `apps/worker/main.py`, `apps/worker/*workflow*.py`, `apps/worker/*activities*.py`
  - Identity verification boundary: `apps/moltbook-adapter/src/server.ts`
- [ ] Algorithm/logic alignment vs docs promises.
  - Partial alignment: core contracts exist, but some worker comments still indicate placeholder dependency wiring (`apps/worker/main.py`).
- [x] Output schema and semantics are defined.
  - DB outputs in `packages/db/migrations/001_initial_schema.py` and corresponding route payload models in `apps/core-api/*_routes.py`.
- [ ] Correctness signals are complete.
  - Partial: unit/integration/e2e suites exist (`tests/`), but CI only runs smoke + stubs guard (`.github/workflows/ci.yml`).
- [ ] Completeness of failure handling and edge paths.
  - Partial: many explicit checks exist, but architecture/alignment gate docs and release discipline are not yet complete (`Docs/implementation/checklists/02_milestones.md`).
- [ ] Interpretability of outputs.
  - Partial: README and Docs explain many workflows, but final user-facing troubleshooting/upgrade guidance is still thin (`README.md`, `Docs/NEXT_STEPS.md`).

## User Journeys (Happy Paths)

### New user: install -> run minimal example -> understand outputs

- [x] What works today.
  - Setup and local boot path are documented (`README.md`, `setup.sh`, `Makefile`, `infra/README.md`).
- [ ] What is missing or fragile.
  - Multiple setup paths and environment assumptions can still be confusing; debug mode behavior for auth is local-only and easy to misinterpret (`infra/docker-compose.yml`, `README.md`).
- [ ] Concrete next step(s).
  - Add a single "golden path" onboarding + failure troubleshooting page linked from `Docs/INDEX.md`.

### Power user: configure -> run end-to-end -> interpret results

- [x] What works today.
  - APIs for workspace/artifact/claim/draft/rule workflows are implemented (`apps/core-api/*_routes.py`).
- [ ] What is missing or fragile.
  - Observability is mostly logs/tables and lacks centralized SLO/alerts (`Docs/manifest/07_observability.md`).
- [ ] Concrete next step(s).
  - Add reliability acceptance checks in milestones and implement alert/metrics strategy for critical flows.

### Contributor: run tests -> make change safely -> validate

- [x] What works today.
  - Makefile test targets and docs guardrail exist (`Makefile`, `.github/workflows/ci.yml`).
- [ ] What is missing or fragile.
  - CI does not run full integration/e2e quality gates by default.
- [ ] Concrete next step(s).
  - Expand CI job matrix to include unit + integration + selected e2e smoke checks.

## Missing "Product" Pieces

- [ ] Installation story: **Partial**
  - Evidence: `README.md`, `infra/README.md`; still multiple overlapping paths.
- [ ] Hello world/minimal reproducible example: **Partial**
  - Evidence: curl examples exist in `README.md`; no single scripted end-to-end golden scenario report.
- [ ] Config/story coherence: **Partial**
  - Evidence: config in `apps/core-api/config.py`, infra env docs in `infra/README.md`; prod/local split not strongly codified.
- [ ] Reproducibility (pinning/seeds/deterministic modes/versioning): **Solid**
  - Evidence: immutable artifact versions and evidence pinning in spec + schema (`Docs/04-system-implementation-spec.md`, `packages/db/migrations/001_initial_schema.py`).
- [ ] Observability: **Partial**
  - Evidence: logs/events/rule checks present; no central metrics/alerts stack (`Docs/manifest/07_observability.md`).
- [ ] Output validation: **Partial**
  - Evidence: tests and rules exist; need stronger CI enforcement and explicit release gates (`tests/`, `.github/workflows/ci.yml`, `Docs/implementation/checklists/02_milestones.md`).
- [ ] Documentation structure: **Solid**
  - Evidence: `Docs/INDEX.md`, manifest + implementation trees now present.
- [ ] Testing strategy: **Partial**
  - Evidence: strategy documented (`Docs/manifest/10_testing.md`) but CI coverage remains limited.
- [ ] Packaging/release: **Missing**
  - Evidence: no `CHANGELOG.md`; no explicit release-readiness checklist currently active.
- [ ] Security/safety basics: **Partial**
  - Evidence: auth/RBAC and boundary rules exist; key rotation/rate limiting hardening not complete (`Docs/manifest/06_security.md`).
- [ ] Dependency/tooling stack coherence: **Partial**
  - Evidence: Python + Node stacks defined (`requirements*.txt`, `package.json`), but category-level inventory and bespoke-vs-buy notes are not yet centralized.

- [ ] Dependency inventory (key libs/tools + usage) is explicitly documented.
  - Evidence needed from: `apps/core-api/requirements*.txt`, `apps/worker/requirements.txt`, `apps/moltbook-adapter/package.json`, `apps/web/package.json`.
- [ ] Category map for dependencies is complete.
  - Target categories: packaging, config, logging, validation/contracts, testing, CI/release, orchestration, DB/migrations, observability, security.
- [ ] Bespoke vs buy duplications are reviewed and reduced.
  - Candidate review areas: custom DB/storage helpers and workflow wrappers.

- [ ] Packaging/release remediation outcomes.
  - Add `CHANGELOG.md` discipline.
  - Add versioning policy doc.
  - Add release checklist and upgrade-notes template.
  - Map release workflow to CI/tag strategy.

- [ ] Observability remediation outcomes.
  - Expand `Docs/manifest/07_observability.md` with log schema and redaction policy.
  - Define metrics/tracing per critical workflow.
  - Define golden signals (`latency`, `traffic`, `errors`, `saturation`).
  - Define SLI/SLO alert thresholds and severity routing.
  - Add debug playbook with common incident triage.

## Architecture & Boundaries

- [x] Separation of concerns is mostly clear.
  - Evidence: repo boundaries in `AGENTS.md`, service folders under `apps/`.
- [ ] Coupling points that will cause pain.
  - Worker startup and dependency wiring are still somewhat ad-hoc (`apps/worker/main.py`).
- [ ] Missing boundaries.
  - Need clearer documented boundary for architecture coherence gate enforcement artifact (`Docs/implementation/checklists/00_architecture_coherence.md` missing).
- [ ] Architecture diagram drift check.
  - New architecture doc exists, but no periodic drift gate is yet implemented as checklist automation.

- [ ] High-impact recommendations.
  - Add architecture coherence checklist and enforce GO/GO_WITH_RISKS before major build packets.
  - Expand CI to include integration matrix and at least one e2e smoke path.
  - Add release-readiness artifacts (changelog/versioning/release checklist).
  - Harden worker dependency lifecycle and remove placeholder comments.
  - Add alignment review checklist and periodic prompt-03 checkpoints.

## UI/UX (If Applicable)

- [x] UI surface and launch path identified.
  - Evidence: `apps/web/`, `apps/web/package.json`, `README.md` local dev instructions.
- [ ] UX-to-logic alignment is complete.
  - Partial evidence: UI calls Core API, but full critical-flow map and failure-state UX checks are limited.
- [ ] Output presentation clarity is complete.
  - Need explicit acceptance criteria around error/empty states in UI verification loops.
- [ ] UX footguns are fully mitigated.
  - Potential hidden prerequisites: local services/env vars and debug token mode assumptions.

## Consistency & Maintenance Risks

- [ ] Dead/unused entrypoints review is complete.
- [ ] Conflicting docs vs code review is complete.
  - Risk: legacy references to `docs/` vs canonical `Docs/` paths still appear in older docs.
- [ ] Duplicate configs review is complete.
- [ ] Works-on-my-machine assumptions are eliminated.
  - Risk: heavy dependence on local Docker/runtime setup.
- [ ] Hidden prerequisites are fully documented.

## Prioritized Next Steps

### P0 (must fix to avoid misleading users)

- [ ] Outcome: CI enforces unit + integration gates in addition to smoke/stub checks.
  - Owner: maintainer
  - Effort: M
  - Evidence: `.github/workflows/ci.yml`, `Makefile`, `Docs/manifest/11_ci.md`
- [ ] Outcome: architecture coherence checklist exists and is used for GO/GO_WITH_RISKS gate before major changes.
  - Owner: maintainer
  - Effort: S
  - Evidence: missing `Docs/implementation/checklists/00_architecture_coherence.md`
- [ ] Outcome: alignment review checklist is added and kept current.
  - Owner: maintainer
  - Effort: S
  - Evidence: missing `Docs/implementation/checklists/07_alignment_review.md`

### P1 (should fix to enable adoption)

- [ ] Outcome: release-discipline artifacts are present (changelog/versioning/release checklist/upgrade notes).
  - Owner: maintainer
  - Effort: M
  - Evidence: missing release discipline artifacts; tracked in milestones.
- [ ] Outcome: observability plan includes metrics/SLO/alerts and triage playbook additions.
  - Owner: maintainer
  - Effort: M
  - Evidence: `Docs/manifest/07_observability.md` currently marks central metrics/alerts as gaps.
- [ ] Outcome: worker runtime dependency lifecycle is hardened and documented.
  - Owner: maintainer
  - Effort: M
  - Evidence: placeholder notes in `apps/worker/main.py`.

### P2 (nice-to-have polish)

- [ ] Outcome: dependency category inventory and bespoke-vs-buy mapping are documented in one place.
  - Owner: contributor
  - Effort: M
  - Evidence: dependency files exist but no unified category map.
- [ ] Outcome: onboarding includes a single scripted end-to-end golden demo.
  - Owner: contributor
  - Effort: S
  - Evidence: current README has examples but no single deterministic demo script.

## Prompt-00 Handoff (Required)

- [ ] Top P0 outcomes to copy into `Docs/implementation/checklists/02_milestones.md`.
  - CI matrix expansion (unit + integration enforcement).
  - Architecture coherence checklist creation/use.
  - Alignment review checklist creation/use.
- [ ] Top P1 outcomes to copy into `Docs/implementation/checklists/02_milestones.md`.
  - Release discipline artifact set.
  - Observability metrics/SLO/alert playbook expansion.
  - Worker dependency lifecycle hardening.
- [ ] Architecture drift outcomes to copy into `Docs/implementation/checklists/00_architecture_coherence.md` (if used).
  - Add periodic diagram-vs-code drift checks and readiness verdict tracking.
- [ ] Packaging/release outcomes to implement via `prompt-11-docs-diataxis-release.md`.
  - `CHANGELOG.md`, versioning policy, release checklist, upgrade notes template.
- [ ] Observability/reliability outcomes to implement via `prompt-02-app-development-playbook.md` gate.
  - metrics/tracing mapping, golden signals, SLI/SLO thresholds, debug playbook.
- [ ] For each copied outcome include target files/areas, acceptance signals, and phase.
  - CI matrix: `.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`; verify on PR checks; phase 4/5.
  - Architecture/alignment checklists: `Docs/implementation/checklists/00_architecture_coherence.md`, `Docs/implementation/checklists/07_alignment_review.md`; verify checklist + status updates; phase 2/3.
  - Release artifacts: `CHANGELOG.md`, `Docs/reference/versioning_policy.md`, `Docs/implementation/checklists/06_release_readiness.md`; verify docs completeness + CI mapping; phase 5.
  - Observability expansion: `Docs/manifest/07_observability.md`, `Docs/manifest/09_runbook.md`; verify explicit SLO/alert/debug sections; phase 3.5/4.
- [ ] Recommended execution packeting.
  - First packet (1-5 items): add architecture/alignment checklists + status/worklog integration.
  - Second packet: expand CI matrix and release discipline docs.
  - Defer: dependency category inventory and onboarding polish (P2).
