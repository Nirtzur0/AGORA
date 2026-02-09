# Reference: Data Formats

## Core persistent entities

Canonical schema source: `packages/db/migrations/001_initial_schema.py`.

Key records:

- `workspaces`: workspace metadata + phase.
- `artifacts` / `artifact_versions`: immutable versioned artifact model.
- `claims` / `claim_evidence` / `citations`: evidence graph.
- `logs` / `events`: append-only audit trail.
- `rule_checks`: explicit gate/rule outcomes.

## Evidence pointer format

Evidence resolution requests use:
- `artifact_version_id` (UUID)
- `location` (deterministic pointer string, e.g. pdf location)

Endpoint:
- `GET /evidence/resolve`

## API output conventions

- JSON responses with explicit status/error payloads.
- No silent fallback for rule/gate failures.
- Idempotent write endpoints honor `Idempotency-Key`.
