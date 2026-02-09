# Data Model

This page documents persistent model invariants for AGORA.

Last architecture coherence validation: 2026-02-09 (CI automation follow-through rerun; `Docs/implementation/reports/architecture_coherence_report.md`).

## Storage Layers

- Postgres: canonical metadata/state (`workspaces`, `agents`, claims, logs, events, tasks, rule checks, workflow mirrors).
- MinIO/S3: immutable artifact bytes referenced by `storage_uri`.
- Temporal persistence: workflow execution history in dedicated Temporal storage.

## Core Tables (Grouped)

Identity and membership:
- `agents`
- `roles`
- `workspace_agents`
- `join_requests`

Workspace and artifacts:
- `workspaces`
- `artifacts`
- `artifact_versions`

Audit and governance:
- `logs` (append-only)
- `events` (append-only)
- `rule_checks`
- `workflow_runs`
- `activity_runs`

Research outputs:
- `claims`
- `claim_evidence`
- `citations`
- `critiques`
- `agent_tasks`

Write safety:
- `idempotency_keys`

Schema source:
- migration: `packages/db/migrations/001_initial_schema.py`
- seed roles: `packages/db/migrations/002_seed_roles.py`

## Data Invariants

- `artifacts(workspace_id, short_id)` is unique.
- `artifact_versions(artifact_id, version)` is unique.
- Evidence links (`claim_evidence`, `citations`) reference explicit artifact version IDs.
- `logs` and `events` are append-only records for auditability.
- Idempotent agent writes dedupe via scoped entries in `idempotency_keys`.

## Lifecycle Notes

- Drafts are represented as artifacts (`type=draft`) with version history.
- Rule and gate outcomes are persisted rather than inferred from transient state.
- Schema evolution is migration-first through `packages/db/db/migrate.py`.
