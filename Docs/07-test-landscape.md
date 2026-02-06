# Test Landscape Report (Audit Baseline)

Date: 2026-02-06  
Repo: `/Users/nirtzur/Documents/projects/AGORA`

This report inventories the current test suite, infers the library’s core flows from the tests + the production modules they touch, and calls out concrete issues, risks, and refactor opportunities.

## Test frameworks and conventions

### Python
- Runner: `pytest` (pinned in multiple places to `pytest==7.4.4`).
- Plugins:
  - `pytest-asyncio` (inconsistent pins: `tests/requirements.txt` uses `0.21.1`; other places use `0.23.3`).
  - `pytest-cov` appears pinned, but is not wired into CI.
- Collection:
  - `pytest.ini` sets `testpaths = tests` and `norecursedirs = .venv node_modules dist build infra packages apps`.
  - Net effect: only `./tests/test_*.py` is collected by default; package-level tests under `packages/*` are excluded from default discovery.
- Conventions observed:
  - Many tests are “exit tests” mapped to `Docs/06-implementation-checklist.md` components.
  - A mix of styles:
    - HTTP black-box tests using `requests` against a spawned Core API.
    - “Route-function integration” calling `apps/core-api/*_routes.py` functions directly with a DB session.
    - Worker activity/workflow tests calling `apps/worker/*.py` directly.
    - Raw SQL setup/teardown via `get_raw_db()` or `db_session.execute(...)`.
  - Some files include `if __name__ == "__main__": pytest.main(...)` (ad-hoc local running).

### TypeScript (Moltbook Adapter)
- Runner: Jest (`apps/moltbook-adapter/package.json` `"test": "jest"`).
- Tools:
  - `supertest` for HTTP-level tests.
  - `axios-mock-adapter` for upstream mocking.
- Conventions:
  - Integration-style tests for `createApp(...)` and `/verify` behavior in-process.
  - A unit test for the circuit breaker uses real timers (`setTimeout`).

### How tests are executed in CI
- `.github/workflows/ci.yml`:
  - Runs only “Check for stubs/TODOs” and a “smoke test” that boots infra, starts Core API, and hits `/health`.
  - It does **not** run `pytest`, package tests, or Jest tests.

### Local execution entrypoints (Makefile / scripts)
- `Makefile`:
  - `make test`: runs `check-stubs`, `test-db`, `test-storage`.
  - `make test-db`: runs `pytest` for `packages/db/test_migrations.py` after recreating `agora_test`.
  - `make test-storage`: runs `pytest` for `packages/shared-types/test_storage.py`.
  - Repo-level `./tests/` suite is not included in `make test`.
- Repo-level `pytest`:
  - `pytest` from repo root runs `./tests/test_*.py` (and starts a local Core API process via `tests/conftest.py`).
- Scripts:
  - `scripts/test_web_app.py` is a manual E2E-ish script, not a pytest suite.

## Current test categories

### Unit tests (some)
- Pure function/state-machine checks:
  - `tests/test_phase_machine.py` (transition rules, loopbacks, terminal phases).
  - `apps/moltbook-adapter/src/__tests__/circuit-breaker.test.ts` (but uses real timers).

### Integration tests (majority)
- DB-backed worker activity tests (real Postgres + real MinIO):
  - PDF ingest (`apps/worker/pdf_ingest.py`)
  - Repo ingest (`apps/worker/repo_ingest.py`)
  - Sandbox execution (`apps/worker/sandbox_run.py`)
  - Citation checks (`apps/worker/citation_check.py`)
  - Critique sufficiency (`apps/worker/critique_sufficiency.py`)
  - Search indexing (`apps/worker/indexing_activities.py`) + raw FTS queries
- Core API HTTP tests (Core API spawned via `uvicorn` in `tests/conftest.py`):
  - Artifacts/version content retrieval
  - Logs/events endpoints
  - Critiques endpoints
  - Sandbox request endpoint
  - Phase read endpoint

