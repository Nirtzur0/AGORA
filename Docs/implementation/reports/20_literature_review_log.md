# Literature Review Validation Log

Date: 2026-02-09  
Prompt packet: `prompt-12-research-literature-validation`

## 1. Scope, regimes, and constraints

- Scope: reproducibility/provenance/workflow-orchestration evidence relevant to AGORA architecture and invariants.
- Regime: collaborative computational research systems with strong auditability requirements.
- Constraints:
  - prioritize primary or consensus sources with stable identifiers (DOI),
  - tie conclusions to AGORA files/contracts instead of generic platform advice,
  - keep one bounded question cluster active in this packet.

## 2. Research questions (Now cluster)

1. Which literature-backed principles most directly justify AGORA's version-pinned citation model?
2. What provenance properties are required to support deterministic audit/replay of research workflows?
3. Which workflow-system design patterns best support reproducibility under infra variability?
4. What contradictions exist between strict determinism and practical distributed execution?
5. Which validations should remain mandatory in AGORA's runbook/CI surface to maintain reproducibility integrity?

Not now:
- Deep quantitative benchmark comparison across workflow engines.
- Domain-specific physics-model validation standards.

State: `downhill` (path to completion became clear after source set converged).

## 3. Search log and inclusion/exclusion method

### Queries used

- "10.1038/sdata.2016.18 FAIR Guiding Principles"
- "10.25490/a97f-egyk data citation principles"
- "10.7717/peerj-cs.86 software citation principles"
- "10.1126/science.1213847 reproducible research computational science"
- "10.1371/journal.pcbi.1003285"
- "10.1145/1084805.1084812 provenance e-science"
- "10.1016/j.future.2014.10.008 pegasus workflow"
- "10.1186/gb-2010-11-8-r86 galaxy reproducible"
- "10.1093/bioinformatics/bts480 snakemake"
- "10.1038/nbt.3820 nextflow"

### Where searched

- DOI resolver endpoints (`doi.org`).
- Publisher/journal landing pages surfaced via DOI/title search.
- Existing AGORA objective/spec docs for alignment target:
  - `Docs/manifest/00_overview.md`
  - `Docs/04-system-implementation-spec.md`
  - `Docs/06-implementation-checklist.md`

### Inclusion criteria

- Stable identifier available (DOI).
- Direct relevance to reproducibility, provenance, citations, or computational workflow orchestration.
- Actionable implications for AGORA design/gates.

### Exclusion criteria

- Blog-only sources without stable scholarly identifier.
- Vendor product pages without methodological evidence.
- Sources that did not materially change AGORA decisions/checks.

## 4. Canonical included sources (bibliographic details)

| Key | Citation (short) | DOI | Year |
| --- | --- | --- | --- |
| R1 | Wilkinson et al., FAIR Guiding Principles | `10.1038/sdata.2016.18` | 2016 |
| R2 | Data Citation Synthesis Group, Joint Declaration of Data Citation Principles | `10.25490/a97f-egyk` | 2014 |
| R3 | Smith et al., Software citation principles | `10.7717/peerj-cs.86` | 2016 |
| R4 | Peng, Reproducible Research in Computational Science | `10.1126/science.1213847` | 2011 |
| R5 | Sandve et al., Ten Simple Rules for Reproducible Computational Research | `10.1371/journal.pcbi.1003285` | 2013 |
| R6 | Simmhan et al., A Survey of Data Provenance in e-Science | `10.1145/1084805.1084812` | 2005 |
| R7 | Deelman et al., Pegasus workflow management system | `10.1016/j.future.2014.10.008` | 2015 |
| R8 | Goecks et al., Galaxy and reproducible computational research | `10.1186/gb-2010-11-8-r86` | 2010 |
| R9 | Koster and Rahmann, Snakemake workflow engine | `10.1093/bioinformatics/bts480` | 2012 |
| R10 | Di Tommaso et al., Nextflow reproducible workflows | `10.1038/nbt.3820` | 2017 |

## 5. Sources considered but excluded

| Candidate | Reason excluded |
| --- | --- |
| Generic tool blog posts on "reproducibility best practices" | Lacked stable scholarly identifier and added no unique claim beyond included papers. |
| Non-peer-reviewed vendor walkthroughs for workflow products | Product-specific guidance, weak transferability to AGORA architecture decisions. |
| Duplicate summaries re-stating FAIR/Data Citation principles | Redundant with R1/R2 canonical sources. |

## 6. Artifact traceability map

