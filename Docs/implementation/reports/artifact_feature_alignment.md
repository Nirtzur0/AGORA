# Artifact-Feature Alignment Report

Date: 2026-02-08
Prompt packet: `prompt-15-artifact-feature-alignment-gate`
Verdict: `ALIGNED_WITH_GAPS`
Objective anchor: `Docs/manifest/00_overview.md#Core Objective`

## Scope and Method

- Artifact metadata gap: `Docs/artifacts/index.json` does not exist in the repository.
- This run used load-bearing in-repo artifacts (canonical spec/checklists/code/tests) for best-effort alignment mapping and recorded explicit metadata gaps.
- Status vocabulary used in this report:
  - `Supported`: implication is implemented and verified.
  - `Partial`: implication is implemented only in part or lacks complete verification.
  - `Missing`: no mapped implementation/verification exists.
  - `Misaligned`: current behavior conflicts with the artifact implication.

## Artifact Inventory Summary

| Artifact ID | Source type | Role | Affected feature area | Evidence path |
|---|---|---|---|---|
| ART-01 | Canonical contract | Defines authority and finalization invariants | phase transitions, finalization gates | `Docs/manifest/04_api_contracts.md`, `apps/core-api/phase_routes.py`, `apps/core-api/draft_routes.py` |
| ART-02 | Canonical contract | Defines version-pinned evidence + citation requirements | claim evidence, citation checks | `Docs/manifest/04_api_contracts.md`, `apps/worker/citation_check.py`, `tests/e2e/workflows/test_literature_grounding.py` |
| ART-03 | Implementation checklist | Defines completion bar for evidence/artifact reliability | resolver and immutability hardening | `Docs/implementation/checklists/02_milestones.md`, `Docs/implementation/checklists/02_milestones.md` |
| ART-04 | Runtime implementation artifact | Worker dependency lifecycle behavior | Temporal worker startup | `apps/worker/main.py` |
| ART-05 | Artifact grounding policy | Requires stable external-source capture and retrieval metadata | artifact provenance traceability | `packages/project-prompts/charter-artifacts-system.md` |
| ART-06 | Router and planning artifact | Requires explicit artifact-feature gate output and routing | milestone prioritization | `Docs/implementation/reports/prompt_execution_plan.md`, `Docs/implementation/checklists/03_improvement_bets.md` |

## Artifact-to-Feature Matrix

| Artifact ID | Expected implication | Current feature/test coverage | Status (Supported/Partial/Missing/Misaligned) | Evidence paths |
|---|---|---|---|---|
| ART-01 | Only system/orchestrator authority can advance phases and finalize drafts; non-pass gates block finalization with persisted outcomes. | API enforces system-token checks on phase advance/finalize and persists gate decisions to `rule_checks` + `logs`; integration tests cover rejection and persistence paths. | Supported | `apps/core-api/phase_routes.py`, `apps/core-api/draft_routes.py`, `tests/integration/worker/test_phase_machine.py`, `tests/integration/core_api/test_drafts.py` |
| ART-02 | Claim evidence and citations are version-pinned and resolvable with deterministic citation checks on draft creation. | Resolver/citation checks are exercised in integration/e2e tests; citations are materialized idempotently and rule checks are persisted. | Supported | `apps/worker/citation_check.py`, `tests/integration/core_api/test_claims.py`, `tests/integration/core_api/test_evidence_resolver.py`, `tests/e2e/workflows/test_literature_grounding.py` |
| ART-03 | Evidence resolver edge cases and artifact immutability should be fully closed as milestone outcomes. | Resolver now maps repo/log malformed pointers to deterministic codes and ingestion immutability conflict path is covered with explicit 409 behavior tests. | Supported | `apps/core-api/evidence_resolver.py`, `tests/integration/core_api/test_evidence_resolver.py`, `tests/integration/core_api/test_artifacts_exit.py`, `tests/integration/worker/test_repo_ingestion.py` |
| ART-04 | Worker startup should have explicit dependency lifecycle handling (no placeholder lifecycle notes). | Worker startup now loads/validates runtime dependencies and creates DB-scoped activity instances per invocation; targeted integration checks pass. | Supported | `apps/worker/main.py`, `tests/unit/worker/test_main_runtime_deps.py`, `tests/integration/worker/test_pdf_ingestion.py` |
| ART-05 | Load-bearing external artifacts should be captured with stable IDs + retrieval metadata for auditability. | Artifact registry seeded under `Docs/artifacts/index.json` with six metadata-tracked external sources and validation command evidence. | Supported | `Docs/artifacts/index.json`, `Docs/artifacts/README.md`, `packages/project-prompts/scripts/web_artifacts.py` |
| ART-06 | Artifact-feature alignment gate should produce corrective/opportunity outcomes and milestone routing. | This prompt run adds alignment checklist/report and routes outcomes into milestone tracking. | Supported | `Docs/implementation/checklists/08_artifact_feature_alignment.md`, `Docs/implementation/checklists/02_milestones.md` |

