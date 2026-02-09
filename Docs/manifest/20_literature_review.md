# Literature Review: Reproducible, Provenance-Centric Computational Research Systems

Date: 2026-02-09  
Prompt packet: `prompt-12-research-literature-validation`

## 1. Problem statement

AGORA's core objective is to produce auditable, reproducible research outputs where every finalized claim is backed by version-pinned, resolvable evidence and all critical state transitions are orchestrator-controlled. This review evaluates literature on reproducibility, provenance, citation rigor, and workflow orchestration to validate whether AGORA's architecture and guardrails are aligned with established research-system practice.

## 2. Scope and regimes

- Topic boundary: reproducible computational research systems and provenance-aware workflow platforms.
- In scope:
  - citation and evidence traceability norms,
  - provenance capture and retrieval expectations,
  - workflow engine design for deterministic/reproducible execution,
  - practical operational patterns for repeatable computational pipelines.
- Out of scope:
  - domain-specific physics model validity,
  - large-scale production multi-tenant operations,
  - deep benchmark comparisons across all workflow engines.
- Target application:
  - AGORA's current stack (`FastAPI` + `Temporal` + `Postgres` + `MinIO`) and MVP invariants in `Docs/04-system-implementation-spec.md`.
- Regime constraints for this synthesis:
  - small-to-medium research teams,
  - high traceability and auditability requirements,
  - deterministic evidence resolution as a non-negotiable.

## 3. Canonical references

| Key | Reference | Stable identifier | Artifact ID | Why included |
| --- | --- | --- | --- | --- |
| R1 | Wilkinson et al. (2016), "The FAIR Guiding Principles for scientific data management and stewardship" | DOI: `10.1038/sdata.2016.18` | `EXT-LIT-FAIR-001` | Baseline principles for findable, accessible, interoperable, reusable artifacts. |
| R2 | Data Citation Synthesis Group (2014), "Joint Declaration of Data Citation Principles" | DOI: `10.25490/a97f-egyk` | `EXT-LIT-DATACITE-001` | Normative citation principles supporting AGORA's version-pinned evidence contract. |
| R3 | Smith et al. (2016), "Software citation principles" | DOI: `10.7717/peerj-cs.86` | `EXT-LIT-SOFTWARECITE-001` | Directly relevant to citing executable artifacts and software-derived outputs. |
| R4 | Peng (2011), "Reproducible Research in Computational Science" | DOI: `10.1126/science.1213847` | `EXT-LIT-PENG-2011-001` | High-level reproducibility framing: code/data availability and repeatability norms. |
| R5 | Sandve et al. (2013), "Ten Simple Rules for Reproducible Computational Research" | DOI: `10.1371/journal.pcbi.1003285` | `EXT-LIT-SANDVE-2013-001` | Operational reproducibility checklist useful for AGORA runbook/checklist design. |
| R6 | Simmhan et al. (2005), "A Survey of Data Provenance in e-Science" | DOI: `10.1145/1084805.1084812` | `EXT-LIT-SIMMHAN-2005-001` | Provenance taxonomy grounding AGORA's append-only logs/events and evidence resolvers. |
| R7 | Deelman et al. (2015), "Pegasus, a workflow management system for science automation" | DOI: `10.1016/j.future.2014.10.008` | `EXT-LIT-PEGASUS-2015-001` | Reliable workflow orchestration patterns and fault-tolerant execution assumptions. |
| R8 | Goecks et al. (2010), "Galaxy: ... accessible, reproducible, and transparent computational research" | DOI: `10.1186/gb-2010-11-8-r86` | `EXT-LIT-GALAXY-2010-001` | User-facing provenance + workflow transparency principles. |
| R9 | Koster and Rahmann (2012), "Snakemake--a scalable bioinformatics workflow engine" | DOI: `10.1093/bioinformatics/bts480` | `EXT-LIT-SNAKEMAKE-2012-001` | Declarative workflow semantics and reproducible dependency-driven runs. |
| R10 | Di Tommaso et al. (2017), "Nextflow enables reproducible computational workflows" | DOI: `10.1038/nbt.3820` | `EXT-LIT-NEXTFLOW-2017-001` | Portable, container-friendly reproducibility model for heterogeneous execution. |

## 4. Key claims

