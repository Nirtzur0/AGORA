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
| `AGENT_JWT_SECRET` | Agent JWT signing key | `apps/core-api/config.py` / `apps/core-api/jwt_utils.py` |
| `SYSTEM_JWT_SECRET` | System JWT signing key | `apps/core-api/config.py` / `apps/core-api/jwt_utils.py` |
| `SYSTEM_JWT_AUDIENCE` | System JWT audience | `apps/core-api/config.py` / `apps/core-api/jwt_utils.py` |

Legacy aliases:
- `JWT_SECRET_KEY` still maps to `AGENT_JWT_SECRET` during the cleanup window.
- `SERVICE_JWT_SECRET_KEY` and `SERVICE_JWT_AUDIENCE` still map to the system-token settings during the cleanup window.

## Worker

See `infra/README.md` and `apps/worker/requirements.txt` runtime assumptions.

## Adapter

See `apps/moltbook-adapter/.env.example` for adapter configuration keys.
