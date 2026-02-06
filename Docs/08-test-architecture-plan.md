# Target Test Architecture (Plan) + Commit Strategy

Date: 2026-02-06  
Repo: `/Users/nirtzur/Documents/projects/AGORA`

This is the proposed end-state test architecture and an implementation plan. No test refactors are performed in this document; it is the design/plan to execute next.

## Proposed folder tree

```text
tests/
  unit/
    auth/
      test_jwt_utils__agent_token__roundtrip.py
      test_jwt_utils__system_token__roundtrip.py
    rbac/
      test_permissions__role_matrix__canonical_keys.py
      test_permissions__membership__denied_for_nonmember.py
    phase_machine/
      test_transitions__valid__allowed.py
      test_transitions__invalid__rejected.py
      test_transitions__loopbacks__detected.py
    gates/
      test_lit_review_gate__snapshot__pass_and_fail.py
      test_internal_review_gate__skeptic_required__blocks.py
      test_finalization_gate__matrix__pass_fail_block.py
    evidence_locations/
      test_pdf_locations__grammar_and_bounds__deterministic.py
      test_log_locations__char_and_jsonpath__deterministic.py
      test_repo_locations__line_ranges__deterministic.py
    data_contracts/
      test_required_fields.py
      test_missingness_thresholds.py
      test_value_ranges.py
      test_allowed_categories.py
      test_shape_and_uniqueness.py

  integration/
    db/
      test_migrations__apply_from_empty__creates_tables.py
      test_constraints__uniqueness_and_fks__enforced.py
    storage/
      test_storage__put_get__roundtrip.py
      test_storage__immutability__no_overwrites.py
      test_storage__uri_validation__rejects_invalid.py
    core_api/
      test_auth_endpoints__errors__422_401.py
      test_artifacts__upload_and_retrieve__exact_bytes.py
      test_events__system_only__enforced.py
      test_logs__append_only__create_and_list.py
      test_requests__ingest_pdf__idempotent.py
      test_requests__ingest_repo__idempotent.py
      test_requests__run_sandbox__budget_enforced.py
      test_critiques__authorization__enforced.py
      test_phase__read_endpoint__reports_allowed_next.py
      test_rulechecks__citation_check__persists_rows.py
      test_search__endpoint__returns_hits_and_snippets.py
    worker/
      test_pdf_ingest__stores_pages_metadata_logs.py
      test_repo_ingest__stores_snapshot_and_metadata.py
      test_sandbox_run__captures_logs_and_config.py
      test_indexing__fts__rank_and_workspace_filter.py
      test_code_replication_workflow__happy_path__creates_runs_and_task.py
      test_literature_grounding_workflow__happy_path__creates_claims_and_draft.py
      test_finalization_activity__updates_metadata_and_emits_events.py
    data_contracts/
      test_boundary_payload_contracts.py
      test_persistence_contracts.py

  e2e/
    workflows/
      test_workflow_a__literature_grounding__critical_path.py
      test_workflow_b__code_replication__critical_path.py
    data_contracts/
      test_end_to_end_output_sanity.py

  helpers/
    assertions.py
    factories.py
    fakes.py
    http.py
    time.py
  conftest.py
```

Notes:
- TypeScript tests remain under `apps/moltbook-adapter/` and are run via Jest; they are part of the “library test suite” but use a different runner.
- `apps/web/node_modules/**` tests are vendored and must never be executed as repo tests.

## Module responsibilities

### `tests/unit/`
- Belongs:
  - Pure logic: parsing/validation, deterministic state transitions, gate evaluation functions, evidence location grammar, RBAC permission matrices.
  - “Contract” checks on *pure stage outputs* (see `data_contracts/` below).
- Must never:
  - Require Docker, Postgres, MinIO, or a running HTTP server.
  - Make real network calls.
- Markers:
  - `@pytest.mark.unit` (default in CI).

### `tests/integration/`
- Belongs:
  - DB + storage + HTTP boundary contracts.
  - Worker activities where the “external boundary” is storage/DB (and optionally Docker where explicitly marked).
  - Core API endpoint integration using in-process ASGI clients where possible.
- Must never:
  - Call external networks beyond local ephemeral containers.
  - Depend on a separately-started service outside pytest control.
- Markers:
  - `@pytest.mark.integration`
  - Additional markers: `docker`, `minio`, `postgres` where applicable.

### `tests/e2e/`
- Belongs:
  - Small number of “critical path” end-to-end flows spanning Core API + worker activities with real infra.
  - End-state “sanity” checks that validate the system as users experience it.