| Claim | Source | Assumptions | Evidence | Confidence | Implications for AGORA |
| --- | --- | --- | --- | --- | --- |
| Persistent identifiers are required for robust long-term reuse and citation. | R1, R2, R3 | Artifacts remain retrievable and metadata remains stable. | Consensus principles and policy synthesis. | High | Reinforces AGORA requirement that citations resolve to explicit `artifact_versions.id` + deterministic location. |
| Reproducibility requires exact linkage between claims and the code/data state used to produce them. | R4, R5 | Execution environment and input set are sufficiently controlled. | Perspective + practical rule set. | High | Supports AGORA append-only logs/events and immutable artifact versioning model. |
| Provenance systems must capture both data lineage and process lineage to support audit and debugging. | R6 | Workflow steps are observable and persisted. | Survey taxonomy across e-science systems. | High | Supports storing both `workflow_runs`/`activity_runs` and claim/evidence mappings. |
| Workflow reliability needs explicit handling of transient failures and heterogeneous resources. | R7 | Failures are common in distributed workflows. | Large-scale workflow system experience. | High | Justifies AGORA Temporal preflight/retry patterns and explicit failure persistence. |
| Accessible UI-level history/provenance improves scientific transparency and trust. | R8 | Users can inspect lineage without deep infra knowledge. | System design + adoption outcomes. | Medium | Supports AGORA web provenance drill-down (`EvidenceDrawer` -> artifact viewer). |
| Declarative workflows improve repeatability by making dependencies and execution graph explicit. | R9 | Pipeline steps are codified declaratively and inputs are versioned. | Engine design and practical use cases. | Medium | Encourages AGORA to keep task/rule/run states explicit and machine-checkable. |
| Reproducibility portability improves when execution is isolated from host-specific environment drift. | R10 | Container/runtime encapsulation is available and controlled. | Workflow engine design with portable execution. | Medium | Supports AGORA sandbox isolation direction and deterministic run-capture artifacts. |
| Data citation principles require specificity and verifiability, not vague "latest" references. | R2 | Data provider maintains citation metadata. | Community principle set. | High | Aligns with AGORA ban on non-version-pinned evidence pointers. |
| Software outputs should be citable as first-class scholarly objects. | R3 | Software versions are identifiable and retained. | Community principle set. | High | Supports treating sandbox logs/artifacts and repository ingests as citable evidence objects. |
| Reproducibility maturity depends on documented workflows and automated checks, not ad hoc conventions. | R5, R7, R9, R10 | Teams adopt runbooks + CI gates consistently. | Rules + workflow platform experiences. | Medium | Validates AGORA's command-mapped runbook/CI discipline (`CMD-*` mapped checks). |

## 5. Competing viewpoints / contradictions

- "Strict determinism" vs "practical reproducibility":
  - R4/R5 emphasize reproducibility practices but allow pragmatic tolerances.
  - R7/R10 acknowledge distributed workflow realities where retries and infrastructure variability exist.
  - AGORA resolution: enforce deterministic evidence/citation resolution and orchestrator authority while allowing controlled operational retries (with explicit persistence and audit traces).

- "Accessibility-first interactive systems" vs "engine-first declarative systems":
  - R8 emphasizes usability and transparency for broad users.
  - R9/R10 emphasize declarative engine semantics and portable execution.
  - AGORA resolution: maintain API/orchestrator rigor while preserving evidence drill-down UI and human-auditable logs.

## 6. What this means for this project

### Recommended modeling choices (build/keep)

- Keep evidence model as strict version-pinned references (`artifact_versions.id` + deterministic `location`).
- Keep append-only audit memory (`logs`, `events`) and explicit gate outcomes (`rule_checks`, `activity_runs`).
- Keep single-locus authority for phase/finalization under orchestrator workflows only.

### Recommended algorithm/system behavior

- Preserve deterministic resolver grammar and explicit failure codes (no silent fallback).
- Keep workflow startup/retry handling explicit and bounded (`preflight_temporal.sh`, guarded integration path), with persisted failure evidence.
- Continue CI command-map enforcement so reproducibility checks remain runnable and auditable.

### Validation plan impact

- Continue objective metrics + observability snapshots as quality evidence, but expand toward runtime alert routing depth.
- Add explicit failure-path workflow coverage where current reports still note gaps (critical workflow failure-path depth is still partially open in testing landscape docs).

### Known pitfalls

- "Operationally green" can mask weak provenance discipline if citation/version checks are bypassed.
- High warning noise can degrade trust in failure signals even when tests pass.
- Partial observability automation (without pager/routing integration) can delay response despite good detection.

### Open questions

- Which additional workflow failure-path properties should be mandatory in deterministic e2e checks?
- What is the minimum alert-routing integration required for release-readiness beyond artifact/objective dashboards?

## 7. Proposed validation checklist

- [x] Citation specificity gate remains strict.
  - Verify: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/core_api/test_evidence_resolver.py tests/integration/worker/test_citation_checks.py`
  - Evidence: PASS (`16 passed`, 2026-02-09).
- [x] Orchestrator-only authority remains enforced.
  - Verify: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/integration/worker/test_phase_machine.py tests/integration/core_api/test_drafts.py`
  - Evidence: PASS (`21 passed`, 2026-02-09).
- [x] Deterministic critical e2e remains green.
  - Verify: `make PYTHON=python3 test-e2e-critical`
  - Evidence: PASS (`1 passed`, 2026-02-09).
- [x] Observability snapshot remains command-generated and CI-published.
  - Verify: `make PYTHON=python3 check-observability-snapshot`
  - Evidence: PASS (`observability_snapshot_summary status=pass`, 2026-02-09).
- [x] Artifact provenance/freshness signals remain in policy bounds.
  - Verify: `make PYTHON=python3 check-observability-slos`
  - Evidence: PASS (`artifact_freshness_summary ... status=pass`, 2026-02-09).
- [x] Release-readiness includes current literature-backed risk review.
  - Verify: `rg -n "20_literature_review|literature" Docs/INDEX.md Docs/implementation/checklists/06_release_readiness.md Docs/implementation/checklists/20_literature_review.md`
  - Evidence: PASS (link/reference grep output present, 2026-02-09).
