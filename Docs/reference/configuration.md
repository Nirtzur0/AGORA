# Reference: Configuration

## Core API

| Variable | Purpose | Default / Source |
|---|---|---|
| `DATABASE_URL` | Postgres connection | `apps/core-api/config.py` |
| `S3_ENDPOINT` | MinIO/S3 endpoint | `apps/core-api/config.py` |
| `S3_ACCESS_KEY` | S3 access key | `apps/core-api/config.py` |
| `S3_SECRET_KEY` | S3 secret | `apps/core-api/config.py` |
| `S3_BUCKET` | Artifact bucket | `apps/core-api/config.py` |
| `TEMPORAL_ADDRESS` | Temporal server address | `apps/core-api/config.py` |
| `TEMPORAL_NAMESPACE` | Temporal namespace | `apps/core-api/config.py` |
| `TEMPORAL_TASK_QUEUE` | Task queue name | `apps/core-api/config.py` |
| `MOLTBOOK_ADAPTER_URL` | Adapter base URL | `apps/core-api/config.py` |
| `JWT_SECRET_KEY` | Agent JWT signing key | `apps/core-api/config.py` |
| `SERVICE_JWT_SECRET_KEY` | System JWT signing key | `apps/core-api/config.py` |
| `SERVICE_JWT_AUDIENCE` | System JWT audience | `apps/core-api/config.py` |

## Worker

See `infra/README.md` and `apps/worker/requirements.txt` runtime assumptions.

## Adapter

See `apps/moltbook-adapter/.env.example` for adapter configuration keys.
