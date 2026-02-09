# Architecture Coherence Report

Date: 2026-02-09
Prompt packet: `prompt-04-architecture-coherence-loop` (worker activity-registration lifecycle follow-through)

## 1) Current Architecture Snapshot

AGORA remains coherent with its Python-first boundary model:
- Core API owns auth/RBAC/domain invariants and orchestration starts.
- Worker owns Temporal activities/workflows and writes auditable outcomes.
- Moltbook adapter remains verification-only (`POST /verify`).
- Web UI remains Core-API-only.
This rerun specifically automated architecture coherence validation by:
- adding `scripts/check_architecture_coherence.py`,
- wiring `make check-architecture-coherence`, and
- enforcing CI `architecture-coherence` job in `.github/workflows/ci.yml`.
Follow-through in this packet extends `apps/worker/main.py` activity registration so additional activities follow the same dependency lifecycle pattern.

## 2) Diagram-to-Repo Mapping Table

| Architecture Element | Repo Evidence | Status |
|---|---|---|
| Agent/Web -> Core API boundary | `apps/core-api/main.py`, `apps/web/src/` | aligned |
| Core API -> Moltbook adapter | `apps/core-api/auth_routes.py`, `apps/moltbook-adapter/src/server.ts` | aligned |
| Core API/Worker -> Temporal | `apps/core-api/*workflow*`, `apps/worker/*workflow*.py`, `apps/worker/main.py` | aligned |
| Core API/Worker -> Postgres | `packages/db/migrations/001_initial_schema.py`, `apps/core-api/*`, `apps/worker/*` | aligned |
| Core API/Worker -> MinIO/S3 | `packages/shared-types/storage.py`, `apps/core-api/artifact_routes.py`, `apps/worker/pdf_ingest.py` | aligned |
| Worker dependency lifecycle | `apps/worker/main.py`, `tests/unit/worker/test_main_runtime_deps.py`, `phase_activities.PHASE_ACTIVITIES` | aligned |
| Evidence resolution boundary | `apps/core-api/evidence_routes.py`, `apps/core-api/evidence_resolver.py` | aligned |

## 3) Key Mismatches, Decisions, and Open Risks

Mismatches closed in this packet:
- Added deterministic CI + local gate for architecture coherence validation (previously manual-only).

Decisions:
- Keep dependency initialization at process startup and create activity objects per invocation to avoid shared mutable DB state.
- Register `repo_ingest` and `sandbox_run` wrappers in `apps/worker/main.py` using the same DB-scoped wrapper lifecycle as `pdf_ingest`.
- Register `PHASE_ACTIVITIES` in `apps/worker/main.py` so workflow activity names used by phase/finalization workflows are available on the worker task queue.

Open risks:
1. Future activity additions may drift unless every new registration keeps the same per-invocation DB-scoped lifecycle pattern.

## 4) Verification Command Evidence

Commands executed and sources:
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/worker/test_main_runtime_deps.py`
  - source: `tests/unit/worker/test_main_runtime_deps.py`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/worker/test_main_runtime_deps.py tests/unit/worker/test_phase_machine.py`
  - source: `tests/unit/worker/test_main_runtime_deps.py`, `tests/unit/worker/test_phase_machine.py`
- `make up`
  - source: `Makefile` (`CMD-01` in `Docs/manifest/09_runbook.md`)
- `PYTHONPATH=packages/db:packages/shared-types:apps/worker python3 - <<'PY' ... wm._load_runtime_dependencies(); wm._validate_runtime_dependencies(deps) ... PY`
  - source: `apps/worker/main.py`
- `PYTHONPATH=packages/db:packages/shared-types:apps/worker python3 - <<'PY' ... wm._load_runtime_dependencies(); wm._build_registered_activities(deps) ... PY`
  - source: `apps/worker/main.py`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/worker/test_pdf_ingestion.py`
  - source: `tests/integration/worker/test_pdf_ingestion.py`
- `make PYTHON=python3 check-architecture-coherence`
  - source: `Makefile`, `scripts/check_architecture_coherence.py`, `.github/workflows/ci.yml`
- `make down`
  - source: `Makefile` (`CMD-02` in `Docs/manifest/09_runbook.md`)

## 5) Readiness Verdict and Rationale

Verdict: `GO_WITH_RISKS`

Rationale:
- Architecture boundaries and runtime behavior are coherent with repository implementation.
- Architecture coherence validation is now enforced by CI and runnable locally (`CMD-28`).
- Activity registration coverage in `apps/worker/main.py` now includes wrapper-backed ingest/execution activities and the phase bundle.
- Remaining risk is implementation-growth drift for future activity additions, not a boundary design flaw.

## 6) Now and Not now

Now:
- Keep `Docs/manifest/01_architecture.md` and mapping docs aligned as worker activity registration expands.

Not now:
- Additional architecture decomposition unless new high-risk containers/components are introduced.
