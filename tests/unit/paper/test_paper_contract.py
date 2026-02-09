"""Contract checks for paper/main.tex <-> paper/implementation_map.md."""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PAPER_MAIN = REPO_ROOT / "paper" / "main.tex"
IMPLEMENTATION_MAP = REPO_ROOT / "paper" / "implementation_map.md"


def _strip_ticks(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`"):
        return value[1:-1]
    return value


def _parse_map_rows() -> list[dict[str, str]]:
    rows = []
    for raw_line in IMPLEMENTATION_MAP.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue

        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 4:
            continue
        if cells[0] == "Paper":
            continue
        if cells[0].startswith("---"):
            continue

        rows.append(
            {
                "paper": _strip_ticks(cells[0]),
                "code": _strip_ticks(cells[1]),
                "find": _strip_ticks(cells[2]),
                "tests": _strip_ticks(cells[3]),
            }
        )
    return rows


def test_implementation_map_rows_reference_real_labels_files_and_find_patterns():
    assert PAPER_MAIN.exists(), f"Missing paper file: {PAPER_MAIN}"
    assert IMPLEMENTATION_MAP.exists(), f"Missing map file: {IMPLEMENTATION_MAP}"

    main_tex = PAPER_MAIN.read_text(encoding="utf-8")
    rows = _parse_map_rows()
    assert rows, "No contract rows found in paper/implementation_map.md"

    for row in rows:
        paper_ref = row["paper"]
        code_path = REPO_ROOT / row["code"]
        find_pattern = row["find"]
        tests_ref = row["tests"]

        if paper_ref.startswith("eq:") or paper_ref.startswith("sec:"):
            assert (
                f"\\label{{{paper_ref}}}" in main_tex
            ), f"Missing label in paper/main.tex: {paper_ref}"

        assert code_path.exists(), f"Mapped code path missing: {code_path}"

        if find_pattern != "N/A":
            result = subprocess.run(
                ["rg", "-n", find_pattern, str(code_path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, (
                f"Find pattern did not match: pattern={find_pattern} file={code_path}\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )

        test_file = tests_ref.split("::", 1)[0]
        test_path = REPO_ROOT / test_file
        assert test_path.exists(), f"Mapped test path missing: {test_path}"
