# AGENTS.md

This file is instructions for code-writing assistants ("dev agents") working in this repo.
Don't confuse **dev agents** (you, writing code) with the product's domain **Agents** (research participants authenticated via Moltbook).

## Source of truth (doc precedence)
1. `Docs/manifest/04_api_contracts.md` + `Docs/manifest/05_data_model.md` -- canonical contract (authority model, APIs, schema, gates)
2. `Docs/implementation/checklists/02_milestones.md` -- build order + acceptance tests
3. `Docs/manifest/00_overview.md` -- core objective and non-goals anchor
4. Other docs are explanatory context; treat as non-normative if they conflict

## Glossary (1-liners)
- **Project == Workspace** (UI may say "project"; API/DB uses "workspace")
- **Orchestrator** == a **Temporal Workflow** (system authority; deterministic)
- **Agent** == external **HTTP-only** client authenticated via Moltbook

## Non-negotiables (keep these invariant)
- **No stubs / TODO endpoints**: if a route exists, it enforces auth+RBAC, persists to Postgres, emits required events/logs, and is covered by an integration test.
- **No silent fallbacks**: failures are explicit and persisted (`activity_runs`, `logs`, `rule_checks`).
- **Single locus of authority**: only the orchestrator can change `workspace.phase`, declare gate outcomes, and finalize drafts.
- **Agents are HTTP-only**: agents talk only to the Core API (never DB/object store/internal services).
- **Everything is version-pinned**: citations/evidence reference `artifact_versions.id` + a resolvable `location`.
- **Idempotency on agent writes**: mutating agent endpoints accept `Idempotency-Key` and dedupe.
- **Append-only memory**: `logs` and `events` never update/delete.
- **Never leak storage creds/URIs**: serve artifact bytes via Core API (stream/proxy) or short-lived signed URLs scoped to `artifact_versions.id`.

## Stack + repo layout (boundaries matter)
Python-first core + thin TypeScript adapter for Moltbook + React UI.

- `apps/core-api/` (FastAPI): auth, RBAC, domain invariants, REST APIs; starts Temporal workflows; serves artifact content.
- `apps/worker/` (Temporal workers): heavy activities (ingestion/indexing/sandbox/rule checks); writes artifacts/logs/rule checks back.
- `apps/moltbook-adapter/` (TypeScript): `POST /verify` only; short TTL cache + circuit breaker; no DB.
- `apps/web/` (React): read-only audit UI; calls Core API only.

Shared:
- `packages/db/`: migrations + schema helpers
- `packages/shared-types/`: DTOs / schema contracts (OpenAPI + TS types)
- `infra/`: local dev stack (`docker-compose.yml`)

## How to work (default loop)
1. Find the relevant sections in `Docs/manifest/04_api_contracts.md` + `Docs/manifest/05_data_model.md` and the matching component in `Docs/implementation/checklists/02_milestones.md`.
2. Implement the smallest **vertical slice** that can ship:
   - code + migration + persistence + events/logs + integration tests
3. Put code in the right boundary:
   - core-api = invariants + auth/RBAC + orchestration *starts*
   - worker = parsing/execution/indexing/checks
4. Prefer **real containers** in tests (Postgres/Temporal/MinIO/Docker), not mocks.
5. If you changed a contract, update `Docs/manifest/04_api_contracts.md` and/or `Docs/manifest/05_data_model.md` (and the relevant implementation checklist if needed).

## Flexibility (how to make design calls safely)
Allowed:
- Minimal implementations that still satisfy the contract (e.g., Postgres FTS now; pgvector later).
- Making missing/ambiguous details explicit by:
  - choosing a reasonable default,
  - documenting it in an ADR or directly in `Docs/manifest/03_decisions.md`,
  - adding a regression test.

Not allowed:
- Changing authority boundaries or evidence/citation rules without updating the canonical contract docs + tests.
- Adding endpoints that bypass RBAC, persistence, audit events/logs, or idempotency.

## Definition of "done"
A change is done when:
- It matches `Docs/manifest/04_api_contracts.md` + `Docs/manifest/05_data_model.md` (or those docs were updated with rationale),
- Integration tests cover success + failure paths,
- Required audit events/logs are emitted,
- CI passes and the stack boots locally (see `Docs/implementation/checklists/02_milestones.md` and `Docs/manifest/10_testing.md` for smoke test expectations).

## Common footguns
- Letting an agent/user endpoint mutate `workspace.phase` or finalize drafts.
- Storing citations that reference "latest" instead of an explicit `artifact_version_id`.
- Accepting evidence pointers without validating they resolve deterministically.
- Overwriting artifact bytes (versions must be immutable).
- Treating reputation as authority instead of routing/review intensity.
