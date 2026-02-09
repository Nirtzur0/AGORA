# Checklist: Literature Review and Claim Validation

Date: 2026-02-09  
Prompt packet: `prompt-12-research-literature-validation`  
Objective anchor: `Docs/manifest/00_overview.md#Core Objective`

## Bet tracking

- [x] Appetite set: `medium`.
  - Now: complete one bounded literature packet connecting reproducibility/provenance/workflow evidence to AGORA design decisions.
  - Not now: deep benchmark comparison across workflow engines, domain-specific physics-model literature.
  - State: moved from `uphill` to `downhill` after stable DOI-backed source set converged.

## Required outputs

- [x] Curated literature review exists in manifest docs.
  - AC: `Docs/manifest/20_literature_review.md` includes required sections and decision-oriented synthesis.
  - Verify: `rg -n "^## 1\. Problem statement|^## 2\. Scope and regimes|^## 3\. Canonical references|^## 4\. Key claims|^## 5\. Competing viewpoints / contradictions|^## 6\. What this means for this project|^## 7\. Proposed validation checklist" Docs/manifest/20_literature_review.md`
  - Files: `Docs/manifest/20_literature_review.md`
  - Docs: `Docs/manifest/20_literature_review.md`
  - Alternatives: N/A

- [x] Reproducible search/validation log exists.
  - AC: `Docs/implementation/reports/20_literature_review_log.md` includes search queries, inclusion/exclusion rationale, bibliographic table, claim extraction notes, and artifact mapping.
  - Verify: `rg -n "^## 3\. Search log and inclusion/exclusion method|^## 4\. Canonical included sources|^## 6\. Artifact traceability map|^## 7\. Per-source claim extraction notes" Docs/implementation/reports/20_literature_review_log.md`
  - Files: `Docs/implementation/reports/20_literature_review_log.md`
  - Docs: `Docs/implementation/reports/20_literature_review_log.md`
  - Alternatives: N/A

- [x] Checklist of done/verified steps exists.
  - AC: this checklist provides explicit AC + verification commands and tracks bet scope.
  - Verify: `rg -n "AC:|Verify:|Files:|Docs:" Docs/implementation/checklists/20_literature_review.md`
  - Files: `Docs/implementation/checklists/20_literature_review.md`
  - Docs: `Docs/implementation/checklists/20_literature_review.md`
  - Alternatives: N/A

## Source quality + traceability requirements

- [x] At least 10 stable-identifier sources included.
  - AC: review/log contain >=10 DOI-backed sources.
  - Verify: `rg -o "10\.[0-9]{4,9}/[-._;()/:A-Z0-9a-z]+" Docs/manifest/20_literature_review.md Docs/implementation/reports/20_literature_review_log.md | sort -u | wc -l`
  - Files: `Docs/manifest/20_literature_review.md`, `Docs/implementation/reports/20_literature_review_log.md`
  - Docs: same as files
  - Alternatives: N/A

- [x] Load-bearing external sources are artifact-indexed.
  - AC: each included source has an artifact ID entry in `Docs/artifacts/index.json`.
  - Verify: `python3 packages/project-prompts/scripts/web_artifacts.py --repo-root . --store-root Docs/artifacts validate && rg -n "EXT-LIT-(FAIR|DATACITE|SOFTWARECITE|PENG-2011|SANDVE-2013|SIMMHAN-2005|PEGASUS-2015|GALAXY-2010|SNAKEMAKE-2012|NEXTFLOW-2017)-001" Docs/artifacts/index.json`
  - Files: `Docs/artifacts/index.json`
  - Docs: `Docs/manifest/20_literature_review.md`, `Docs/implementation/reports/20_literature_review_log.md`
  - Alternatives: N/A

## Integration into existing docs system

- [x] New literature artifacts are linked from docs navigation.
  - AC: docs index and reports index include the new literature files.
  - Verify: `rg -n "20_literature_review" Docs/INDEX.md Docs/implementation/reports/README.md`
  - Files: `Docs/INDEX.md`, `Docs/implementation/reports/README.md`
  - Docs: same as files
  - Alternatives: N/A

- [x] Status/worklog/decision trail updated for this packet.
  - AC: status snapshot, worklog, and decisions include this prompt run and evidence pointers.
  - Verify: `rg -n "prompt-12-research-literature-validation|20_literature_review" Docs/implementation/00_status.md Docs/implementation/03_worklog.md Docs/manifest/03_decisions.md`
  - Files: `Docs/implementation/00_status.md`, `Docs/implementation/03_worklog.md`, `Docs/manifest/03_decisions.md`
  - Docs: same as files
  - Alternatives: N/A

## Residual risks

- [x] Residual risk explicitly captured.
  - Risk: claims in this packet are strategy/architecture guidance, not direct empirical re-benchmarking in this repo.
  - Mitigation: route open items into follow-on validation packets (failure-path depth and observability routing depth).

## Follow-through validation (2026-02-09, prompt-11 release packet)

- [x] Section 7 validation checklist in `Docs/manifest/20_literature_review.md` fully executed and marked complete.
  - Verify:
    - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/core_api/test_evidence_resolver.py tests/integration/worker/test_citation_checks.py` -> PASS (`16 passed`)
    - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/worker/test_phase_machine.py tests/integration/core_api/test_drafts.py` -> PASS (`21 passed`)
    - `make PYTHON=python3 test-e2e-critical` -> PASS (`1 passed`)
    - `make PYTHON=python3 check-observability-snapshot` -> PASS
    - `make PYTHON=python3 check-observability-slos` -> PASS
    - `rg -n "20_literature_review|literature" Docs/INDEX.md Docs/implementation/checklists/06_release_readiness.md Docs/implementation/checklists/20_literature_review.md` -> PASS
- [x] Release-readiness checklist now explicitly includes literature-backed risk review reference.
  - Files: `Docs/implementation/checklists/06_release_readiness.md`, `Docs/manifest/20_literature_review.md`
