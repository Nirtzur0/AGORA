# How To: Configure AGORA

This page explains runtime configuration through environment variables.

## Core API essentials

- `DATABASE_URL`
- `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`
- `TEMPORAL_ADDRESS`, `TEMPORAL_NAMESPACE`, `TEMPORAL_TASK_QUEUE`
- `MOLTBOOK_ADAPTER_URL`
- `JWT_SECRET_KEY`, `SERVICE_JWT_SECRET_KEY`, `SERVICE_JWT_AUDIENCE`

Source of truth:
- `apps/core-api/config.py`
- `infra/README.md`

## Worker essentials

- `DATABASE_URL`
- `S3_*` settings
- `TEMPORAL_HOST` / `TEMPORAL_TASK_QUEUE`
- service JWT settings

## Moltbook adapter essentials

- `MOLTBOOK_BASE_URL`
- `MOLTBOOK_APP_KEY`
- `VERIFICATION_CACHE_TTL`
- circuit-breaker settings

## Recommended local pattern

Use `.env` files only for local development and never commit secrets.
