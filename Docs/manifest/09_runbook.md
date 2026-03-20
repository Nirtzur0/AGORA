# Runbook

This runbook is the canonical command map for AGORA.

## Command Map

| ID | Command | Purpose | Source |
|---|---|---|---|
| CMD-01 | `make up` | Start local infra stack | `Makefile`, `infra/docker-compose.yml` |
| CMD-02 | `make down` | Stop local infra stack | `Makefile` |
| CMD-03 | `make logs` | Tail infra service logs | `Makefile` |
| CMD-04 | `make dev-core-api` | Run Core API locally | `Makefile`, `apps/core-api/main.py` |
| CMD-05 | `python3 apps/worker/main.py` | Run Temporal worker locally | `apps/worker/main.py` |
| CMD-06 | `make migrate-up` | Apply DB migrations + seed roles | `Makefile`, `packages/db/db/migrate.py` |
| CMD-07 | `make install-core-api` | Install Core API deps | `Makefile` |
| CMD-08 | `make install-db` | Install DB package deps | `Makefile` |
| CMD-09 | `make install-storage` | Install shared storage deps | `Makefile` |
| CMD-10 | `make install-moltbook` | Install Moltbook adapter deps | `Makefile` |
| CMD-11 | `make test` | Fast checks (`check-stubs` + unit tests) | `Makefile` |
| CMD-12 | `make test-all` | Unit + integration test path | `Makefile` |
| CMD-13 | `make test-e2e` | End-to-end tests with warning-budget enforcement | `Makefile`, `scripts/check_full_e2e_warning_budget.py` |
| CMD-14 | `make check-stubs` | Reject TODO/bare-pass in prod dirs | `Makefile` |
| CMD-15 | `python3 packages/project-prompts/scripts/prompt_router.py select --target-root . --phase auto --output Docs/implementation/reports/prompt_execution_plan.md` | Generate prompt routing plan | `packages/project-prompts/scripts/prompt_router.py` |
| CMD-16 | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/integration/worker/test_draft_finalization.py tests/integration/core_api/test_drafts.py` | Authority + finalization-gate regression pack | `tests/integration/worker/`, `tests/integration/core_api/` |
| CMD-17 | `make test-integration` | Full integration reliability check | `Makefile` |
| CMD-18 | `rg -n "phase_changed|finalized|finalization_gate|citation_check" core_api.log apps/worker/worker.log` | Fast signal scan for observability triage | runtime logs |
| CMD-19 | `python3 packages/project-prompts/scripts/web_artifacts.py --repo-root . --store-root Docs/artifacts validate` | Validate artifact registry structure + local consistency | `packages/project-prompts/scripts/web_artifacts.py`, `Docs/artifacts/index.json` |
| CMD-20 | `python3 scripts/check_artifact_freshness.py --index Docs/artifacts/index.json --warn-age-days 75 --max-age-days 90` | Evaluate provenance coverage + artifact freshness SLOs | `scripts/check_artifact_freshness.py`, `Docs/artifacts/index.json` |
| CMD-21 | `npm --prefix apps/web run dev` | Run web UI dev server (Vite) | `apps/web/package.json`, `apps/web/vite.config.js` |
| CMD-22 | `npm --prefix apps/web run build` | Build web UI bundle | `apps/web/package.json` |
| CMD-23 | `npm --prefix apps/web run smoke:artifact-viewer` | Browser smoke for claims/drafts provenance drill-down + artifact viewer | `apps/web/scripts/smoke_artifact_viewer.mjs` |
| CMD-24 | `scripts/preflight_temporal.sh` | Block until Temporal container is healthy (with one restart on exited/dead state) | `scripts/preflight_temporal.sh`, `infra/docker-compose.yml` |
| CMD-25 | `make test-all-guarded` | Unit + integration path with Temporal preflight and one retry on transient Temporal startup failures | `Makefile`, `scripts/run_test_all_with_temporal_guard.sh` |
| CMD-26 | `make check-observability-slos` | Automated observability SLO gate for artifact provenance/freshness thresholds | `Makefile`, `scripts/check_artifact_freshness.py`, `Docs/artifacts/index.json` |
| CMD-27 | `make test-e2e-critical` | Deterministic critical-flow e2e gate (literature-grounding happy path) with warning-budget enforcement | `Makefile`, `scripts/check_critical_e2e_warning_budget.py`, `tests/e2e/workflows/test_literature_grounding.py` |
| CMD-28 | `make check-architecture-coherence` | Validate architecture docs coherence and CI/runbook gate wiring | `Makefile`, `scripts/check_architecture_coherence.py`, `.github/workflows/ci.yml` |
| CMD-29 | `make check-objective-metrics` | Automated objective-metrics gate (citation integrity + authority-boundary regression trends) with latest JSON, dashboard, append-only history JSONL, and timeline report generation | `Makefile`, `scripts/check_objective_metrics.py`, integration regression suites |
| CMD-30 | `npm --prefix apps/web run smoke:artifact-viewer:matrix` | Deterministic cross-browser UI smoke matrix (Chromium/Firefox/WebKit) for provenance drill-down and artifact viewer health | `apps/web/scripts/smoke_artifact_viewer.mjs`, `apps/web/package.json`, `.github/workflows/ci.yml` |
| CMD-31 | `npm --prefix apps/web run smoke:artifact-viewer:mobile` | Deterministic mobile-width smoke for all workspace tabs plus provenance drill-down/artifact viewer health | `apps/web/scripts/smoke_artifact_viewer.mjs`, `apps/web/package.json`, `.github/workflows/ci.yml` |
| CMD-32 | `make check-observability-snapshot` | Generate observability snapshot JSON + dashboard by consolidating artifact freshness/provenance and objective-metric trend signals | `Makefile`, `scripts/check_observability_snapshot.py`, `Docs/implementation/reports/*` |
| CMD-33 | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/paper` | Run paper invariant harness + paper/code contract drift checks | `tests/unit/paper/*`, `paper/implementation_map.md`, `paper/main.tex` |
| CMD-34 | `python3 scripts/generate_paper_verification_snapshot.py --output paper/artifacts/verification_snapshot.json` | Generate deterministic paper verification snapshot artifact | `scripts/generate_paper_verification_snapshot.py`, `paper/artifacts/verification_snapshot.json` |
| CMD-35 | `python3 -m pip install -r dash_app/requirements.txt` | Install Dash data explorer runtime dependencies | `dash_app/requirements.txt` |
| CMD-36 | `python3 dash_app/app.py` | Run Dash data explorer app locally | `dash_app/app.py`, `dash_app/pages/*`, `dash_app/components/*` |
| CMD-37 | `python3 -m dash_app.data.validation --repo-root . --output /tmp/agora-dash-validation.json` | Run headless Dash data-quality validation checks | `dash_app/data/validation.py`, `dash_app/data/loaders.py`, `dash_app/data/catalog.py` |
| CMD-38 | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/test_data_validation.py tests/test_loaders_smoke.py` | Run Dash data loader/validation regression tests | `tests/test_data_validation.py`, `tests/test_loaders_smoke.py` |
| CMD-39 | `python3 scripts/build_ci_runtime_trend.py --summary-file /tmp/cmd-13-nightly-runtime-policy.txt --latest /tmp/cmd-13-nightly-runtime-trend-latest.json --history /tmp/cmd-13-nightly-runtime-trend-history.jsonl --dashboard /tmp/cmd-13-nightly-runtime-trend-dashboard.md` | Build heavy CI runtime/flake trend artifact bundle from runtime policy summary output | `scripts/build_ci_runtime_trend.py`, `.github/workflows/ci.yml` |
| CMD-40 | `make check-observability-sink-dry-run` | Build external observability sink payload/report locally (no network publish) | `Makefile`, `scripts/publish_observability_sink.py`, `Docs/implementation/reports/*` |
| CMD-41 | `make check-sink-evidence-recency` | Enforce periodic sink-evidence recency thresholds for objective/nightly/release gates using workflow history | `Makefile`, `scripts/check_sink_evidence_recency.py`, `.github/workflows/ci.yml` |

## Required Environment Variables

- Core API/Worker runtime:
  - `DATABASE_URL`
  - `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`
  - `TEMPORAL_ADDRESS`, `TEMPORAL_TASK_QUEUE`
  - `MOLTBOOK_ADAPTER_URL`
  - `AGENT_JWT_SECRET`, `SYSTEM_JWT_SECRET`, `SYSTEM_JWT_AUDIENCE`
- Testing warning budgets:
  - `E2E_CRITICAL_WARNING_BUDGET` (`CMD-27`, default `40`)
  - `E2E_FULL_WARNING_BUDGET` (`CMD-13`, default `200`)

## Common Triage Flows

### API not healthy

1. Run `CMD-01` and wait for healthy containers.
2. Run `CMD-04` and hit `GET /health`.
3. Check infra logs with `CMD-03`.

### Test failures

1. Run `CMD-11` first.
2. If integration-related, run `CMD-24` then `CMD-25` with infra up.
3. For flow/UI related issues, run `CMD-23` first, then `CMD-31`, `CMD-30`, `CMD-27`, and `CMD-13`.
4. For authority/finalization regressions, run `CMD-16`.
5. For architecture drift checks, run `CMD-28`.
6. For paper/code drift or invariant-model regressions, run `CMD-33` and `CMD-34`.
7. For Dash explorer regressions, run `CMD-37` and `CMD-38` (and `CMD-36` for manual UI checks).
8. For heavy nightly/release runtime+flake drift, inspect trend outputs from `CMD-39`.
9. For external sink payload verification before live publish, run `CMD-40`.
10. For periodic sink-evidence recency governance checks, run `CMD-41`.

### Observability and Incident Routing

1. Classify severity using `Docs/manifest/07_observability.md#severity-routing`.
2. Run `CMD-18` for fast signal scan.
3. Run `CMD-19`, `CMD-20`, `CMD-26`, `CMD-29`, `CMD-32`, `CMD-40`, and `CMD-41` when objective/citation/authority observability is part of the incident.
4. For SEV-1/SEV-2, run `CMD-17` and capture failing suites + affected workflow IDs.
5. Capture persisted evidence rows (`rule_checks`, `activity_runs`, `logs`, `events`) before applying fixes.

### Migration issues

1. Verify DB container is healthy (`CMD-01`).
2. Rerun migrations with `CMD-06`.
3. Inspect DB migration package logs/output.