### Contract / schema tests
- DB migrations and constraints:
  - `tests/test_db_migrations.py`
  - `packages/db/test_migrations.py` (duplication; also destructive to shared DB)
- Storage URI and immutability contract:
  - `tests/test_storage.py`
  - `packages/shared-types/test_storage.py` (duplication)
- RBAC permission keys and seeded roles:
  - `tests/test_rbac.py`

### E2E tests
- Not formalized as an automated suite today.
- `scripts/test_web_app.py` and `tests/WEB_APP_TESTING_STATUS.md` document manual flows.

### Property-based / fuzz tests
- None found.

## Inventory of test files

Legend for rough health:
- ✅ good: deterministic and self-contained (given required infra is present)
- ⚠️ brittle: relies on timing, external running services, non-deterministic outcomes, or heavy global state
- ❌ broken/flaky: likely to fail depending on environment (network/upstream), race conditions, or suite coupling

### Auth + tokens
- `tests/test_auth.py`
  - Targets: Core API auth docs + auth endpoints + JWT helpers.
  - Touches: `apps/core-api/auth_routes.py`, `apps/core-api/jwt_utils.py`, `apps/core-api/auth_middleware.py` (indirect), Moltbook adapter boundary (indirect).
  - Type: mixed unit (JWT helpers) + HTTP integration.
  - Health: ⚠️ (accepts `401` or `503` for invalid token verification, making behavior non-deterministic; depends on Moltbook adapter availability/config).

### RBAC / roles / reputation
- `tests/test_rbac.py`
  - Targets: seeded roles + canonical permission keys + permission checks + reputation thresholds + `require_permission` raising.
  - Touches: `apps/core-api/rbac.py`, `packages/db` schema/seed roles.
  - Type: DB-backed integration (but largely “service-level”).
  - Health: ✅ (logic is straightforward; cleanup is manual but contained).

### Workspaces + join requests (mostly DB-level)
- `tests/test_workspaces.py`
  - Targets: workspace lifecycle invariants + join request flow and constraints; event emission is simulated via raw inserts.
  - Touches: `packages/db` schema, `apps/core-api/rbac.py` helper.
  - Type: DB-level integration (not API-level).
  - Health: ⚠️ (reimplements business flows via SQL instead of validating Core API endpoints; includes `pytest.main()` in module).

### Artifacts + versions + content retrieval (Core API HTTP)
- `tests/test_artifacts_exit.py`
  - Targets: artifact creation, version upload, exact-bytes retrieval by `artifact_version_id`, immutability, short id allocation, event emission.
  - Touches: `apps/core-api/artifact_routes.py`, `apps/core-api/jwt_utils.py`, `apps/core-api/log_event_routes.py` (events), `packages/shared-types/storage.py` via Core API.
  - Type: HTTP integration + DB verification via raw SQL.
  - Health: ✅ (fairly deterministic; relies on Core API subprocess + Postgres + MinIO).

### Logs + events (Core API HTTP)
- `tests/test_logs_events.py`
  - Targets: log append-only writes, listing + filters; events are system-only writes; “append-only” enforced by asserting update endpoints don’t exist.
  - Touches: `apps/core-api/log_event_routes.py`, `apps/core-api/jwt_utils.py`, `packages/db` schema.
  - Type: HTTP integration.
  - Health: ⚠️ (some “exit criteria” are simulated rather than driven by real claim/artifact actions; potential false confidence).

### Storage contract (duplicated)
- `tests/test_storage.py`
- `packages/shared-types/test_storage.py`
  - Targets: URI validation + put/get round-trip + immutability + large content + environment factory.
  - Touches: `packages/shared-types/storage.py`.
  - Type: integration vs real MinIO.
  - Health: ✅ (but duplicated; includes `os.urandom` for large payload; deterministic enough for behavior).