- Must never:
  - Duplicate coverage already well-served by integration tests.
- Markers:
  - `@pytest.mark.e2e`
  - `@pytest.mark.slow`

### `tests/helpers/`
- Belongs:
  - Shared factories/builders, fakes, and contract assertion helpers with debug-first failure messages.
- Must never:
  - Hardcode environment-specific paths or assume dev machine layout.

## Old -> New mapping table

This table is a *target mapping*; implementation will be done in small commits and may split a file into multiple new files.

| Old path | New path | Reason |
|---|---|---|
| `tests/test_auth.py` | `tests/unit/auth/*` + `tests/integration/core_api/test_auth_endpoints__*.py` | Split JWT pure logic from HTTP endpoint behavior; remove non-deterministic status allowances by faking adapter. |
| `tests/test_rbac.py` | `tests/unit/rbac/*` + small `tests/integration/core_api/*` as needed | RBAC logic is mostly unit-level; keep a small integration check that endpoints enforce it. |
| `tests/test_workspaces.py` | `tests/integration/core_api/test_workspaces__create_join__*.py` + `tests/unit/data_contracts/*` | Replace “SQL reimplementation” with API-level behavior tests; keep schema constraints in DB suite. |
| `tests/test_artifacts_exit.py` | `tests/integration/core_api/test_artifacts__*.py` | Keep as Core API boundary integration; migrate from `requests` + subprocess server to in-process ASGI where possible. |
| `tests/test_logs_events.py` | `tests/integration/core_api/test_logs__*.py` + `tests/integration/core_api/test_events__*.py` | Split logs vs events; avoid “simulated” exit criteria where real flows exist. |
| `tests/test_storage.py` | `tests/integration/storage/*` | Consolidate storage tests in one place (remove duplication with `packages/shared-types/test_storage.py`). |
| `packages/shared-types/test_storage.py` | `tests/integration/storage/*` (or keep, but shared helpers) | Remove duplication; keep one authoritative suite. |
| `tests/test_db_migrations.py` | `tests/integration/db/*` | Make migrations/constraints a single suite; consistent isolated DB creation. |
| `packages/db/test_migrations.py` | delete or convert to thin wrapper calling `tests/integration/db/*` | Avoid destructive shared-DB drops; enforce isolated DB per run. |
| `tests/test_pdf_ingestion.py` | `tests/integration/worker/test_pdf_ingest__*.py` | Flow-aligned worker activity integration suite. |
| `tests/test_evidence_resolver.py` | `tests/unit/evidence_locations/*` + `tests/integration/core_api/test_evidence__resolver__*.py` | Grammar/bounds are unit-level; storage/DB integration is separate. |
| `tests/test_claims.py` | `tests/integration/core_api/test_claims__*.py` | Keep as behavior tests; prefer API boundary when feasible. |
| `tests/test_drafts.py` | `tests/integration/core_api/test_drafts__*.py` | Split create/version/finalize; add contract assertions on outputs. |
| `tests/test_citation_checks.py` | `tests/unit/data_contracts/*` + `tests/integration/worker/test_citation_check__*.py` + `tests/integration/core_api/test_rulechecks__*.py` | Separate parsing/contract assertions from persistence and endpoint behaviors. |
| `tests/test_workflows.py` | `tests/integration/worker/test_workflow_tracking__*.py` + `tests/integration/core_api/test_tasks__*.py` | Separate worker tracking rows from API agent tasks behavior. |
| `tests/test_literature_grounding.py` | `tests/e2e/workflows/test_workflow_a__*.py` (keep one) + `tests/integration/*` for narrow cases | Keep one critical-path E2E; move other checks to integration modules. |
| `tests/test_repo_ingestion.py` | `tests/integration/worker/test_repo_ingest__*.py` + `tests/integration/core_api/test_requests__ingest_repo__*.py` | Split activity vs request endpoint and idempotency. |
| `tests/test_sandbox_execution.py` | `tests/integration/worker/test_sandbox_run__*.py` + `tests/integration/core_api/test_requests__run_sandbox__*.py` | Isolate Docker-required tests with markers; keep API request validations separate. |
| `tests/test_code_replication_workflow.py` | `tests/e2e/workflows/test_workflow_b__*.py` + `tests/integration/worker/test_code_replication_workflow__*.py` | Reduce duplication; keep one E2E and a smaller integration suite. |
| `tests/test_critiques.py` | `tests/integration/core_api/test_critiques__*.py` + `tests/unit/gates/*` (sufficiency) | Split API auth behaviors from worker sufficiency logic. |
| `tests/test_phase_machine.py` | `tests/unit/phase_machine/*` + `tests/unit/gates/*` + `tests/integration/core_api/test_phase__*.py` | Split pure state machine and gate evaluation from API endpoint. |
| `tests/test_search_indexing.py` | `tests/integration/worker/test_indexing__*.py` + `tests/integration/core_api/test_search__endpoint__*.py` | Add missing API endpoint coverage; keep FTS behavior tests. |
| `tests/test_draft_finalization.py` | `tests/integration/worker/test_finalization_gate__*.py` + `tests/integration/worker/test_finalization_activity__*.py` | Split gate matrix from activity side effects; keep async deterministic. |
| `tests/test_moltbook_adapter.py` | Prefer delete (redundant) or move to `tests/integration/external/*` w/ `external` marker | Python black-box tests are non-hermetic; Jest tests already cover adapter behavior deterministically. |
| `apps/moltbook-adapter/src/server.test.ts` | keep, maybe move to `apps/moltbook-adapter/src/__tests__/server.test.ts` | Align Jest structure; keep in app boundary. |
| `apps/moltbook-adapter/src/__tests__/circuit-breaker.test.ts` | keep, rewrite to fake timers | Remove real sleeps; deterministic unit tests. |
| `scripts/test_web_app.py` | keep as manual utility (not pytest) | Useful for human smoke; not part of deterministic CI gate. |
| `tests/evaluation_harness.py` | `tests/e2e/test_evaluation_harness__regression.py` | Ensure collected and run under explicit marker (e2e/slow). |

