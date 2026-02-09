# Checklist: Artifact-Feature Alignment

Date: 2026-02-08
Prompt packet: `prompt-15-artifact-feature-alignment-gate`
Verdict: `ALIGNED_WITH_GAPS`
Report: `Docs/implementation/reports/artifact_feature_alignment.md`

## Corrective Outcomes

- [x] AF-C01: Seed an external artifact registry for load-bearing sources.
  - Owner type: maintainer
  - Effort: S
  - Target files/areas: `Docs/artifacts/index.json`, `Docs/artifacts/README.md`, `Docs/implementation/reports/artifact_feature_alignment.md`
  - Acceptance signal: at least 5 load-bearing artifacts are recorded with `id`, `url`, and `retrieved_at` metadata.
  - Verification method: docs check
  - Verify: `test -f Docs/artifacts/index.json && rg -n '"id"|"url"|"retrieved_at"' Docs/artifacts/index.json && python3 packages/project-prompts/scripts/web_artifacts.py --repo-root . --store-root Docs/artifacts validate` (PASS, 2026-02-08).
  - Prompt chain: `prompt-02` -> `prompt-11` -> `prompt-03`

- [x] AF-C02: Replace worker bootstrap placeholder lifecycle behavior with explicit dependency lifecycle handling.
  - Owner type: maintainer
  - Effort: M
  - Target files/areas: `apps/worker/main.py`, worker bootstrap helpers, `Docs/manifest/01_architecture.md`, `Docs/manifest/09_runbook.md`
  - Acceptance signal: worker startup path is deterministic and no placeholder lifecycle notes remain.
  - Verification method: integration
  - Verify: `make up` (PASS), `PYTHONPATH=packages/db:packages/shared-types:apps/worker python3 - <<'PY' ... wm._load_runtime_dependencies(); wm._validate_runtime_dependencies(deps) ... PY` (PASS), `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/worker/test_pdf_ingestion.py` (PASS), `make down` (PASS) (2026-02-08).
  - Prompt chain: `prompt-04` -> `prompt-02` -> `prompt-10`

- [x] AF-C03: Close M2 artifact/evidence reliability gaps with deterministic failure-path coverage.
  - Owner type: maintainer
  - Effort: M
  - Target files/areas: `apps/core-api/evidence_resolver.py`, `apps/core-api/artifact_routes.py`, `tests/integration/core_api/test_evidence_resolver.py`, `tests/integration/core_api/test_artifacts_exit.py`
  - Acceptance signal: milestone M2 reliability items are checked with passing deterministic edge-case tests.
  - Verification method: unit + integration
  - Verify: `make test-unit` (PASS), `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/core_api/test_evidence_resolver.py tests/integration/core_api/test_artifacts_exit.py tests/integration/worker/test_repo_ingestion.py` (PASS), `make test-integration` (PASS) (2026-02-08).
  - Prompt chain: `prompt-02` -> `prompt-09` -> `prompt-10` -> `prompt-03`

- [x] AF-C04: Enforce artifact-alignment documentation freshness in CI/docs guardrails.
  - Owner type: maintainer
  - Effort: S
  - Target files/areas: `.github/workflows/ci.yml`, docs guardrail job logic, `Docs/implementation/checklists/08_artifact_feature_alignment.md`
  - Acceptance signal: CI fails when reliability-critical file changes skip status/worklog/alignment updates.
  - Verification method: docs check + contract
  - Verify: `rg -n "required_alignment|reliability_changes|test_evidence_resolver|Docs/artifacts" .github/workflows/ci.yml` (PASS, 2026-02-08), `make test` (PASS, 2026-02-08).
  - Prompt chain: `prompt-02` -> `prompt-11` -> `prompt-03`

## Opportunity Outcomes

- [x] AF-O01: Add artifact-alignment checkpoint to release readiness as a formal gate.
  - Owner type: maintainer
  - Effort: S
  - Target files/areas: `Docs/implementation/checklists/06_release_readiness.md`, `Docs/reference/release_workflow.md`, `Docs/implementation/checklists/08_artifact_feature_alignment.md`
  - Acceptance signal: release checklist requires latest alignment verdict reference before sign-off.
  - Verification method: docs check
  - Verify: `rg -n 'artifact[- ]feature alignment|alignment verdict|08_artifact_feature_alignment' Docs/implementation/checklists/06_release_readiness.md Docs/reference/release_workflow.md` (PASS, 2026-02-08).
  - Prompt chain: `prompt-11` -> `prompt-03`

- [x] AF-O02: Add artifact provenance drill-down to the web audit UI.
  - Owner type: maintainer
  - Effort: M
  - Target files/areas: `apps/web/src/components/EvidenceDrawer.jsx`, `apps/web/src/pages/WorkspacePage.jsx`, `apps/web/src/components/EvidenceDrawer.css`, `apps/web/src/pages/WorkspacePage.css`, `tests/e2e/*`
  - Acceptance signal: users can navigate from claims/citations to deterministic artifact-version evidence metadata in UI.
  - Verification method: e2e
  - Verify: `npm --prefix apps/web run build` (PASS, 2026-02-08), `make up` (PASS, 2026-02-08), `make test-e2e` (PASS, 2026-02-08), `make down` (PASS, 2026-02-08).
  - Prompt chain: `prompt-02` -> `prompt-06` -> `prompt-10`

- [x] AF-O03: Introduce artifact freshness observability signals.
  - Owner type: maintainer
  - Effort: M
  - Target files/areas: `Docs/manifest/07_observability.md`, `Docs/manifest/09_runbook.md`, `scripts/check_artifact_freshness.py`
  - Acceptance signal: freshness SLI/SLO and incident routing are documented for stale or missing artifact metadata.
  - Verification method: docs check + integration
  - Verify: `python3 scripts/check_artifact_freshness.py --index Docs/artifacts/index.json --warn-age-days 75 --max-age-days 90` (PASS, 2026-02-08), docs review (`Docs/manifest/07_observability.md`, `Docs/manifest/09_runbook.md`), `make test-integration` (PASS, 2026-02-08).
  - Prompt chain: `prompt-02` -> `prompt-11` -> `prompt-03`