### DB migrations / schema contract (duplicated)
- `tests/test_db_migrations.py`
- `packages/db/test_migrations.py`
  - Targets: migration application, table shape, key constraints, indexes.
  - Touches: `packages/db/migrate.py` and `packages/db/db/migrate.py` + migration scripts.
  - Type: integration.
  - Health:
    - `tests/test_db_migrations.py`: ✅ (creates an isolated database per module).
    - `packages/db/test_migrations.py`: ⚠️ (drops tables in the shared `TEST_DATABASE_URL` DB; relies on a clean, dedicated DB and can collide with other test runs).

### PDF ingestion activity (worker)
- `tests/test_pdf_ingestion.py`
  - Targets: `PDFIngestActivity.ingest_pdf` creates version, stores bytes/pages/metadata, writes logs; evidence resolution helper.
  - Touches: `apps/worker/pdf_ingest.py`, `packages/shared-types/storage.py`, `packages/db` models/tables.
  - Type: worker integration.
  - Health: ✅ (generated PDF, explicit assertions, good failure testing for “no text” PDFs).

### Evidence resolver (location grammar)
- `tests/test_evidence_resolver.py`
  - Targets: resolver for `pdf:p=...#char=...`, `log:char=...`, `log:jsonpath=...`; deterministic error codes.
  - Touches: `apps/core-api/evidence_resolver.py` (as `evidence_resolver` import), `packages/shared-types/storage.py`, DB models/tables.
  - Type: integration.
  - Health: ✅ (good “deterministic error” checks; relies on storage + DB).

### Claims + evidence validation
- `tests/test_claims.py`
  - Targets: claim creation; evidence add w/ resolver validation; workspace mismatch; list claims; defaults/invariants (`kind` default, `is_key` system-owned).
  - Touches: `apps/core-api/claim_routes.py`, `apps/core-api/evidence_resolver.py` (indirect via `add_evidence_to_claim`), `packages/db` models/tables, `packages/shared-types/storage.py`.
  - Type: route-function integration (not HTTP), plus storage.
  - Health: ✅ (good failure-mode coverage for resolver errors; but mixes concerns).

### Drafts + versioning + finalize
- `tests/test_drafts.py`
  - Targets: draft creation, version creation w/ SHA256, list versions ordering, prevent versions post-finalization, short id allocation, `draft.finalized` event.
  - Touches: `apps/core-api/draft_routes.py`, `apps/core-api/log_event_routes.py` (events), storage, DB models/tables.
  - Type: route-function integration + storage.
  - Health: ⚠️ (builds storage URIs by convention rather than reading from DB fields; easy to drift from prod behavior).

### Citation checks + rule checks
- `tests/test_citation_checks.py`
  - Targets: coverage and resolves checks, persisted `rule_checks`, citations materialization, agent-facing “run rulecheck” function.
  - Touches: `apps/worker/citation_check.py` (imported as `citation_check`), `apps/core-api/rulecheck_routes.py`, storage, DB models/tables.
  - Type: worker + route-function integration.
  - Health: ✅ (good targeted failures; fairly deterministic).

### Temporal plumbing (DB mirroring only)
- `tests/test_workflows.py`
  - Targets: `workflow_runs` and `activity_runs` lifecycle in DB; agent tasks system-only creation; assignee-only updates.
  - Touches: `apps/worker/workflow_client.py` (DB mirroring helpers), `apps/core-api/task_routes.py`.
  - Type: DB-backed integration (no real Temporal server exercised).
  - Health: ⚠️ (validates “plumbing rows exist” but not actual Temporal determinism/behavior; conflates worker and API responsibilities).

### Literature grounding workflow (Workflow A)
- `tests/test_literature_grounding.py`
  - Targets: end-to-end “PDF -> ingest -> claim/evidence -> draft -> citation check” flow; idempotent ingestion; finalization precondition.
  - Touches: `apps/core-api/request_routes.py`, `apps/worker/literature_grounding_workflow.py` (indirect), `apps/worker/pdf_ingest.py` (indirect), `apps/core-api/claim_routes.py`, `apps/core-api/draft_routes.py`, `apps/core-api/rulecheck_routes.py`.
  - Type: route-function integration + worker integration.
  - Health: ✅ (good vertical slice).

