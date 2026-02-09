# Observability

This page is the observability and reliability gate for AGORA runtime workflows.

## Critical Workflows

1. Authentication and workspace join.
2. Artifact ingestion (PDF/repo) and artifact version creation.
3. Evidence resolution and claim/citation linkage.
4. Draft finalization and rule-check gating.
5. External artifact registry freshness and provenance coverage.
6. Objective metrics automation for citation integrity and authority-boundary regressions.
7. Heavy CI runtime/flake trend monitoring for nightly and release gates.
8. External sink publishing for CI observability payloads.

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
| Heavy CI gates | Runtime/flake trend | per-run runtime trend bundle exists for `cmd-13-nightly-full-suite` and `release-tag-gate` with elapsed/runtime-target/retry data | 100% heavy runs publish trend bundle; treat 2 consecutive runtime-target misses or retry usage in 3 of latest 5 runs as SEV-2 | `.github/workflows/ci.yml`, `scripts/build_ci_runtime_trend.py`, `cmd-13-nightly-runtime-trend`, `release-tag-gate-artifacts` |

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
- [x] External sink publish pipeline is implemented with fail-open rollout controls (`CMD-40` + CI publish steps in heavy/objective jobs).

## Artifact Freshness Monitoring (AF-O03)

- Baseline validation: run `CMD-19` to validate artifact index structure and local path consistency.
- Freshness and coverage audit: run `CMD-20` to detect stale (`retrieved_at` > 90 days), malformed timestamps, or missing provenance fields.
- Objective metrics regression report: run `CMD-29` to regenerate `Docs/implementation/reports/objective_metrics_latest.json` and fail on citation/authority metric regressions.
- Objective metrics dashboard and history reports: `CMD-29` also regenerates `Docs/implementation/reports/objective_metrics_dashboard.md`, `Docs/implementation/reports/objective_metrics_history.jsonl`, and `Docs/implementation/reports/objective_metrics_timeline.md`; CI publishes all as `objective-metrics-report` artifact output.
- Observability snapshot synthesis: run `CMD-32` to regenerate `Docs/implementation/reports/observability_snapshot_latest.json` and `Docs/implementation/reports/observability_snapshot_dashboard.md`; CI publishes both as `observability-snapshot-report` artifact output.
- Heavy CI runtime trend synthesis: run `python3 scripts/build_ci_runtime_trend.py --summary-file /tmp/cmd-13-nightly-runtime-policy.txt --latest /tmp/cmd-13-nightly-runtime-trend-latest.json --history /tmp/cmd-13-nightly-runtime-trend-history.jsonl --dashboard /tmp/cmd-13-nightly-runtime-trend-dashboard.md`; CI runs this automatically for nightly and release heavy gates.
- External sink payload dry-run: run `CMD-40` to regenerate `Docs/implementation/reports/observability_sink_publish_latest.json` and `Docs/implementation/reports/observability_sink_publish_dashboard.md`.
- Incident handling:
  - Any `FRESHNESS_STALE`, `MISSING_PROVENANCE`, or `INVALID_RETRIEVED_AT` result is treated as SEV-2 if unresolved for >24h.
  - Any `FRESHNESS_WARN` result (75-90 days) is tracked as SEV-3 and scheduled in the next working cycle.

## External Sink Ownership and Escalation Policy (`AR-C12`)

Status: implemented with fail-open rollout.

### Ownership Model

| Role | Responsibility | Escalation SLA |
|---|---|---|
| Maintainer on-call (primary) | Owns first response for external sink alerts and triage routing | Acknowledge SEV-1 immediately, SEV-2 within 30 minutes |
| Release owner (secondary) | Approves release-impacting actions when sink signals indicate gating risk | Same business day for SEV-2, immediate for SEV-1 during release windows |
| Core API/Worker maintainer (backup) | Owns remediation when signal source is objective metrics, workflow runs, or persistence | Join incident within 60 minutes for SEV-2 |

### Signal-to-Severity Mapping for External Routing

| Signal source | Trigger | Severity | Owner |
|---|---|---|---|
| `CMD-29` objective metrics gate | any `overall.status=fail` in `objective_metrics_latest.json` | SEV-1 | Maintainer on-call |
| `CMD-32` observability snapshot | `overall_status=fail` in `observability_snapshot_latest.json` | SEV-1 | Maintainer on-call |
| `CMD-39` heavy-gate trend output | 2 consecutive runtime-target misses or retries in 3 of latest 5 runs | SEV-2 | Release owner + maintainer on-call |
| `CMD-20` freshness audit | stale/missing provenance unresolved >24h | SEV-2 | Maintainer on-call |
| `CMD-20` freshness warning | warning window (75-90 days), no hard breach | SEV-3 | Next working cycle owner |

### Rollout and Fallback Policy

1. CI supports `disabled`, `dry_run`, and `active` sink modes (`workflow_dispatch` input `observability_sink_mode`; URL from input override or `OBSERVABILITY_SINK_URL` secret).
2. Current default rollout is fail-open: sink-delivery failures do not block CI promotion and triage continues from in-repo artifacts and job summaries.
3. If sink delivery fails, responders must use in-repo fallback signals:
   - `CMD-29` outputs (`objective_metrics_*`)
   - `CMD-32` outputs (`observability_snapshot_*`)
   - `CMD-39` heavy-job trend artifacts
4. Pager-backed fail-closed behavior remains deferred until a later tightening packet explicitly flips fail-open policy.

### Current CI Publish Paths

1. `objective-metrics-gate` publishes objective + observability snapshot payloads using `scripts/publish_observability_sink.py`.
2. `cmd-13-nightly-full-suite` publishes runtime trend payloads and includes sink report artifacts.
3. `release-tag-gate` publishes release runtime trend payloads and includes sink report artifacts.
4. First remote active-mode evidence exists in run `21813367976` (job `62929945541`) with sink report status `pass` and response `200`.

## Known Gaps

- Structured external dashboards are not yet provisioned; runbook triage now includes generated in-repo snapshot dashboard outputs (`CMD-32`) and heavy-gate runtime trend artifacts plus CLI checks.
- Objective metrics history is persisted in-repo (`objective_metrics_history.jsonl`) and per-run CI artifacts, but no external TSDB/pager automation exists yet.
- External sink routing is fail-open by policy; fail-closed escalation gating is deferred.
- Full e2e gating (`CMD-13`) is release-time; per-PR path currently enforces deterministic subset (`CMD-27`) with warning-budget guardrails.