## Fixture strategy

### Global fixtures (`tests/conftest.py`) should be minimal
- `postgres_engine` / `db_session`:
  - Prefer one DB abstraction per suite: SQLAlchemy session for most integration tests.
  - Provide an explicit `committed_db_conn` helper when a test needs committed state visible across connections (avoid raw DB usage scattered around).
- `minio_storage`:
  - Use a single storage fixture that creates a per-test prefix (e.g., `s3://bucket/<run-id>/<test-id>/...`) and deletes objects at teardown.
- `core_api_app` + `asgi_client`:
  - Prefer in-process ASGI test client for Core API endpoint tests to avoid subprocess + sleep polling.
  - Only run an external uvicorn process for a small set of “real HTTP process” tests (if needed) and mark them `e2e`.

### Per-feature fixtures
- Keep feature-local fixtures close to their tests (e.g., `tests/integration/worker/conftest.py`).
- Avoid “fixture sprawl”:
  - Use factories/builders instead of many bespoke fixtures.

### Factories/builders (`tests/helpers/factories.py`)
- Provide explicit builders for:
  - `Agent`, `Workspace`, `Artifact`, `ArtifactVersion`, `Claim`, `Critique`, `RuleCheck`, `WorkflowRun`, `ActivityRun`, `AgentTask`, `Log`, `Event`.
- Factories should:
  - Default to valid “happy path” objects.
  - Allow overrides via keyword args.
  - Create + persist in one step (so tests don’t need to remember commit/flush semantics).

### Cleanup strategy
- Prefer transaction rollback for SQLAlchemy-session integration tests.
- For worker activities that open their own DB sessions and commit:
  - Use per-test unique IDs and delete rows in FK-safe order in a fixture finalizer (as done in `tests/test_search_indexing.py` today).
- For MinIO:
  - Track created URIs in the storage fixture and delete them in teardown.

## Mocking strategy

Mock only external boundaries.

- Moltbook upstream (external HTTP):
  - Mock in Jest (`axios-mock-adapter`) for adapter tests (already done).
  - For Core API auth tests that require adapter behavior:
    - Use a fake adapter server started in-process (or dependency injection) so tests are deterministic.
- Docker execution:
  - Unit tests: use a fake runner that returns deterministic stdout/stderr and exit code.
  - Integration tests: real Docker runs behind `@pytest.mark.docker` and skipped when Docker unavailable.
- Clock/time:
  - Prefer `freezegun` (or a small injected clock abstraction) for tests that assert timestamps/expiry.
  - In TS, use Jest fake timers (`jest.useFakeTimers()`).

## Test pyramid + selection policy

Target ratio:
- Unit: ~70%
- Integration: ~25%
- E2E: ~5% (only critical paths)