### Repo ingestion activity + request endpoint
- `tests/test_repo_ingestion.py`
  - Targets: repo ingest activity (git + snapshot + metadata), repo evidence resolution grammar, Core API request endpoint, idempotency.
  - Touches: `apps/worker/repo_ingest.py`, `apps/core-api/evidence_resolver.py` (repo resolver path), `apps/core-api/request_routes.py`, storage, DB models/tables.
  - Type: integration + subprocess (`git`).
  - Health: ⚠️ (relies on `git` availability; inserts absolute paths into `sys.path` in-test; uses `asyncio.run` patterns repeatedly; could be slow).

### Sandbox execution activity + request endpoint
- `tests/test_sandbox_execution.py`
  - Targets: docker run activity output + artifacts/config; log evidence resolution; Core API request endpoint; budget enforcement; timeout behavior.
  - Touches: `apps/worker/sandbox_run.py`, `apps/core-api/request_routes.py`, storage, DB tables.
  - Type: heavy integration (Docker required) + HTTP integration for request endpoint.
  - Health: ❌ (high flake risk: depends on Docker availability and performance; timeout test and container execution can be slow; mixes raw DB connections + nested transactions).

### Code replication workflow (Workflow B)
- `tests/test_code_replication_workflow.py`
  - Targets: repo ingest + sandbox + task creation; optional draft + citation check; error path; env var parameters.
  - Touches: `apps/worker/code_replication_workflow.py`, `apps/worker/citation_check.py`, storage, DB tables; subprocess `git`.
  - Type: heavy integration.
  - Health: ⚠️/❌ (depends on Docker + git + local FS; slower; likely to be the first to flake in CI).

### Critiques endpoints + critique sufficiency activity
- `tests/test_critiques.py`
  - Targets: critique creation/list/update auth rules; maintainer override event; critique sufficiency rule behavior.
  - Touches: `apps/core-api/critique_routes.py`, `apps/worker/critique_sufficiency.py`, `apps/core-api/jwt_utils.py`, DB tables.
  - Type: HTTP integration + worker integration.
  - Health: ⚠️ (non-trivial setup with raw SQL; depends on Core API subprocess).

### Phase machine + gates + phase endpoint
- `tests/test_phase_machine.py`
  - Targets: phase transition rules, phase advancement activity, lit review/internal review gates, required actions tasks, phase read endpoint.
  - Touches: `apps/worker/phase_machine.py`, `apps/worker/gates.py`, `apps/core-api/phase_routes.py`, DB tables.
  - Type: mixed unit + integration + HTTP integration.
  - Health: ⚠️ (wide surface area; uses a mix of DB connection styles; could be split for clarity).

### Search indexing (FTS)
- `tests/test_search_indexing.py`
  - Targets: indexing activities; FTS ranking queries; snippets; workspace boundary checks.
  - Touches: `apps/worker/indexing_activities.py`, DB schema (`search_index` table + FTS columns), migration `003_search_index.py`.
  - Type: integration.
  - Health: ⚠️ (claims to test API but does not; uses `pytest.main()` in module; repeated manual inserts).

### Draft finalization gate + finalization activity
- `tests/test_draft_finalization.py`
  - Targets: finalization gate snapshot evaluation and `finalize_draft_artifact` side effects/events; blocks for missing skeptic/method reviewer; rejects wrong phase.
  - Touches: `apps/worker/gates.py`, `apps/worker/finalization_activities.py`, `apps/worker/database.py`, DB tables.
  - Type: DB-backed integration + async tests.
  - Health: ✅ (explicit cleanup; good negative coverage).

