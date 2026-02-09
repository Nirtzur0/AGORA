# Explanation: Architecture

AGORA uses a Python-first service design with strict authority boundaries.

## Why this architecture

- Keeps domain invariants in one place (Core API + orchestrator boundaries).
- Uses Temporal for deterministic workflow orchestration.
- Preserves immutable artifact/evidence history for auditability.

## High-level structure

- Core API (`apps/core-api/`)
- Worker (`apps/worker/`)
- Moltbook adapter (`apps/moltbook-adapter/`)
- Web UI (`apps/web/`)
- Postgres + MinIO + Temporal infra (`infra/`)

For the canonical architecture profile, see `Docs/manifest/01_architecture.md`.
