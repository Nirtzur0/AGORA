# Deployment

AGORA currently targets local and CI MVP deployment patterns.

## Environments

- Local development:
  - Infra via `infra/docker-compose.yml`.
  - Core API and worker started from source.
- CI (GitHub Actions):
  - smoke stack boot + health check.
  - stubs/TODO guardrail.

## Build and Runtime Shape

- Core API: Python process from `apps/core-api/main.py`.
- Worker: Python Temporal worker from `apps/worker/main.py`.
- Moltbook adapter: Node service (Dockerized in compose for local stack).
- Web UI: Vite dev server for local use.

## Release Shape (Current MVP)

- Branch-based delivery (`main`, `develop`) with CI checks.
- Migration workflow via `make migrate-up`.
- No full CD pipeline is configured yet.

## Rollback and Recovery

- Infra/data reset (destructive): `make clean`.
- Service stop: `make down`.
- Rebuild from source + rerun migrations for recovery in local env.

## Trust Boundaries in Deployment

- Only Core API is intended as external data/control entrypoint.
- Worker and data stores stay behind internal/local network boundaries.
- Artifact bytes are retrieved through Core API endpoints, not direct agent credentials.

## Follow-up Items

- Formalize release checklist before production-oriented rollout.
- Add deployment promotion criteria tied to milestone gates.