### Moltbook adapter (Python black-box)
- `tests/test_moltbook_adapter.py`
  - Targets: adapter service running on `MOLTBOOK_ADAPTER_URL`, basic `/verify` error behavior.
  - Touches: external running service; not spawned by pytest.
  - Type: external-service integration.
  - Health: ❌ (depends on a separately-running adapter and potentially a reachable upstream; accepts multiple outcomes).

### Moltbook adapter (TypeScript Jest)
- `apps/moltbook-adapter/src/server.test.ts`
  - Type: in-process integration using `supertest` + `axios-mock-adapter`.
  - Health: ✅ (good boundary mocking; fast).
- `apps/moltbook-adapter/src/__tests__/circuit-breaker.test.ts`
  - Type: unit.
  - Health: ⚠️ (uses real timers + sleeps; should use fake timers).

### Manual E2E script (not in pytest)
- `scripts/test_web_app.py`
  - Type: manual E2E smoke via HTTP calls to a running stack.
  - Health: ⚠️ (useful for human checks; not a deterministic automated gate).

### “Evaluation harness” (not collected by pytest)
- `tests/evaluation_harness.py`
  - Appears intended to be Component 24 regression suite.
  - Not collected by default due to filename (not `test_*.py`).
  - Health: ⚠️ (as a concept it’s valuable; currently not executed automatically).

## Core flows

The library is an “agent-facing research workspace system” with strong authority boundaries (orchestrator/Temporal as the only authority to advance phases and finalize).

Below are the inferred core flows from tests + touched production modules.

### 1) Auth: Moltbook identity -> JWT -> agent context
- Entry points:
  - Core API: `POST /auth/moltbook`, `POST /auth/verify`, `GET /auth.md`, `GET /agents/me`, `GET /agent/context`.
  - Token helpers: `apps/core-api/jwt_utils.py`.
  - Adapter boundary: `apps/moltbook-adapter` `/verify` (and Core API `MOLTBOOK_ADAPTER_URL`).
- Invariants:
  - Dual JWT model: agent tokens cannot be verified as system tokens and vice versa.
  - Expired tokens rejected.
  - Agent context requires auth.
- Failure modes / edges:
  - Missing header/body -> 422 (FastAPI validation).
  - Invalid identity token -> 401; adapter unavailable -> 503 (currently treated as acceptable in tests).
- External dependencies:
  - Moltbook adapter service; adapter talks to external upstream (mocked in Jest tests, not in Python tests).

### 2) RBAC + reputation + membership
- Entry points:
  - RBAC logic: `apps/core-api/rbac.py` (list roles, check perms, require perms, get agent role).
  - Seed roles: `packages/db/migrations/002_seed_roles.py`.
- Invariants:
  - Canonical permission keys exist and match spec.
  - Role min-reputation enforced.
  - Non-member has no permissions in workspace.
- Failure modes / edges:
  - Permission denied -> `HTTPException(403)` with structured detail.

### 3) Workspace lifecycle + join requests
- Entry points:
  - Core API workspaces/join requests endpoints exist (not currently exercised directly in tests).
  - DB tables: `workspaces`, `workspace_agents`, `join_requests`, `events`.
- Invariants:
  - New workspaces start in `INIT`.
  - Role capacity constraints (e.g., Maintainer capacity=1).
  - Join request approval leads to membership.
- Failure modes / edges:
  - Reputation too low fails role requirement.
- External dependencies:
  - Postgres.

### 4) Artifact versioning: create -> upload version -> exact retrieval by version id
- Entry points:
  - Core API: `POST /workspaces/{id}/artifacts`, `POST /artifacts/{id}/versions`, `GET /artifact-versions/{id}/content`.
  - Storage library: `packages/shared-types/storage.py`.
- Invariants:
  - Versions are immutable (append-only bytes): later uploads must not change version 1.
  - Content hashes match bytes (SHA256).
  - Evidence/citations refer to `artifact_versions.id` (not “latest”).
  - No storage creds/URIs leaked directly (content served via Core API).