| Source/Citation | Artifact ID | Usage in review | Notes |
| --- | --- | --- | --- |
| R1 | `EXT-LIT-FAIR-001` | Motivation for persistent IDs/metadata requirements. | Metadata-only capture via DOI. |
| R2 | `EXT-LIT-DATACITE-001` | Citation specificity and verifiability principles. | Supports version-pinned evidence rationale. |
| R3 | `EXT-LIT-SOFTWARECITE-001` | Software/artifact citation as first-class research object. | Supports code/log artifact citation treatment. |
| R4 | `EXT-LIT-PENG-2011-001` | Reproducibility minimum-bar framing. | Used in problem statement and synthesis. |
| R5 | `EXT-LIT-SANDVE-2013-001` | Operational reproducibility practices. | Used in validation checklist and guardrail rationale. |
| R6 | `EXT-LIT-SIMMHAN-2005-001` | Provenance taxonomy grounding. | Supports audit table + resolver expectations. |
| R7 | `EXT-LIT-PEGASUS-2015-001` | Reliability/fault-handling workflow evidence. | Supports guarded startup/retry policy framing. |
| R8 | `EXT-LIT-GALAXY-2010-001` | Usability + transparency in reproducible workflows. | Supports UI provenance drill-down value. |
| R9 | `EXT-LIT-SNAKEMAKE-2012-001` | Declarative workflow reproducibility tradeoffs. | Supports explicit run/task dependencies. |
| R10 | `EXT-LIT-NEXTFLOW-2017-001` | Container/portability execution reproducibility. | Supports sandbox portability direction. |

## 7. Per-source claim extraction notes

### R1 - FAIR Guiding Principles (`10.1038/sdata.2016.18`)

- Claim 1: machine-actionable metadata and persistent identifiers are necessary for Findable and Reusable objects.
  - Assumptions: metadata remains maintained and indexed.
  - Evidence type: community framework synthesis.
  - Confidence: High.
- Claim 2: interoperability requires explicit formal/shared vocabularies rather than ad hoc text descriptions.
  - Assumptions: communities can converge on schemas.
  - Evidence type: principle-level argument.
  - Confidence: Medium.
- Claim 3: reusability depends on rich provenance metadata and clear usage context.
  - Assumptions: provenance is captured at creation time.
  - Evidence type: principle synthesis.
  - Confidence: High.

### R2 - Data Citation Principles (`10.25490/a97f-egyk`)

- Claim 1: data citations should enable identification and access to exact cited evidence.
  - Assumptions: repositories keep stable identifiers resolvable.
  - Evidence type: consensus principles.
  - Confidence: High.
- Claim 2: citation must support verification and reproducibility, not only attribution.
  - Assumptions: citation metadata includes enough detail to reproduce retrieval.
  - Evidence type: consensus principles.
  - Confidence: High.
- Claim 3: machine and human readability are both required for scalable data citation workflows.
  - Assumptions: systems expose structured citation metadata.
  - Evidence type: consensus principles.
  - Confidence: High.

### R3 - Software Citation Principles (`10.7717/peerj-cs.86`)

- Claim 1: software should be citable as a legitimate scholarly product.
  - Assumptions: software versions/metadata are preserved.
  - Evidence type: community principles.
  - Confidence: High.
- Claim 2: citations should identify the specific software version used.
  - Assumptions: versioning scheme exists and is stable.
  - Evidence type: principle set.
  - Confidence: High.
- Claim 3: persistent identifiers improve reproducibility and credit attribution.
  - Assumptions: PID infrastructure remains available.
  - Evidence type: principle set.
  - Confidence: High.

### R4 - Reproducible Research in Computational Science (`10.1126/science.1213847`)

- Claim 1: computational results should be accompanied by code/data sufficient for independent re-execution.
  - Assumptions: legal/privacy constraints permit sharing.
  - Evidence type: policy/editorial synthesis.
  - Confidence: High.
- Claim 2: reproducibility is a minimum scientific standard rather than optional quality polish.
  - Assumptions: community incentive structures support enforcement.
  - Evidence type: scientific-policy argument.
  - Confidence: Medium.
- Claim 3: pipeline/documentation quality strongly affects trust in computational claims.
  - Assumptions: documentation is kept current with code changes.
  - Evidence type: field-level practice analysis.
  - Confidence: Medium.

### R5 - Ten Simple Rules (`10.1371/journal.pcbi.1003285`)

- Claim 1: preserving raw data behind plots/tables is required for reliable reanalysis.
  - Assumptions: storage/access constraints are manageable.
  - Evidence type: practical rule synthesis.
  - Confidence: High.
- Claim 2: recording intermediate results and workflows reduces irrecoverable analysis drift.
  - Assumptions: intermediate outputs are versioned and discoverable.
  - Evidence type: practical rule synthesis.
  - Confidence: High.
- Claim 3: automation and script-first workflows outperform manual point-and-click reproducibility.
  - Assumptions: teams can operationalize scripted pipelines.
  - Evidence type: practical rule synthesis.
  - Confidence: High.

### R6 - Provenance Survey (`10.1145/1084805.1084812`)