## Top Corrective Outcomes

| Outcome ID | Corrective outcome | Owner | Effort | Target files/areas | Acceptance signal | Verification approach | Prompt chain |
|---|---|---|---|---|---|---|---|
| AF-C01 | Initialize artifact registry for load-bearing external sources (stable IDs, URLs/permalinks, retrieval timestamps). | maintainer | S | `Docs/artifacts/index.json`, `Docs/artifacts/README.md`, `Docs/implementation/reports/artifact_feature_alignment.md` | Completed 2026-02-08: six load-bearing artifacts registered with retrieval metadata and validation evidence. | docs check | `prompt-02` -> `prompt-11` -> `prompt-03` |
| AF-C02 | Harden worker dependency lifecycle to remove placeholder startup behavior and ensure deterministic boot dependencies. | maintainer | M | `apps/worker/main.py`, worker bootstrap helpers, `Docs/manifest/01_architecture.md`, `Docs/manifest/09_runbook.md` | Completed 2026-02-08: worker lifecycle now uses startup dependency validation and per-invocation DB-scoped activity construction. | integration | `prompt-04` -> `prompt-02` -> `prompt-10` |
| AF-C03 | Close M2 reliability gaps for evidence resolver edge cases and artifact immutability semantics. | maintainer | M | `apps/core-api/evidence_resolver.py`, `apps/core-api/artifact_routes.py`, `tests/integration/core_api/*`, `tests/integration/worker/test_repo_ingestion.py` | Completed 2026-02-08: deterministic edge-case mappings and immutability conflict tests pass in unit/integration packs. | unit + integration | `prompt-02` -> `prompt-09` -> `prompt-10` -> `prompt-03` |
| AF-C04 | Add CI/docs guardrail for artifact-alignment freshness when reliability-critical files change. | maintainer | S | `.github/workflows/ci.yml`, docs guardrail script block, `Docs/implementation/checklists/08_artifact_feature_alignment.md` | Completed 2026-02-08: docs guardrail now enforces `required_alignment` updates when reliability-critical files are changed in PR diffs. | docs check + CI check | `prompt-02` -> `prompt-11` -> `prompt-03` |

## Top Opportunity Outcomes

| Outcome ID | Opportunity outcome | Owner | Effort | Target files/areas | Acceptance signal | Verification approach | Prompt chain |
|---|---|---|---|---|---|---|---|
| AF-O01 | Add a pre-release artifact-alignment checkpoint as a formal release gate. | maintainer | S | `Docs/implementation/checklists/06_release_readiness.md`, `Docs/reference/release_workflow.md`, `Docs/implementation/checklists/08_artifact_feature_alignment.md` | Completed 2026-02-08: release checklist/workflow now require latest artifact-feature alignment verdict references before sign-off. | docs check | `prompt-11` -> `prompt-03` |
| AF-O02 | Expose artifact provenance drill-down in the audit UI (claim/citation to artifact version evidence paths). | maintainer | M | `apps/web/src/components/EvidenceDrawer.jsx`, `apps/web/src/pages/WorkspacePage.jsx`, `apps/web/src/components/EvidenceDrawer.css`, `apps/web/src/pages/WorkspacePage.css`, `tests/e2e/*` | Completed 2026-02-08: evidence drawer now exposes deterministic artifact-version provenance metadata and opens exact artifact/version drill-down from claim/citation evidence clicks. | e2e | `prompt-02` -> `prompt-06` -> `prompt-10` |
| AF-O03 | Add artifact-freshness monitoring (stale retrieval metadata and missing provenance coverage alerts). | maintainer | M | `Docs/manifest/07_observability.md`, `Docs/manifest/09_runbook.md`, `scripts/check_artifact_freshness.py` | Completed 2026-02-08: observability/runbook now define artifact freshness + provenance coverage thresholds with command-backed triage checks (`CMD-19`, `CMD-20`). | docs check + integration | `prompt-02` -> `prompt-11` -> `prompt-03` |

## Milestone Routing (This Run)

- Marked DIR-05 milestone adoption complete in `Docs/implementation/checklists/02_milestones.md`.
- Added milestone-routed follow-through outcomes (`AF-C01`..`AF-C04`, `AF-O01`..`AF-O03`) as measurable, verification-linked items in `Docs/implementation/checklists/02_milestones.md`.
- Follow-through progress update: `AF-C01`, `AF-C02`, `AF-C03`, `AF-C04`, `AF-O01`, `AF-O02`, and `AF-O03` are now completed with recorded verification evidence.

## Explicit Gaps

- Artifact registry is currently metadata-only (no local blobs captured yet).
- No open artifact-feature corrective/opportunity outcomes remain.
