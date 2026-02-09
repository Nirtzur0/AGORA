# Paper Verification Log

Date: 2026-02-09  
Prompt packet: `prompt-13-research-paper-verification`

## 1. Scope, regimes, and constraints

- Scope: formalize and verify AGORA invariants for citation coverage/materialization and phase-transition control.
- Regime: deterministic, unit-level invariant verification for repository code paths (`apps/worker/*`).
- Constraints:
  - Use repo-native commands and test framework.
  - No claim is marked "verified" without a concrete deterministic test.
  - Reuse canonical literature from `Docs/manifest/20_literature_review.md`.

Bet tracking:
- Appetite: `medium`
- Now: one invariant cluster (`citation + phase-machine`)
- Not now: full-system performance validation and alert-routing policy automation
- State: `downhill`

## 2. Research questions

1. Can citation coverage and materialization semantics be specified as equations and verified against code?
2. Can phase-transition authority logic be represented as relation equations and verified against the phase graph implementation?
3. Which assumptions should remain literature-backed rather than test-verified in this packet?
4. How can paper-to-code drift be automatically detected?

## 3. Search log and inclusion/exclusion criteria

- Sources reused from prompt-12 packet and AGORA docs:
  - `Docs/manifest/20_literature_review.md`
  - `Docs/implementation/reports/20_literature_review_log.md`
  - `Docs/manifest/00_overview.md`
  - `Docs/04-system-implementation-spec.md`
- Inclusion criteria:
  - DOI-backed source with direct relevance to reproducibility/provenance/workflows.
  - Enables a concrete modeling assumption or decision in this paper.
- Exclusion criteria:
  - Generic tool blogs without stable IDs.
  - Claims not directly tied to AGORA invariants in this packet.

## 4. Canonical references (project-critical subset)

- `wilkinson2016fair` (`10.1038/sdata.2016.18`): FAIR metadata and persistent identifier principles.
- `datacite2014principles` (`10.25490/a97f-egyk`): citation specificity and verifiability.
- `smith2016software` (`10.7717/peerj-cs.86`): software/version citation principles.
- `simmhan2005provenance` (`10.1145/1084805.1084812`): provenance taxonomy (data + process lineage).
- `deelman2015pegasus` (`10.1016/j.future.2014.10.008`): workflow fault handling/reliability patterns.

## 5. Artifact traceability map

| Artifact ID | Source/Citation key | Used for | Notes |
| --- | --- | --- | --- |
| `EXT-LIT-FAIR-001` | `wilkinson2016fair` | Persistent identifier and metadata assumptions | Metadata-only DOI artifact |
| `EXT-LIT-DATACITE-001` | `datacite2014principles` | Version-pinned citation specificity rationale | Metadata-only DOI artifact |
| `EXT-LIT-SOFTWARECITE-001` | `smith2016software` | Versioned software/output citation assumptions | Metadata-only DOI artifact |
| `EXT-LIT-SIMMHAN-2005-001` | `simmhan2005provenance` | Process+data lineage requirement | Metadata-only DOI artifact |
| `EXT-LIT-PEGASUS-2015-001` | `deelman2015pegasus` | Workflow failure-handling assumption | Metadata-only DOI artifact |

## 6. Key claims table

| Claim | Source | Assumptions | Evidence | Confidence | Traceability | Tests |
| --- | --- | --- | --- | --- | --- | --- |
| Coverage pass iff every claim marker has at least one cite in same paragraph (`Cov=1`). | AGORA code + spec | Paragraph splitting is deterministic and marker syntax is valid. | Unit verification against `check_citation_coverage`. | High | Verified | `test_property_citation_coverage_matches_indicator_equation` |
| Citation materialization count equals paragraph-wise claim-cite cross product (`M = sum |C_p||Z_p|`) under idempotent dedupe. | AGORA code + spec | Existing citation rows are deduped by key. | Unit verification with fake DB plus explicit duplicate guard. | High | Verified | `test_property_materialization_count_matches_cross_product_equation`, `test_limiting_materialization_second_run_is_idempotent` |
| Phase transition validity equals graph adjacency membership (`Valid(u,v)=1 iff v in T(u)`). | AGORA code + spec | Transition graph is authoritative in `ALLOWED_TRANSITIONS`. | Exhaustive pairwise unit check. | High | Verified | `test_property_phase_validity_matches_adjacency_relation` |
| Terminal phase iff out-degree is zero (`Terminal(u)=1 iff |T(u)|=0`). | AGORA code + spec | `ARCHIVED` remains terminal by design. | Unit checks and golden snapshot. | High | Verified | `test_limiting_archived_is_terminal_phase`, `test_golden_allowed_transitions_snapshot` |
| Persistent, specific, versioned citations are required for reproducible evidence reuse. | `wilkinson2016fair`, `datacite2014principles`, `smith2016software` | DOI/PID ecosystems remain available and maintained. | Literature synthesis from prompt-12 packet. | High | Literature | N/A |
| Workflow reliability requires explicit failure handling and auditable process lineage. | `simmhan2005provenance`, `deelman2015pegasus` | Distributed failures remain expected operational reality. | Literature synthesis + AGORA architecture alignment. | Medium | Literature | N/A |
| Full alert-routing policy correctness is validated end-to-end in this packet. | N/A | Requires broader infra/integration setup. | Not covered by current unit harness. | Low | TODO | TODO |

## 7. Competing viewpoints / contradictions

- Strict determinism vs practical reliability:
  - Deterministic invariants are required for evidence resolution correctness.
  - Workflow operations still require bounded retries and explicit failure persistence.
- Equation-level verification vs full-system behavior:
  - This packet verifies invariant kernels, not total operational behavior under production-like load.

## 8. Decisions for this project

- Keep citation coverage/materialization semantics and phase transition graph behavior as explicit invariant contracts.
- Keep a machine-checkable paper-to-code map (`paper/implementation_map.md`) and enforce it via unit tests.
- Preserve literature-backed assumptions as explicit "literature" claims until corresponding empirical tests exist.

## 9. Verification coverage summary

- Verified by tests in this packet: 5 claims.
- Sourced from literature (not directly tested here): 2 claims.
- TODO/unverified in this packet: 1 claim.
