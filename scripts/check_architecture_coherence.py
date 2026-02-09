#!/usr/bin/env python3
"""Validate architecture coherence docs and CI wiring.

This check intentionally focuses on deterministic, repo-local signals:
- required architecture docs and section anchors exist
- readiness verdict markers are present
- architecture coherence automation is wired in CI + runbook
- core architecture boundary evidence paths still exist
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


REQUIRED_FILES = (
    "Docs/manifest/01_architecture.md",
    "Docs/manifest/04_api_contracts.md",
    "Docs/manifest/05_data_model.md",
    "Docs/manifest/09_runbook.md",
    "Docs/manifest/11_ci.md",
    "Docs/implementation/checklists/00_architecture_coherence.md",
    "Docs/implementation/reports/architecture_coherence_report.md",
    ".github/workflows/ci.yml",
    "Makefile",
)

ARCH_REQUIRED_SECTIONS = (
    "## Scope, Constraints, and Quality Scenarios",
    "## C4-1 System Context",
    "## C4-2 Containers",
    "## C4-3 Components",
    "## Runtime Scenarios",
    "## Deployment and Trust Boundaries",
    "## Cross-Cutting Concepts",
    "## Risks and Technical Debt",
)

API_CONTRACT_REQUIRED_SNIPPETS = (
    "## Auth and Identity Contracts",
    "## Artifact and Evidence Contracts",
    "## Request Action Contracts",
    "## Contract Enforcement Plan",
)

DATA_MODEL_REQUIRED_SNIPPETS = (
    "## Storage Layers",
    "## Core Tables (Grouped)",
    "## Data Invariants",
)

RUNBOOK_REQUIRED_SNIPPETS = (
    "CMD-28",
    "check-architecture-coherence",
)

CI_DOC_REQUIRED_SNIPPETS = (
    "architecture-coherence",
    "CMD-28",
)

CI_YAML_REQUIRED_SNIPPETS = (
    "architecture-coherence",
    "check-architecture-coherence",
)

CHECKLIST_AUTOMATION_SNIPPET = "- [x] Architecture coherence validation is automated in CI"

REPO_EVIDENCE_PATHS = (
    "apps/core-api",
    "apps/worker",
    "apps/moltbook-adapter",
    "apps/web",
    "infra/docker-compose.yml",
    "packages/db/migrations/001_initial_schema.py",
)

VERDICT_RE = re.compile(r"\b(GO|GO_WITH_RISKS|NO_GO)\b")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _require_contains(errors: list[str], label: str, text: str, snippets: tuple[str, ...]) -> None:
    for snippet in snippets:
        if snippet not in text:
            errors.append(f"{label}: missing snippet '{snippet}'")


def _check_required_files(errors: list[str], repo_root: Path) -> None:
    for rel in REQUIRED_FILES:
        if not (repo_root / rel).exists():
            errors.append(f"missing required file: {rel}")


def _check_verdict(errors: list[str], label: str, text: str) -> None:
    if not VERDICT_RE.search(text):
        errors.append(f"{label}: missing readiness verdict token (GO/GO_WITH_RISKS/NO_GO)")


def _check_repo_evidence_paths(errors: list[str], repo_root: Path) -> None:
    for rel in REPO_EVIDENCE_PATHS:
        if not (repo_root / rel).exists():
            errors.append(f"missing repo evidence path: {rel}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate architecture coherence docs + CI wiring.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    errors: list[str] = []

    _check_required_files(errors, repo_root)
    if errors:
        for err in errors:
            print(f"ARCH_COHERENCE_FAIL {err}")
        return 2

    architecture_md = _read_text(repo_root / "Docs/manifest/01_architecture.md")
    api_contracts_md = _read_text(repo_root / "Docs/manifest/04_api_contracts.md")
    data_model_md = _read_text(repo_root / "Docs/manifest/05_data_model.md")
    runbook_md = _read_text(repo_root / "Docs/manifest/09_runbook.md")
    ci_doc_md = _read_text(repo_root / "Docs/manifest/11_ci.md")
    checklist_md = _read_text(repo_root / "Docs/implementation/checklists/00_architecture_coherence.md")
    report_md = _read_text(repo_root / "Docs/implementation/reports/architecture_coherence_report.md")
    ci_yaml = _read_text(repo_root / ".github/workflows/ci.yml")
    makefile = _read_text(repo_root / "Makefile")

    _require_contains(errors, "Docs/manifest/01_architecture.md", architecture_md, ARCH_REQUIRED_SECTIONS)
    _require_contains(errors, "Docs/manifest/04_api_contracts.md", api_contracts_md, API_CONTRACT_REQUIRED_SNIPPETS)
    _require_contains(errors, "Docs/manifest/05_data_model.md", data_model_md, DATA_MODEL_REQUIRED_SNIPPETS)
    _require_contains(errors, "Docs/manifest/09_runbook.md", runbook_md, RUNBOOK_REQUIRED_SNIPPETS)
    _require_contains(errors, "Docs/manifest/11_ci.md", ci_doc_md, CI_DOC_REQUIRED_SNIPPETS)
    _require_contains(errors, ".github/workflows/ci.yml", ci_yaml, CI_YAML_REQUIRED_SNIPPETS)
    _require_contains(errors, "Makefile", makefile, ("check-architecture-coherence",))

    if CHECKLIST_AUTOMATION_SNIPPET not in checklist_md:
        errors.append(
            "Docs/implementation/checklists/00_architecture_coherence.md: "
            "automation checkbox is not marked complete"
        )

    _check_verdict(errors, "Docs/implementation/checklists/00_architecture_coherence.md", checklist_md)
    _check_verdict(errors, "Docs/implementation/reports/architecture_coherence_report.md", report_md)
    _check_repo_evidence_paths(errors, repo_root)

    if errors:
        print(f"architecture_coherence_summary status=fail errors={len(errors)}")
        for err in errors:
            print(f"ARCH_COHERENCE_FAIL {err}")
        return 2

    print(
        "architecture_coherence_summary status=ok "
        f"checked_files={len(REQUIRED_FILES)} "
        f"sections={len(ARCH_REQUIRED_SECTIONS)} "
        f"evidence_paths={len(REPO_EVIDENCE_PATHS)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
