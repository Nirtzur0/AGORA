# Epic: Authority and Gates

## Goal

Ensure phase progression and draft finalization authority stays exclusively in orchestrator/system paths with explicit persistence of gate outcomes.

## User Stories

- As a maintainer, I need confidence that agents cannot directly mutate phase state.
- As an auditor, I need every gate failure to be explicit and queryable.

## Tasks

- Add/expand integration tests for phase mutation denial on agent routes.
- Verify finalization failure paths write `rule_checks`, `activity_runs`, and `logs`.
- Close worker-side technical debt affecting deterministic gate execution.
