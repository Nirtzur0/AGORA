# Explanation: Design Decisions

This page summarizes major architectural and process decisions.

## Primary references

- Canonical system contract: `Docs/04-system-implementation-spec.md`
- Decision log: `Docs/manifest/03_decisions.md`

## Key decisions

- Python-first core with TypeScript adapter for Moltbook verification.
- Orchestrator/system authority over phase/finalization transitions.
- Version-pinned evidence and immutable artifact versions.
- Append-only audit trail (`logs`, `events`).

## Tradeoffs

- Cross-language runtime/tooling complexity (Python + Node).
- Strong determinism/auditability focus over immediate production hardening.
