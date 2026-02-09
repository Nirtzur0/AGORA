#!/usr/bin/env python3
"""Generate deterministic paper verification snapshot artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_import_paths(repo_root: Path) -> None:
    path_order = [
        repo_root / "packages" / "db",
        repo_root / "packages" / "shared-types",
        repo_root / "apps" / "core-api",
        repo_root / "apps" / "worker",
    ]
    for path in reversed(path_order):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def build_snapshot() -> dict:
    repo_root = _repo_root()
    _ensure_import_paths(repo_root)

    import citation_check
    import phase_machine

    sample_markdown = (
        "Paragraph one [[claim:11111111-1111-1111-1111-111111111111]] "
        "[[cite:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa|pdf:p=1#char=0-20]] "
        "[[cite:bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb|pdf:p=1#char=21-40]]\n\n"
        "Paragraph two [[claim:22222222-2222-2222-2222-222222222222]] "
        "[[claim:33333333-3333-3333-3333-333333333333]] "
        "[[cite:cccccccc-cccc-cccc-cccc-cccccccccccc|repo:path=README.md#L1-L5]]\n\n"
        "Paragraph three contains context only."
    )

    claim_markers, cite_markers, _ = citation_check.parse_draft_markdown(sample_markdown)
    coverage_pass, coverage_failures = citation_check.check_citation_coverage(claim_markers, cite_markers)

    claims_by_para = {}
    cites_by_para = {}
    for claim in claim_markers:
        claims_by_para.setdefault(claim.paragraph_index, 0)
        claims_by_para[claim.paragraph_index] += 1
    for cite in cite_markers:
        cites_by_para.setdefault(cite.paragraph_index, 0)
        cites_by_para[cite.paragraph_index] += 1

    materialization_count = 0
    for paragraph_index in sorted(set(list(claims_by_para.keys()) + list(cites_by_para.keys()))):
        materialization_count += claims_by_para.get(paragraph_index, 0) * cites_by_para.get(paragraph_index, 0)

    transition_graph = {
        phase.value: sorted([target.value for target in targets])
        for phase, targets in phase_machine.ALLOWED_TRANSITIONS.items()
    }

    terminal_phases = sorted(
        [phase for phase, targets in transition_graph.items() if len(targets) == 0]
    )

    snapshot = {
        "citation_sample": {
            "claims_total": len(claim_markers),
            "cites_total": len(cite_markers),
            "coverage_pass": coverage_pass,
            "coverage_failures": coverage_failures,
            "materialization_count": materialization_count,
        },
        "phase_graph": {
            "states_total": len(transition_graph),
            "edges_total": sum(len(targets) for targets in transition_graph.values()),
            "terminal_phases": terminal_phases,
            "loopback_examples": [
                ["INTERNAL_REVIEW", "EXPERIMENTATION"],
                ["CLAIM_VALIDATION", "LIT_REVIEW"],
            ],
        },
    }

    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate paper verification snapshot artifact")
    parser.add_argument(
        "--output",
        default="paper/artifacts/verification_snapshot.json",
        help="Output JSON artifact path",
    )
    args = parser.parse_args()

    repo_root = _repo_root()
    output_path = (repo_root / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = build_snapshot()
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"paper_verification_snapshot_written output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
