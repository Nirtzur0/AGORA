# Troubleshooting

## API health check fails

Symptom:
- `GET /health` does not return healthy.

Likely causes:
- Infra not started.
- Core API not running.

Fix:
- Run `make up`.
- Run `make dev-core-api`.
- Check `make logs`.

## Tests fail because pytest is missing

Symptom:
- `No module named pytest` when running Make targets.

Likely cause:
- Shell is using a different Python than the one with installed deps.

Fix:
- Install repo deps (`make install-core-api`, etc.).
- Run Make targets with explicit `PYTHON=<path>`.

## Integration tests fail due services

Symptom:
- Connection errors to Postgres/MinIO/Temporal.

Fix:
- Ensure `make up` completed and containers are healthy.
- Verify ports are available.

## Evidence resolve errors

Symptom:
- `GET /evidence/resolve` returns unresolved/invalid location error.

Fix:
- Confirm `artifact_version_id` exists.
- Confirm `location` format is deterministic and supported.
