# Observability

This page is the observability and reliability gate for AGORA runtime workflows.

## Critical Workflows

1. Authentication and workspace join.
2. Artifact ingestion (PDF/repo) and artifact version creation.
3. Evidence resolution and claim/citation linkage.
4. Draft finalization and rule-check gating.
5. External artifact registry freshness and provenance coverage.
6. Objective metrics automation for citation integrity and authority-boundary regressions.

## Telemetry Surfaces

- Service health:
  - `GET /health` on Core API.
- Persistent audit streams:
  - `logs`, `events`, `rule_checks`, `workflow_runs`, `activity_runs`.
- Local runtime logs:
  - `core_api.log`, `apps/worker/worker.log`.
- Temporal runtime visibility:
  - Temporal UI (`http://localhost:8080`).

## Golden Signals and SLO Targets

| Workflow | Signal Class | SLI Definition | SLO Target | Persistence Source |
|---|---|---|---|---|
| Auth + join | Latency | p95 response time for `/auth/moltbook` and join-request review path | p95 < 2.0s over 15m | API logs + `events` |
| Auth + join | Errors | ratio of 4xx/5xx auth failures excluding invalid-token expected failures | < 1% 5xx over 15m | `logs`, API logs |
| Artifact ingestion | Latency | p95 time from request action to terminal `workflow_runs.status` for `literature_grounding`/`code_replication` | p95 < 120s over 30m | `workflow_runs`, `activity_runs` |
| Artifact ingestion | Errors | failed workflow/activity ratio for ingest/run activities | < 2% failed over 30m | `workflow_runs`, `activity_runs`, `logs` |
| Evidence + citation | Correctness | draft versions with latest `citation_check=pass` and `all_citations_resolve=true` | 100% before finalization attempt | `rule_checks` |
| Evidence + citation | Freshness | time from draft version creation to first citation check row | p95 < 30s over 30m | `artifact_versions`, `rule_checks` |
| Draft finalization | Gate health | finalization attempts with persisted `finalization_gate` row and explicit status | 100% persisted | `rule_checks`, `logs` |
| Draft finalization | Errors/Blocks | share of `finalization_gate` statuses in `fail`/`block` | investigate immediately when > 5% over 60m | `rule_checks`, `events` |
| Artifact registry | Provenance coverage | share of external artifacts with non-empty `id`, `url`, and parseable `retrieved_at` | 100% continuously | `Docs/artifacts/index.json`, `CMD-19`, `CMD-20` |
| Artifact registry | Freshness | share of external artifacts with `retrieved_at` age <= 90 days (warning >= 75 days) | 100% <= 90 days; page on sustained breach (>24h) | `Docs/artifacts/index.json`, `CMD-20` |
| Objective metrics | Citation integrity regression | targeted citation suites in `CMD-29` pass with `pass_rate=1.0` | 100% metric pass per run | `scripts/check_objective_metrics.py`, `tests/integration/worker/test_citation_checks.py`, `tests/integration/core_api/test_evidence_resolver.py` |
| Objective metrics | Authority boundary regression | targeted authority suites in `CMD-29` pass with `pass_rate=1.0` | 100% metric pass per run | `scripts/check_objective_metrics.py`, `tests/integration/worker/test_phase_machine.py`, `tests/integration/core_api/test_drafts.py` |

## Severity Routing

| Severity | Trigger | Required Routing | Initial Triage |
|---|---|---|---|
| SEV-1 | data integrity risk, missing audit persistence, or >10% 5xx on critical workflow for 10m | maintainer + orchestrator owner immediately | `CMD-03`, `CMD-12`, `CMD-16` |
| SEV-2 | sustained SLO breach without data loss (for example ingest/finalization latency breach 30m), artifact freshness stale > 90 days for >24h, or provenance coverage <100% | maintainer on-call within 30m | `CMD-03`, `CMD-11`, `CMD-17`, `CMD-19`, `CMD-20` |
| SEV-3 | transient or low-impact degradation, no gate-blocking failures, or artifact freshness warning window (75-90 days) | next working cycle | `CMD-11`, `CMD-18`, `CMD-20` |

Command IDs are defined in `Docs/manifest/09_runbook.md#command-map`.

## Reliability Gate Checklist (DIR-02)

- [x] Critical workflow actions persist explicit success/failure records.
- [x] Artifact and evidence operations have deterministic resolution paths.
- [x] Critical workflows have explicit golden-signal SLI/SLO targets.
- [x] Severity routing is defined with runbook command links.
- [x] CI smoke health check exists (`CMD-11`, `CMD-12` mapping in `Docs/manifest/11_ci.md`).
- [x] Artifact provenance coverage and freshness thresholds are defined with command-backed checks (`CMD-19`, `CMD-20`).
- [x] Artifact provenance/freshness SLO checks are auto-enforced in CI (`CMD-26`).
- [x] Objective success metrics (citation integrity + authority-boundary trends) are auto-generated in report output and CI gate checks (`CMD-29`).
- [x] Consolidated observability snapshot synthesis is auto-generated and CI-published (`CMD-32`).

## Artifact Freshness Monitoring (AF-O03)

- Baseline validation: run `CMD-19` to validate artifact index structure and local path consistency.
- Freshness and coverage audit: run `CMD-20` to detect stale (`retrieved_at` > 90 days), malformed timestamps, or missing provenance fields.
- Objective metrics regression report: run `CMD-29` to regenerate `Docs/implementation/reports/objective_metrics_latest.json` and fail on citation/authority metric regressions.
- Objective metrics dashboard and history reports: `CMD-29` also regenerates `Docs/implementation/reports/objective_metrics_dashboard.md`, `Docs/implementation/reports/objective_metrics_history.jsonl`, and `Docs/implementation/reports/objective_metrics_timeline.md`; CI publishes all as `objective-metrics-report` artifact output.
- Observability snapshot synthesis: run `CMD-32` to regenerate `Docs/implementation/reports/observability_snapshot_latest.json` and `Docs/implementation/reports/observability_snapshot_dashboard.md`; CI publishes both as `observability-snapshot-report` artifact output.
- Incident handling:
  - Any `FRESHNESS_STALE`, `MISSING_PROVENANCE`, or `INVALID_RETRIEVED_AT` result is treated as SEV-2 if unresolved for >24h.
  - Any `FRESHNESS_WARN` result (75-90 days) is tracked as SEV-3 and scheduled in the next working cycle.

## Known Gaps

- Alert paging automation is manual (no pager integration in MVP).
- Structured external dashboards are not yet provisioned; runbook triage now includes generated in-repo snapshot dashboard outputs (`CMD-32`) plus CLI checks.
- Objective metrics history is persisted in-repo (`objective_metrics_history.jsonl`) and per-run CI artifacts, but no external TSDB/pager automation exists yet.
- Full e2e gating (`CMD-13`) is release-time; per-PR path currently enforces deterministic subset (`CMD-27`) with warning-budget guardrails.
