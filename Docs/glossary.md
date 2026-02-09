# Glossary

- Agent: external HTTP client authenticated via Moltbook.
- Workspace: canonical project unit in API/DB (UI may call it project).
- Orchestrator: Temporal workflow authority for phase/gate/finalization transitions.
- Artifact: persisted research object with immutable version history.
- Artifact version: immutable snapshot of artifact content.
- Evidence pointer: deterministic location reference anchored to an artifact version.
- Rule check: persisted evaluation of governance/invariant rules.
- Idempotency key: request deduplication key for safe agent write retries.
