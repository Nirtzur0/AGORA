# Checklist: Alignment Review Gate

Date: 2026-02-09 (fresh checkpoint after `DIR-23` / `AR-C17` enforcement)
Prompt packet: `prompt-03-alignment-review-gate`
Triggering delta: `prompt-02` follow-through implemented periodic sink-evidence recency enforcement (`AR-C17`) in CI/runtime, so residual sink-operability risk needed reranking.
Verdict: `ALIGNED_WITH_RISKS`

Objective anchor: `Docs/manifest/00_overview.md#Core Objective`

## Required Questions

- [x] Are we still building the same thing defined by Core Objective?
  - Evidence: authority boundaries and evidence immutability remain unchanged in `Docs/manifest/00_overview.md`, `Docs/manifest/04_api_contracts.md`, and `Docs/manifest/05_data_model.md`.

- [x] Is the main user journey usable end-to-end right now?
  - Evidence: deterministic critical flow remains green (`make PYTHON=python3 test-e2e-critical` PASS, 2026-02-09).

- [x] Are we measuring the right success metrics from the objective?
  - Evidence: objective/snapshot checks remain green (`make PYTHON=python3 check-objective-metrics`, `make PYTHON=python3 check-observability-snapshot`, both PASS on 2026-02-09).

- [x] Are we spending meaningful effort on explicit non-goals?
  - Evidence: packet scope stayed on CI/release sink-operability governance; no product-scope expansion introduced.

## Evidence-Backed Misalignment Checklist

- [x] M10 and M11 governance outcomes through `AR-C17` are closed.
  - Evidence: `Docs/implementation/checklists/02_milestones.md` and `Docs/implementation/checklists/06_release_readiness.md` now mark `AR-C13`..`AR-C17` closed.

- [ ] Sink troubleshooting guidance still lacks concrete error signatures and first-response owner actions.
  - Evidence: `Docs/reference/release_workflow.md` and `Docs/manifest/11_ci.md` still need the explicit troubleshooting signature matrix planned for `DIR-24` / `AR-C18`.

## Top 3 Next Corrections

- [ ] Correction 1: add sink-failure troubleshooting signature matrix (`DIR-24` / `AR-C18`).
  - Owner type: maintainer
  - Effort: S
  - Target files: `Docs/reference/release_workflow.md`, `Docs/manifest/11_ci.md`, `Docs/implementation/checklists/06_release_readiness.md`
  - Acceptance signal: docs include representative sink-failure signatures, likely causes, first-response actions, and owner routing.

- [ ] Correction 2: rerun alignment checkpoint after `DIR-24` docs follow-through.
  - Owner type: maintainer
  - Effort: S
  - Target files: `Docs/implementation/checklists/07_alignment_review.md`, `Docs/implementation/reports/alignment_review.md`
  - Acceptance signal: fresh rerank confirms no new post-AR-C18 residual risks require immediate implementation.

- [ ] Correction 3: defer additional sink-governance expansion until troubleshooting signatures land.
  - Owner type: maintainer
  - Effort: S
  - Target files: `Docs/implementation/checklists/03_improvement_bets.md`, `Docs/implementation/reports/improvement_directions.md`
  - Acceptance signal: plan stays focused on `DIR-24` + checkpoint, without introducing parallel low-signal work.

## Next Execution Packet Mapping

- [x] Corrections remain mapped to milestone planning references in `Docs/implementation/checklists/02_milestones.md`.
- [x] Recommended next non-redundant packet: `prompt-11-docs-diataxis-release` for `DIR-24` (`AR-C18`), then `prompt-03-alignment-review-gate`.

## Keep-The-Slate-Clean Decision

- Decision: `Reshape Next Bet`
- Closed leftovers: `AR-C13`, `AR-C14`, `AR-C15`, `AR-C16`, `AR-C17`.
- Reshaped leftovers: `DIR-24` troubleshooting signatures remain the primary residual risk.
- Dropped leftovers: none.

## Latest Checkpoint

- [x] 2026-02-09 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/test_sink_evidence_recency.py` -> PASS.
- [x] 2026-02-09 `ruby -e 'require "yaml"; YAML.load_file(".github/workflows/ci.yml"); puts "yaml_ok"'` -> PASS.
- [x] 2026-02-09 `rg -n "run_sink_recency_gate|sink-evidence-recency-gate|check_sink_evidence_recency.py|allow-current-release-candidate|release-sink-evidence-recency" .github/workflows/ci.yml Makefile scripts/check_sink_evidence_recency.py Docs/manifest/09_runbook.md Docs/manifest/11_ci.md Docs/reference/release_workflow.md Docs/implementation/checklists/06_release_readiness.md` -> PASS.
- [x] 2026-02-09 retained remote sink evidence references for guardrail continuity:
  - run URL: `https://github.com/Nirtzur0/AGORA/actions/runs/21824083555`
  - job URL: `https://github.com/Nirtzur0/AGORA/actions/runs/21824083555/job/62964694204`
  - sink artifacts: `objective-metrics-report`, `observability-snapshot-report`
