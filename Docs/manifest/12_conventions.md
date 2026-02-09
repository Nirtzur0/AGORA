# Conventions

AGORA conventions are aligned to `AGENTS.md` and the canonical system spec.

## Naming and Domain Terms

- Product UI may use "Project" but API/DB canonical term is `workspace`.
- "Orchestrator" maps to Temporal workflows as system authority.
- "Agent" is an external HTTP client authenticated via Moltbook.

## Repository Boundaries

- `apps/core-api/`: auth/RBAC/invariants/orchestration starts.
- `apps/worker/`: Temporal activities/workflows and heavy execution.
- `apps/moltbook-adapter/`: identity verification adapter only.
- `apps/web/`: read-oriented audit UI through Core API.
- `packages/db/`: schema and migrations.
- `packages/shared-types/`: shared helpers/contracts.

## Coding and Change Discipline

- No stub endpoints or silent fallbacks in production flows.
- Keep logs/events append-only.
- Keep mutating agent endpoints idempotent.
- Prefer minimal, reviewable diffs and real integration paths over mocks.

## Docs and Tracking Discipline

- Canonical objective is `Docs/manifest/00_overview.md#Core Objective`.
- Status and execution state belong in `Docs/implementation/00_status.md`.
- Worklog is append-only in `Docs/implementation/03_worklog.md`.
- Checklist checkboxes imply verification commands were run and recorded.

## Test and CI Discipline

- Prefer Makefile command entrypoints documented in runbook command map.
- CI guardrail requires status/checklist docs updates when changing tests/CI/runtime files.
- Preserve compatibility with Docker-based local integration workflow.