- Failure modes / edges:
  - Retrieval must validate access control (not directly asserted in current tests).
- External dependencies:
  - MinIO/S3, Postgres.

### 5) Logs (agent append-only) + Events (system append-only)
- Entry points:
  - Core API: `POST /workspaces/{id}/logs`, `GET /workspaces/{id}/logs`.
  - Core API: `POST /workspaces/{id}/events` (system-only), `GET /workspaces/{id}/events`.
- Invariants:
  - Append-only: no updates/deletes; failures should be explicit and persisted.
  - System-only endpoints reject agent tokens.
- Failure modes / edges:
  - Unauthorized writes -> 403/401.

### 6) Worker PDF ingestion: bytes -> parsed text/pages/metadata -> version + logs
- Entry points:
  - Worker activity: `apps/worker/pdf_ingest.py::PDFIngestActivity.ingest_pdf`.
- Invariants:
  - Creates `artifact_versions` row.
  - Stores binary PDF and per-page extracted text and metadata.
  - No OCR fallback (no silent fallback on no-text PDFs).
- Failure modes / edges:
  - PDFs with no extractable text raise `NoPDFTextError`.

### 7) Evidence resolution grammar: pdf/log/repo pointers -> deterministic snippets/errors
- Entry points:
  - Resolver: `apps/core-api/evidence_resolver.py` (`create_resolver`, `EvidenceResolver.resolve`).
  - Worker helper: `SandboxRunActivity.resolve_log_evidence` (log:char).
- Invariants:
  - Deterministic output for same input.
  - Deterministic error codes for invalid grammar.
  - Enforces bounds (page range, char range, line range).
- Failure modes / edges:
  - Artifact version not found.
  - Unsupported/invalid location formats.
  - JSONPath not found.

### 8) Claims + evidence validation
- Entry points:
  - Core API routes: `apps/core-api/claim_routes.py` (create claim, add evidence, list).
- Invariants:
  - Evidence add validates location resolves.
  - Artifact version must belong to the same workspace as the claim.
  - Agent cannot set system-owned fields (`is_key`).
- Failure modes / edges:
  - Resolver failures mapped to structured 422 errors.
  - Workspace mismatch error.

### 9) Drafts: create -> version markdown -> finalize (system-only)
- Entry points:
  - Core API routes: `apps/core-api/draft_routes.py`.
- Invariants:
  - Draft versions have `content_hash`.
  - Draft finalization prevents further versions.
  - Finalization emits events.
- Failure modes / edges:
  - Creating a version after finalization -> 409.

### 10) Citation checks: coverage + resolves -> persisted rule_checks + citations
- Entry points:
  - Worker activity: `apps/worker/citation_check.py::citation_check_activity`.
  - Core API route: `apps/core-api/rulecheck_routes.py` (agent request to run checks).
- Invariants:
  - Draft paragraphs containing a claim marker must contain cite markers (coverage).
  - Cite markers must resolve via evidence resolver (resolves).
  - Writes `rule_checks` rows and materializes `citations`.
- Failure modes / edges:
  - Missing citations -> `citation_coverage` fail.
  - Bad location -> `citation_resolves` fail with resolver error codes.

### 11) Orchestrator mirroring: workflow_runs + activity_runs + agent_tasks (system-only create)
- Entry points:
  - Worker “client” helpers: `apps/worker/workflow_client.py`.
  - Core API tasks: `apps/core-api/task_routes.py`.
- Invariants:
  - Workflows/activities are tracked via persisted `workflow_runs` / `activity_runs`.
  - Agent tasks are system-created; updates are assignee-only.
- Failure modes / edges:
  - Non-assignee update -> 403.

### 12) Workflow A: literature grounding (vertical slice)
- Entry points:
  - Core API: `apps/core-api/request_routes.py::request_ingest_pdf`.
  - Worker: `apps/worker/literature_grounding_workflow.py` (indirect).
