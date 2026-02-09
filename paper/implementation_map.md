# Paper to Code Implementation Map

This file is the compatibility contract between `paper/main.tex` and implementation/test entrypoints.

## Contract Entries

| Paper | Code | Find | Tests |
| --- | --- | --- | --- |
| `eq:coverage_ratio` | `apps/worker/citation_check.py` | `def check_citation_coverage\(` | `tests/unit/paper/test_paper_verification_harness.py::test_property_citation_coverage_matches_indicator_equation` |
| `eq:materialization_count` | `apps/worker/citation_check.py` | `def materialize_citations\(` | `tests/unit/paper/test_paper_verification_harness.py::test_property_materialization_count_matches_cross_product_equation` |
| `eq:phase_transition_validity` | `apps/worker/phase_machine.py` | `def is_valid_transition\(` | `tests/unit/paper/test_paper_verification_harness.py::test_property_phase_validity_matches_adjacency_relation` |
| `eq:terminal_phase` | `apps/worker/phase_machine.py` | `def is_terminal_phase\(` | `tests/unit/paper/test_paper_verification_harness.py::test_limiting_archived_is_terminal_phase` |
| `sec:verification` | `tests/unit/paper/test_paper_verification_harness.py` | `test_golden_allowed_transitions_snapshot` | `tests/unit/paper/test_paper_verification_harness.py::test_golden_allowed_transitions_snapshot` |
| `sec:reproducibility` | `scripts/generate_paper_verification_snapshot.py` | `def build_snapshot\(` | `tests/unit/paper/test_paper_contract.py::test_implementation_map_rows_reference_real_labels_files_and_find_patterns` |

## Known naming discrepancies

- Paper symbol set uses `C_p` and `Z_p`; code names are `claim_markers` and `cite_markers`.
- Paper uses relation notation `Valid(u,v)` and `Terminal(u)`; code exposes these through `PhaseMachine.is_valid_transition` and `PhaseMachine.is_terminal_phase`.
