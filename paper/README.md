# Paper Reproducibility Guide

This directory contains the paper and verification contract for AGORA invariant checks.

## Prerequisites

- Python 3.12+ and project test dependencies (same environment used for repo tests).
- Optional for PDF output: TeX distribution with `pdflatex` (and optionally `bibtex`).

## Commands

All commands below are repo-native and sourced from existing command patterns:

| Purpose | Command | Source |
| --- | --- | --- |
| Run unit verification harness for the paper packet | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/paper` | `Makefile` (`PYTEST_ENV`, `PYTEST`, `test-unit`) |
| Run full unit suite (includes paper tests) | `make test-unit` | `Makefile:test-unit` |
| Generate deterministic result artifact referenced by the paper | `python3 scripts/generate_paper_verification_snapshot.py --output paper/artifacts/verification_snapshot.json` | `scripts/generate_paper_verification_snapshot.py` |
| Build PDF output | `bash scripts/build_paper.sh` | `scripts/build_paper.sh` |

## Expected outputs

- `paper/artifacts/verification_snapshot.json`: deterministic JSON summary for paper Section `Experiments and Results`.
- `paper/build/main.pdf`: compiled paper PDF (if TeX toolchain is available).

## Determinism notes

- Tests are deterministic and do not depend on live infrastructure.
- Snapshot generation uses fixed inline markdown and static transition graph definitions.
- No random seed is required for this packet.

## Approximate runtime

- `tests/unit/paper`: under 5 seconds on a typical local dev machine.
- Snapshot generation: under 1 second.
- PDF build: depends on local TeX installation, typically under 10 seconds.

## Troubleshooting

- If paper tests fail due to missing imports, run from repository root.
- If PDF build fails with `pdflatex is required but not installed`, install a TeX distribution or skip PDF compilation; verification tests and snapshot generation remain runnable without TeX.
