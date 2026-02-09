# Assumptions Register

| Assumption | Impact | Status | Owner | Evidence / Decision Note | Target Stage |
|---|---|---|---|---|---|
| `Docs/` (capital D) remains the canonical docs root; `docs/...` references are aliases only. | high | accepted | maintainers | Existing repo uses `Docs/`; locked via `Docs/.prompt_system.yml` on 2026-02-08. | Shape |
| Orchestrator/system-only authority for phase advancement/finalization is already enforced across runtime paths. | high | accepted | maintainers | Canonical contract in `Docs/04-system-implementation-spec.md`; requires additional integration proof in Milestone M1. | Build |
| CI smoke + stubs checks are sufficient short-term while full matrix remains manual/local. | medium | accepted | maintainers | `.github/workflows/ci.yml` currently defines `docs-guardrail`, `check-stubs`, and `smoke-test`. | Cool-down |
| Worker DB connection lifecycle in `apps/worker/main.py` placeholder comments does not currently break critical workflows. | medium | open | maintainers | Placeholder comments exist; treat as technical debt item in M1/M2 hardening. | Build |
| Moltbook debug mode enabled in local compose is acceptable only for local development. | low | validated | maintainers | `infra/docker-compose.yml` sets `ENABLE_DEBUG_MODE=true`; production profile still required. | Shape |
