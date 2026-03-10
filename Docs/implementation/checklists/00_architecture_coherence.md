# Checklist: Architecture Coherence

## Scope & Readiness

- Appetite: `medium`
- Packet state: `downhill`
- Readiness verdict: `GO_WITH_RISKS`

Objective anchor: `Docs/manifest/00_overview.md#Core Objective`

- [x] Scope for this packet is bounded to architecture coherence + worker lifecycle hardening.
  - AC: architecture docs/checklist/report reflect current runtime behavior without parallel doc systems.
  - Verify: `test -f Docs/manifest/01_architecture.md && test -f Docs/implementation/reports/architecture_coherence_report.md`

- [x] Readiness verdict is explicit and evidence-backed.
  - AC: verdict appears in both checklist and report with top risks and `Now/Not now`.
  - Verify: `rg -n "GO_WITH_RISKS|Readiness verdict|Now|Not now" Docs/implementation/checklists/00_architecture_coherence.md Docs/implementation/reports/architecture_coherence_report.md`

## C4 Coverage (L1/L2/L3 where used)

- [x] C4-1 system context documented and mapped to repo boundaries.
  - Evidence: `Docs/manifest/01_architecture.md`, `apps/core-api/`, `apps/worker/`, `apps/moltbook-adapter/`, `apps/web/`

- [x] C4-2 container view documented and mapped to runtime/data services.
  - Evidence: `Docs/manifest/01_architecture.md`, `infra/docker-compose.yml`

- [x] C4-3 high-risk component view documented for API/worker boundaries.
  - Evidence: `Docs/manifest/01_architecture.md`, `apps/core-api/*`, `apps/worker/*`

## Runtime + Deployment Coverage

- [x] Runtime scenarios include at least one failure path.
  - Evidence: `Docs/manifest/01_architecture.md` (`## Runtime Scenarios`)

- [x] Deployment and trust boundaries are documented.
  - Evidence: `Docs/manifest/01_architecture.md`, `Docs/manifest/08_deployment.md`

## Docs Architecture vs Code Reality (Drift Diff)

- [x] Service boundary docs match repo layout (`apps/core-api`, `apps/worker`, `apps/moltbook-adapter`, `apps/web`).
- [x] Artifact/evidence model in docs matches migration schema (`artifacts`, `artifact_versions`, `citations`, `claim_evidence`).
- [x] Worker bootstrap dependency lifecycle is explicitly hardened (no placeholder lifecycle comments remain in `apps/worker/main.py`).
- [x] CI enforces unit/integration matrix and is mapped to runbook command IDs (`.github/workflows/ci.yml`, `Docs/manifest/11_ci.md`).
- [x] Test-boundary drift follow-up is recorded as links (prompt-09 packet), without duplicating architecture prose.
  - Evidence: `Docs/implementation/reports/test_landscape.md`, `Docs/implementation/reports/test_architecture_plan.md`, `Docs/manifest/01_architecture.md` (`## Test Architecture Boundary Note (2026-02-09)`).
- [x] Architecture coherence validation is automated in CI (via `CMD-28` + `architecture-coherence` job).

## Invariants + Verification Commands

- [x] Invariant: agent clients are HTTP-only and never direct DB/storage.
  - Verify evidence: `apps/core-api/main.py`, `Docs/manifest/01_architecture.md`

- [x] Invariant: phase/finalization authority remains orchestrator/system-controlled.
  - Verify evidence: `Docs/manifest/04_api_contracts.md`, `apps/core-api/phase_routes.py`, `apps/core-api/draft_routes.py`

- [x] Invariant: evidence is version-pinned and resolvable.
  - Verify evidence: `packages/db/migrations/001_initial_schema.py`, `apps/core-api/evidence_routes.py`, `apps/core-api/evidence_resolver.py`

- [x] Invariant: worker runtime dependencies are validated at boot and DB-scoped per invocation.
  - Verify evidence: `apps/worker/main.py`, `tests/unit/worker/test_main_runtime_deps.py`

Verification commands used in this packet (repo-sourced):
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/worker/test_main_runtime_deps.py`
- `make up`
- `PYTHONPATH=packages/db:packages/shared-types:apps/worker python3 - <<'PY' ... wm._load_runtime_dependencies(); wm._validate_runtime_dependencies(deps) ... PY`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/worker/test_pdf_ingestion.py`
- `make PYTHON=python3 check-architecture-coherence`
- `make down`

## Now / Not now

Now:
- [x] Remove placeholder worker lifecycle behavior and enforce deterministic dependency handling in `apps/worker/main.py`.
- [x] Re-run architecture coherence mapping and refresh architecture docs/report.

Not now:
- [x] Extend the same worker lifecycle pattern as additional activities are registered through `apps/worker/main.py`.
  - Completed 2026-02-09 by extending `apps/worker/main.py` registrations to:
    - wrapper-backed activities: `pdf_ingest`, `repo_ingest`, `sandbox_run`
    - bundled phase/gate/index/finalization activities via `PHASE_ACTIVITIES`
  - Verify:
    - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/worker/test_main_runtime_deps.py tests/unit/worker/test_phase_machine.py` -> PASS (`16 passed`)
    - `make test-unit` -> PASS (`31 passed`)
    - `make PYTHON=python3 check-architecture-coherence` -> PASS
    - `PYTHONPATH=packages/db:packages/shared-types:apps/worker python3 - <<'PY' ... wm._load_runtime_dependencies(); wm._build_registered_activities(deps) ... PY` -> PASS (`REGISTERED_ACTIVITIES=16`, wrappers present)

## Blockers / TODOs

- [x] Implement an automated architecture coherence check in CI to reduce manual drift risk.
