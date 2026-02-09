#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAPER_DIR="${REPO_ROOT}/paper"
BUILD_DIR="${PAPER_DIR}/build"

if ! command -v pdflatex >/dev/null 2>&1; then
  echo "pdflatex is required but not installed." >&2
  echo "Install a TeX distribution, then rerun scripts/build_paper.sh." >&2
  exit 2
fi

mkdir -p "${BUILD_DIR}"

pdflatex -interaction=nonstopmode -halt-on-error -output-directory "${BUILD_DIR}" "${PAPER_DIR}/main.tex" >/dev/null

if command -v bibtex >/dev/null 2>&1; then
  if [ -f "${BUILD_DIR}/main.aux" ]; then
    bibtex "${BUILD_DIR}/main" >/dev/null || true
    pdflatex -interaction=nonstopmode -halt-on-error -output-directory "${BUILD_DIR}" "${PAPER_DIR}/main.tex" >/dev/null
    pdflatex -interaction=nonstopmode -halt-on-error -output-directory "${BUILD_DIR}" "${PAPER_DIR}/main.tex" >/dev/null
  fi
fi

echo "paper_build_complete pdf=${BUILD_DIR}/main.pdf"
