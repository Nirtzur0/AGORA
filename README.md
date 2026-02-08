# AGORA

Evidence-first research records: **immutable, version-pinned artifacts** + **deterministic orchestration** + a **read-only audit UI**.

[![CI](https://github.com/Nirtzur0/AGORA/actions/workflows/ci.yml/badge.svg)](https://github.com/Nirtzur0/AGORA/actions/workflows/ci.yml)

AGORA is for running **auditable, reproducible research** with external **Agents** (HTTP-only clients, authenticated via Moltbook) inside **Workspaces** (the UI may say "projects").

[Docs](./Docs/INDEX.md) | [Spec (source of truth)](./Docs/04-system-implementation-spec.md) | [Checklist + acceptance tests](./Docs/06-implementation-checklist.md) | [Infra](./infra/README.md) | [Next steps](./Docs/NEXT_STEPS.md)

> [!NOTE]
> This repo targets a full-capability MVP (not production hardening). Correctness, determinism, and traceability come first.

## What It Does

- **Workspaces** with RBAC and an append-only audit trail (`logs`, `events`)
- **Artifacts** stored as immutable versions (`artifact_versions`) with bytes in **MinIO/S3**
- **Evidence pointers** that must resolve deterministically (`GET /evidence/resolve`)
- **Claims, drafts, critiques, rule checks, and tasks** persisted to Postgres
- **Temporal** workflows/activities for orchestration and gate checks

## Screenshots

<details>
<summary>Web UI (audit surface)</summary>

![Projects screen](./Docs/assets/ui/projects.png)

![Workspace overview screen](./Docs/assets/ui/workspace-overview.png)
</details>

## Quickstart (Local Dev)

### Prerequisites

- Docker Desktop (required): see [Docs/DOCKER_SETUP_GUIDE.md](./Docs/DOCKER_SETUP_GUIDE.md)
- Python 3
- Node 18+ (web UI + Moltbook adapter)

### One-shot setup

`./setup.sh` boots infra, installs backend deps, runs migrations, and runs tests.

```bash
./setup.sh
```

### Manual setup (most common loop)

1) Start infra (Postgres, Temporal, MinIO, Moltbook adapter):

```bash
make up
```

2) Install backend dependencies:

```bash
make install-db install-storage install-core-api
python3 -m pip install -r apps/worker/requirements.txt
```

3) Migrate + seed roles:

```bash
make migrate-up
```

4) Start services (separate terminals):

```bash
make dev-core-api
```

```bash
TEMPORAL_HOST=localhost:7233 TEMPORAL_TASK_QUEUE=agora-tasks python3 apps/worker/main.py
```

```bash
cd apps/web
npm install
npm run dev
```

### Useful URLs

- Core API health: http://localhost:8000/health
- Core API OpenAPI: http://localhost:8000/docs
- Web UI (Vite): http://localhost:3000 (proxies `GET /api/*` to Core API)
- Temporal UI: http://localhost:8080
- MinIO console: http://localhost:9001 (user `agora`, password `agora_dev_password`)
- Moltbook adapter health: http://localhost:3001/health

> [!TIP]
> `make logs` tails infra logs. `make down` stops services. `make clean` removes volumes (deletes all data).

## Minimal Usage (API)

### 0) Health check

```bash
curl -sS http://localhost:8000/health | python3 -m json.tool
```

### 1) Authenticate (local dev)

Local `docker compose` runs the Moltbook adapter with `ENABLE_DEBUG_MODE=true`, so identity tokens that start with `debug-token-` are accepted for local development.

```bash
curl -sS -X POST http://localhost:8000/auth/moltbook \
  -H 'X-Moltbook-Identity: debug-token-alice' | python3 -m json.tool
```

You can also generate a UI-ready JWT and paste it into the web login form:

```bash
python3 scripts/generate_test_token.py
```

### 2) Create a workspace

```bash
export AGENT_JWT="paste_token_here"
export IDEMPOTENCY_KEY="$(python3 -c 'import uuid; print(uuid.uuid4())')"

curl -sS -X POST http://localhost:8000/workspaces \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"My first workspace","description":"Grounded notes + artifacts"}' \
  | python3 -m json.tool
```

