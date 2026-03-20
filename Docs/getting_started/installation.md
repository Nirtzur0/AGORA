# Installation

This guide installs AGORA for local development on macOS/Linux.

## Prerequisites

- Docker Desktop (or compatible Docker engine)
- Python 3.12+
- Node 18+
- `make`

## 1) Clone and enter the repo

```bash
git clone https://github.com/Nirtzur0/AGORA.git
cd AGORA
```

## 2) Start infrastructure

```bash
make up
```

This starts Postgres, Temporal, MinIO, and the Moltbook adapter (see `infra/docker-compose.yml`).

## 3) Install dependencies

```bash
make install-db install-storage install-core-api install-moltbook
python3 -m pip install -r apps/worker/requirements.txt
```

## 4) Run migrations

```bash
make migrate-up
```

## 5) Start services

Core API:

```bash
make dev-core-api
```

Worker:

```bash
TEMPORAL_HOST=localhost:7233 TEMPORAL_TASK_QUEUE=agora-tasks python3 apps/worker/main.py
```

Web UI:

```bash
cd apps/web
npm install
npm run dev
```

## 6) Validate health

```bash
curl -sS http://localhost:18000/health
```

Expected output contains `"status": "healthy"`.

## Common install issues

- If `pytest` is missing in your shell Python, use the repo install commands above and run Make targets with explicit `PYTHON=<path>` when needed.
- If Docker services are unhealthy, run `make logs` and verify ports are free.