Required E2E coverage:
- Workflow A: literature grounding critical path.
- Workflow B: code replication critical path.
- End-to-end output sanity checks (data contracts) on those flows.

Markers/tags (pytest):
- `unit`, `integration`, `e2e`, `slow`, `docker`, `minio`, `postgres`, `external`

Example commands:
- Unit only: `pytest -m unit`
- Integration only (no docker): `pytest -m "integration and not docker"`
- Integration including docker: `pytest -m integration`
- E2E only: `pytest -m e2e`
- Full suite: `pytest` (default should run unit + non-docker integration; docker/e2e behind explicit markers to keep CI stable)

CI policy:
- Always run `unit` + `integration and not docker`.
- Run `docker` integration on a dedicated job with adequate resources and timeouts.
- Run Jest tests for Moltbook adapter on every PR.

## Coverage goals

Must-cover flows (happy + failure paths):
- Auth: JWT creation/verification; Core API auth endpoints error behavior; adapter unavailable behavior is explicit and deterministic.
- Artifacts: version immutability; exact retrieval by `artifact_versions.id`; event emission.
- Evidence resolver: all supported grammars + deterministic error codes.
- Claims: evidence validation failures and workspace mismatch.
- Drafts: versioning + finalize restrictions + event emission.
- Citation check: coverage/resolves persistence in `rule_checks` + `citations`.
- Repo ingest: metadata + evidence pointers + idempotency.
- Sandbox run: logs/config artifacts + budget enforcement + timeout.
- Critiques: endpoint authorization + sufficiency rule behavior.
- Phase machine: transition validity + gates + required actions.
- Search: indexing + boundary filtering + Core API `/search` endpoint contract.

## Required “Range & Completeness” data_contracts modules (first-class)

These modules will be implemented as required by the prompt:

- `tests/helpers/assertions.py` will include:
  - `assert_required_fields(obj, fields, context="...")`
  - `assert_missing_rate(rows, field, max_rate, context="...")`
  - `assert_in_range(values, min=None, max=None, allow_nan=False, context="...")`
  - `assert_allowed_values(values, allowed, context="...")`
  - `assert_unique(values, context="...")`
  - `assert_probability_vector(vec, tol=1e-6, context="...")` (used where applicable)
- Unit `tests/unit/data_contracts/*` will apply these checks to:
  - Evidence resolver results and error payload shapes.
  - Gate evaluation outputs (required keys, allowed statuses).
  - Citation check outputs (required keys; failures carry actionable detail).
- Integration `tests/integration/data_contracts/*` will apply these checks to:
  - Core API response payloads for key endpoints.
  - Persistence: DB rows for append-only tables, rule_checks, citations, artifact_versions.
- E2E `tests/e2e/data_contracts/test_end_to_end_output_sanity.py` will validate:
  - Final artifacts/logs/rule checks produced by Workflow A/B have required fields populated, allowed categories, sane ranges, and uniqueness invariants.

## Small-commit strategy (enforced)

This is the execution order once implementation begins:

- [ ] Commit 1: Scaffolding only
  - [ ] Add new `tests/unit`, `tests/integration`, `tests/e2e`, `tests/helpers` directories
  - [ ] Add pytest markers in `pytest.ini`
  - [ ] Move files only (no logic changes), add `xfail/skip` where absolutely necessary for infra gating
- [ ] Commit 2: Introduce helpers
  - [ ] `tests/helpers/assertions.py` (debug-first contract assertions)
  - [ ] `tests/helpers/factories.py` (builders for common domain objects)
  - [ ] `tests/helpers/fakes.py` (fake clock, fake docker runner)
- [ ] Commit 3: Rewrite worst offenders for determinism
  - [ ] Remove subprocess Core API server for most tests; use in-process ASGI client
  - [ ] Make Moltbook adapter dependency deterministic (fake server or injected verifier)
  - [ ] Remove sleeps/time-based flake patterns
- [ ] Commit 4: De-duplicate suites
  - [ ] Unify storage tests (one authoritative suite)
  - [ ] Unify migrations tests (isolated DB only)
- [ ] Commit 5: Add missing coverage
  - [ ] Add `/search` endpoint integration tests
  - [ ] Add explicit idempotency-key dedupe tests for agent write endpoints (where contract requires)
  - [ ] Add first-class `data_contracts` modules across unit/integration/e2e
- [ ] Commit 6: Cleanup
  - [ ] Delete dead/redundant tests, remove `pytest.main()` blocks
  - [ ] Update `Makefile` and `.github/workflows/ci.yml` to run the new suites