- Claim 1: provenance answers both "where did data come from" and "which process produced it".
  - Assumptions: lineage capture instrumentation is available.
  - Evidence type: survey taxonomy.
  - Confidence: High.
- Claim 2: provenance utility spans debugging, validation, and trust/audit concerns.
  - Assumptions: provenance records are queryable.
  - Evidence type: survey analysis across systems.
  - Confidence: High.
- Claim 3: provenance representation choices create tradeoffs between fidelity and operational cost.
  - Assumptions: high-fidelity capture has measurable overhead.
  - Evidence type: comparative survey discussion.
  - Confidence: Medium.

### R7 - Pegasus (`10.1016/j.future.2014.10.008`)

- Claim 1: robust scientific workflow execution requires handling failures, retries, and heterogeneity natively.
  - Assumptions: distributed compute failures are expected.
  - Evidence type: system architecture + operational outcomes.
  - Confidence: High.
- Claim 2: explicit workflow modeling improves scalability and repeatability.
  - Assumptions: workflow graph captures real dependencies.
  - Evidence type: workflow-system evaluation.
  - Confidence: Medium.
- Claim 3: provenance-enabled workflow execution materially improves post-hoc analysis/debugging.
  - Assumptions: execution metadata is persisted and indexed.
  - Evidence type: system experience report.
  - Confidence: Medium.

### R8 - Galaxy (`10.1186/gb-2010-11-8-r86`)

- Claim 1: reproducibility improves when users can re-run and inspect published analysis workflows.
  - Assumptions: shared environments are accessible.
  - Evidence type: system design and user experience evidence.
  - Confidence: Medium.
- Claim 2: transparency requires linking outputs back to computational history.
  - Assumptions: history capture is complete enough for replay.
  - Evidence type: platform architecture evidence.
  - Confidence: Medium.
- Claim 3: usability is a practical prerequisite for widespread reproducible practice.
  - Assumptions: less technical users are target participants.
  - Evidence type: platform adoption argument.
  - Confidence: Medium.

### R9 - Snakemake (`10.1093/bioinformatics/bts480`)

- Claim 1: declarative rule-based workflow definitions reduce hidden dependency errors.
  - Assumptions: dependency graph is correctly specified.
  - Evidence type: workflow engine design.
  - Confidence: Medium.
- Claim 2: scalable execution can be achieved while preserving reproducible workflow semantics.
  - Assumptions: execution backend behavior is sufficiently controlled.
  - Evidence type: system paper evidence.
  - Confidence: Medium.
- Claim 3: explicit file/target rules improve traceability across pipeline stages.
  - Assumptions: target naming/versioning is disciplined.
  - Evidence type: platform method.
  - Confidence: Medium.

### R10 - Nextflow (`10.1038/nbt.3820`)

- Claim 1: workflow portability increases with containerized and abstracted execution backends.
  - Assumptions: container images are version-pinned and available.
  - Evidence type: system design + case studies.
  - Confidence: Medium.
- Claim 2: reproducibility is strengthened by making pipeline definitions explicit and shareable.
  - Assumptions: teams enforce version control and dependency pinning.
  - Evidence type: platform architecture.
  - Confidence: Medium.
- Claim 3: heterogeneous cloud/HPC execution can preserve reproducibility when runtime contract is controlled.
  - Assumptions: environment parity and dependency pinning are maintained.
  - Evidence type: system-level results.
  - Confidence: Medium.

## 8. Contradictions and competing viewpoints

- Strict determinism vs operational resilience:
  - Some literature frames reproducibility as exact replay; workflow-system papers emphasize fault tolerance and practical retry behavior.
  - AGORA handling: deterministic evidence contracts + explicit persisted retry/failure history.

- Accessibility-first UX vs engine-first rigor:
  - Interactive platforms prioritize transparency/usability; engine papers prioritize declarative reproducibility and scalability.
  - AGORA handling: preserve provenance drill-down UI while keeping orchestrator/rule system authoritative.

## 9. Decisions for AGORA from this packet

- Keep current core invariants (version-pinned evidence, orchestrator-only authority, append-only audit memory) as they are literature-supported.
- Continue emphasizing explicit workflow/event persistence and deterministic resolver behavior.
- Prioritize additional failure-path verification depth and alert-routing integration as the next reproducibility hardening area.

## 10. Coverage summary (claim traceability status)

- Verified by current AGORA tests/commands: 6 claims (citation specificity, orchestrator authority, deterministic resolver behavior, immutable artifact versioning, critical e2e path, command-mapped CI gates).
- Sourced from literature and aligned to architecture (not directly re-proven in this packet): 18 claims.
- TODO/unverified in current repo packet: 6 claims (broader workflow failure-path depth, richer alert-routing automation, portability constraints under broader runtime matrices).
