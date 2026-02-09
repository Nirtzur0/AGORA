# How To: Interpret Outputs

AGORA outputs are mainly API responses, DB-backed audit records, and artifact versions.

## What to inspect first

- `workspaces` state and phase.
- `artifacts` + `artifact_versions` for immutable outputs.
- `logs`, `events`, and `rule_checks` for audit/gate behavior.

## Correctness cues

- Evidence and citations should always reference explicit `artifact_version_id` and deterministic `location`.
- Finalization should fail explicitly when rule checks fail (no silent fallback).
- Idempotent write retries should return consistent results.

## Practical validation path

1. Run integration tests (`make test-integration`).
2. Inspect rule-check and event outputs in failing/success flows.
3. Verify evidence resolution endpoint output for expected location snippets.