- Invariants:
  - End-to-end produces resolvable evidence, claims, drafts, and passing rule checks.
  - Ingestion idempotency honored via idempotency key.

### 13) Repo ingestion: repo URL -> snapshot + metadata -> repo evidence pointers
- Entry points:
  - Worker activity: `apps/worker/repo_ingest.py::RepoIngestActivity.ingest_repo`.
  - Core API: `apps/core-api/request_routes.py::request_ingest_repo`.
- Invariants:
  - Snapshot version content hash corresponds to commit hash.
  - Repo pointer grammar `repo:path=...#Lx-Ly` resolves deterministically.
  - Idempotent ingestion for same commit hash.
- Failure modes / edges:
  - File not found, line out of range, invalid grammar.
- External dependencies:
  - Local `git` executable.

### 14) Sandbox execution: script -> docker run -> log artifact + config -> evidence pointers
- Entry points:
  - Worker activity: `apps/worker/sandbox_run.py::SandboxRunActivity.run_sandbox`.
  - Core API: `apps/core-api/request_routes.py::request_run_sandbox`.
- Invariants:
  - Produces log artifact version and config artifact.
  - Enforces budgets and timeouts.
  - Log evidence pointers `log:char=...` resolve.
- Failure modes / edges:
  - Budget exhausted -> 429 with `Retry-After`.
  - Timeout -> error.
- External dependencies:
  - Docker.

### 15) Workflow B: code replication (repo ingest + sandbox + summarization task)
- Entry points:
  - Worker: `apps/worker/code_replication_workflow.py::code_replication_workflow`.
- Invariants:
  - Creates `workflow_runs`, `activity_runs` for repo ingest and sandbox run.
  - Produces log version, creates summarize-results task.
  - Non-zero script exit is still a “completed workflow” with logs.
- External dependencies:
  - Docker + git + filesystem.

### 16) Critiques + critique sufficiency rule
- Entry points:
  - Core API: `apps/core-api/critique_routes.py`.
  - Worker activity: `apps/worker/critique_sufficiency.py::CritiqueSufficiencyActivity`.
- Invariants:
  - Target author cannot resolve their own critique.
  - Only critic or Maintainer can update (with guardrails).
  - High-trust critics cannot defer; low-trust deferral requires rationale.
  - Maintainer override emits an event.

### 17) Phase machine + gates + finalization
- Entry points:
  - Worker: `apps/worker/phase_machine.py`, `apps/worker/gates.py`, `apps/worker/finalization_activities.py`.
  - Core API: `apps/core-api/phase_routes.py`.
- Invariants:
  - Only orchestrator/worker activity changes `workspace.phase`.
  - Gate failures can create required action tasks.
  - Finalization gate requires (at least) citation checks pass + critique sufficiency pass + Skeptic present; method reviewer required if sandbox runs exist.
- Failure modes / edges:
  - Invalid transition rejected.
  - Finalization rejected if phase not `FINALIZED`.

### 18) Search indexing (Postgres FTS)
- Entry points:
  - Worker: `apps/worker/indexing_activities.py`.
  - Core API: `apps/core-api/search_routes.py` exists but is not directly tested.
- Invariants:
  - Index entries keyed by `artifact_version_id`.
  - Workspace boundary filtering.
  - Ranking and snippet generation via Postgres FTS functions.

## Current test suite issues

### CI and execution gaps
- CI does not run `pytest` or Jest at all (`.github/workflows/ci.yml` is stub-check + health-only).
- `make test` does not run repo-level `./tests/` (it only runs `test-db` and `test-storage`).

### Determinism and flakiness sources
- `tests/conftest.py` readiness loop uses `time.sleep(0.15)` and a wall-clock deadline; can be flaky on slow CI.
- Heavy integration tests depend on Docker (`test_sandbox_execution.py`, `test_code_replication_workflow.py`).
- `tests/test_moltbook_adapter.py` depends on an externally-running adapter (and potentially upstream behavior); outcome is allowed to vary.
- `tests/test_auth.py` allows different statuses for invalid tokens (401 vs 503), making “expected behavior” ambiguous.
- TypeScript circuit breaker unit test uses real timers and sleeps (`setTimeout`), which is a common flake vector.