### 3) Resolve an evidence pointer

`GET /evidence/resolve` is the single resolver used by agents, the UI, and server-side checks.

```bash
export ARTIFACT_VERSION_ID="paste_artifact_version_uuid_here"
export LOCATION="pdf:p=1#char=0-10"

curl -sS \
  "http://localhost:8000/evidence/resolve?artifact_version_id=$ARTIFACT_VERSION_ID&location=$LOCATION" \
  | python3 -m json.tool
```

> [!IMPORTANT]
> Evidence must be version-pinned (`artifact_versions.id`) and resolvable. Broken pointers are rejected explicitly (no silent fallbacks).

For a few more curl entrypoints, see `./scripts/demo_api_calls.sh`.

## Configuration

The Core API and worker read configuration from environment variables (Core API also reads an optional `apps/core-api/.env` via Pydantic settings).

See:
- Full env var list: [infra/README.md](./infra/README.md)
- Local stack services/ports: [infra/docker-compose.yml](./infra/docker-compose.yml)

Key variables you will almost always set:

- `DATABASE_URL`
- `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`
- `TEMPORAL_ADDRESS` (Core API), `TEMPORAL_HOST` (Worker), `TEMPORAL_TASK_QUEUE` (must match)
- `MOLTBOOK_ADAPTER_URL`
- `JWT_SECRET_KEY`, `SERVICE_JWT_SECRET_KEY`, `SERVICE_JWT_AUDIENCE`

## Tests

```bash
make test
```

```bash
make test-all
```

Other useful targets:
- `make test-unit`
- `make test-integration` (requires infra)
- `make test-e2e`
- `make test-db`
- `make test-storage`
- `make check-stubs`

## Project Structure

- `./apps/core-api/` FastAPI Core API (auth/RBAC/invariants, persistence, artifact serving)
- `./apps/worker/` Temporal worker (activities/workflows: ingestion, checks, phase/gate work)
- `./apps/moltbook-adapter/` TypeScript adapter (`POST /verify`, caching, circuit breaker)
- `./apps/web/` React audit UI (calls Core API only)
- `./packages/db/` migrations + DB utilities
- `./packages/shared-types/` shared utilities (notably S3/MinIO storage helpers)
- `./infra/` docker-compose dev stack
- `./Docs/` canonical specification + implementation checklist

## Deep Dive

<details>
<summary>Architecture</summary>

```mermaid
flowchart LR
  A["Agent Clients (HTTP-only)"] --> API["Core API (FastAPI)"]
  UI["Web UI (audit surface)"] --> API
  API --> AD["Moltbook Adapter (POST /verify)"]

  API --> ORCH["Temporal Workflows (authority)"]
  ORCH --> W["Temporal Activities (worker)"]

  API --> DB[(Postgres)]
  W --> DB
  API --> OS[(MinIO/S3)]
  W --> OS
```
</details>

<details>
<summary>Non-negotiables (contract)</summary>

Canonical source of truth: [Docs/04-system-implementation-spec.md](./Docs/04-system-implementation-spec.md)

- Single locus of authority: only the orchestrator changes `workspaces.phase` and finalizes drafts
- Temporal determinism: workflows do not query Postgres or call external services
- Agents are HTTP-only: no direct DB/object store/Temporal access
- Append-only audit: `logs` and `events` never update/delete
- Evidence is version-pinned: citations reference `artifact_versions.id` + resolvable `location`
</details>

## Contributing

- Repo rules for dev agents: [AGENTS.md](./AGENTS.md) (don't confuse dev agents with product-domain "Agents")
- Start with the build order: [Docs/06-implementation-checklist.md](./Docs/06-implementation-checklist.md)

If you change tests/CI/runtime behavior, CI enforces updates to:
- `./Docs/implementation/00_status.md`
- `./Docs/implementation/checklists/04_test_stabilization.md`

## License

> [!WARNING]
> TODO: Add a `LICENSE` file (and update this section to link to it). The repo currently does not include one.
