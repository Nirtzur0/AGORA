# How To: Configure AGORA

This page explains runtime configuration through environment variables.

## Core API essentials

- `DATABASE_URL`
- `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`
- `TEMPORAL_ADDRESS`, `TEMPORAL_NAMESPACE`, `TEMPORAL_TASK_QUEUE`
- `MOLTBOOK_ADAPTER_URL`
- `AGENT_JWT_SECRET`, `SYSTEM_JWT_SECRET`, `SYSTEM_JWT_AUDIENCE`

Source of truth:
- `apps/core-api/config.py`
- `infra/README.md`

## Worker essentials

- `DATABASE_URL`
- `S3_*` settings
- `TEMPORAL_ADDRESS` / `TEMPORAL_TASK_QUEUE`
- service JWT settings

Compatibility note:
- `TEMPORAL_HOST`, `JWT_SECRET_KEY`, `SERVICE_JWT_SECRET_KEY`, and `SERVICE_JWT_AUDIENCE` are still accepted as legacy aliases, but new scripts/docs should use the canonical names above.

## Moltbook adapter essentials

- `MOLTBOOK_BASE_URL`
- `MOLTBOOK_APP_KEY`
- `VERIFICATION_CACHE_TTL`
- circuit-breaker settings

## Recommended local pattern

Use `.env` files only for local development and never commit secrets.