### Duplication and drift risk
- Storage tests duplicated: `tests/test_storage.py` vs `packages/shared-types/test_storage.py`.
- Migration tests duplicated: `tests/test_db_migrations.py` vs `packages/db/test_migrations.py` (and the package version is destructive).
- Many flows are tested by direct SQL rather than through the Core API boundary, which can drift from actual behavior and silently miss auth/RBAC invariants.

### Hidden coupling / global state
- `tests/conftest.py` mutates `sys.path` and force-binds `sys.modules["database"]`, which is brittle and makes import resolution non-obvious.
- Mixed DB access patterns (`db_session` nested transaction vs raw `psycopg2` connections vs worker connections that commit) cause tests to “leak” state and require special-case raw inserts.

### Readability and maintainability
- Test naming is not consistently `test_<unit_of_behavior>__<condition>__<expected>()` today.
- AAA structure is inconsistent (many tests are long “scripts”).
- Several tests include inline helpers duplicated across modules (creating workspace/agent/artifact/version repeatedly).
- Some tests claim to test an API endpoint but only assert via raw SQL queries (e.g., search).

### Coverage blind spots caused by collection/layout
- `tests/evaluation_harness.py` is not collected by default (filename doesn’t match patterns) despite being labeled as a regression harness.
- Node tests under `apps/web/node_modules/...` are vendored and should not be considered part of the repo’s test suite.

## Risk areas / missing coverage

- API-level RBAC enforcement is under-tested:
  - Many tests validate RBAC logic in `rbac.py`, but fewer validate that endpoints consistently call `require_permission(...)` and enforce membership.
- `/search` Core API endpoint behavior is not directly covered (tests query DB FTS directly).
- Idempotency behavior is not consistently validated across mutating agent endpoints:
  - Some idempotency is tested in ingestion flows, but there isn’t a uniform “Idempotency-Key required + dedupe” suite across endpoints.
- “Append-only memory” is only asserted by “no update endpoint exists” rather than also validating DB immutability constraints and audit log/event emission behavior on failures.
- Moltbook adapter integration in Python tests is not hermetic (external service required); Core API auth happy-path using adapter is not covered in a stable way.

## Refactor opportunities

- Introduce a clear test pyramid with explicit suites:
  - Fast unit tests for pure logic (state machines, parsers, gate evaluators, circuit breaker) using fake timers where needed.
  - Integration tests for DB/storage boundaries (Postgres + MinIO), with explicit markers and deterministic fixtures.
  - A small E2E suite for the critical vertical flows (Workflow A and B).
- Centralize factories/builders:
  - `WorkspaceFactory`, `AgentFactory`, `ArtifactFactory`, `ArtifactVersionFactory`, `ClaimFactory`, etc.
  - Standardize on one DB access pattern per suite (SQLAlchemy session vs raw connection) and provide helpers for “committed rows visible to server”.
- Add shared assertion helpers for “contract tests”:
  - Required fields, missingness thresholds (where applicable), value ranges, allowed enums, uniqueness/ref integrity.
- Reduce duplication:
  - Pick a single authoritative location for migration tests and storage tests; make package-level suites call into shared helpers instead of copy/paste.
- Make non-deterministic tests deterministic:
  - Replace “401 or 503 is fine” assertions with explicit fakes or explicit “adapter unavailable” test that is marked and isolated.
  - Start the Moltbook adapter in tests when needed (or run all adapter checks in Jest only).
  - Use fake timers for TS circuit breaker tests.
- Wire tests into CI:
  - Add jobs for `pytest` (unit + integration) and Jest (adapter) with docker-compose services.

