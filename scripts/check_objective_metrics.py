#!/usr/bin/env python3
"""Objective metrics automation gate.

Runs targeted regression suites for objective-critical signals:
- Citation integrity coverage/resolution.
- Authority-boundary enforcement for phase/finalization paths.

Emits machine-readable summary lines and writes a JSON report that can be used
for local triage and CI artifact capture.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COUNT_PATTERNS: dict[str, tuple[str, ...]] = {
    "passed": (r"(\d+)\s+passed",),
    "failed": (r"(\d+)\s+failed",),
    "errors": (r"(\d+)\s+errors?",),
}


@dataclass(frozen=True)
class MetricSuite:
    metric_id: str
    description: str
    targets: tuple[str, ...]
    threshold: float = 1.0


METRIC_SUITES: tuple[MetricSuite, ...] = (
    MetricSuite(
        metric_id="citation_integrity",
        description="Citation coverage/resolution regression suite.",
        targets=(
            "tests/integration/worker/test_citation_checks.py",
            "tests/integration/core_api/test_evidence_resolver.py",
        ),
    ),
    MetricSuite(
        metric_id="authority_boundary",
        description="Orchestrator-only authority regression suite.",
        targets=(
            "tests/integration/worker/test_phase_machine.py",
            "tests/integration/core_api/test_drafts.py",
        ),
    ),
)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _extract_count(text: str, patterns: tuple[str, ...]) -> int:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return 0


def _extract_counts(output: str) -> dict[str, int]:
    return {name: _extract_count(output, patterns) for name, patterns in COUNT_PATTERNS.items()}


def _extract_summary_line(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for line in reversed(lines):
        if re.search(r"\b(\d+\s+passed|\d+\s+failed|\d+\s+errors?)\b", line):
            return line
    return ""


def _run_suite(metric: MetricSuite, python_bin: str) -> dict[str, Any]:
    cmd = [
        python_bin,
        "-m",
        "pytest",
        "-p",
        "pytest_asyncio.plugin",
        "-q",
        *metric.targets,
    ]
    env = os.environ.copy()
    env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")

    started = time.monotonic()
    proc = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    duration_seconds = round(time.monotonic() - started, 3)
    combined = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
    counts = _extract_counts(combined)
    summary_line = _extract_summary_line(combined)
    executed = counts["passed"] + counts["failed"] + counts["errors"]
    pass_rate = float(counts["passed"] / executed) if executed else 0.0
    status = "pass" if proc.returncode == 0 and pass_rate >= metric.threshold else "fail"

    failure_excerpt: list[str] = []
    if status == "fail":
        merged_lines = [line for line in combined.splitlines() if line.strip()]
        failure_excerpt = merged_lines[-25:]

    command_template = "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ${PYTHON_BIN:-python3} -m pytest -p pytest_asyncio.plugin -q " + " ".join(
        metric.targets
    )

    return {
        "id": metric.metric_id,
        "description": metric.description,
        "status": status,
        "threshold": metric.threshold,
        "return_code": proc.returncode,
        "command": command_template,
        "targets": list(metric.targets),
        "counts": counts,
        "executed_tests": executed,
        "pass_rate": round(pass_rate, 4),
        "duration_seconds": duration_seconds,
        "summary_line": summary_line,
        "failure_excerpt": failure_excerpt,
    }


def _metric_trend(current_status: str, previous_status: str | None) -> str:
    if previous_status is None:
        return "initial"
    if previous_status == current_status:
        return "steady"
    if previous_status == "fail" and current_status == "pass":
        return "improved"
    return "regressed"


def _write_dashboard(report: dict[str, Any], dashboard_path: Path) -> None:
    metrics: list[dict[str, Any]] = report.get("metrics", [])
    overall: dict[str, Any] = report.get("overall", {})
    generated_at = str(report.get("generated_at", "unknown"))
    objective = str(report.get("objective", "unknown"))
    overall_status = str(overall.get("status", "unknown"))
    passed_metrics = int(overall.get("passed_metrics", 0))
    required_metrics = int(overall.get("required_metrics", 0))

    lines = [
        "# Objective Metrics Dashboard",
        "",
        f"Generated at: `{generated_at}`",
        f"Objective anchor: `{objective}`",
        "",
        f"Overall status: `{overall_status}` ({passed_metrics}/{required_metrics} metrics passing)",
        "",
        "## Metric Summary",
        "",
        "| Metric | Status | Trend | Pass rate | Executed tests | Summary |",
        "|---|---|---|---|---:|---|",
    ]

    for metric in metrics:
        metric_id = str(metric.get("id", "unknown"))
        status = str(metric.get("status", "unknown"))
        trend = str(metric.get("trend", "unknown"))
        pass_rate = float(metric.get("pass_rate", 0.0))
        executed_tests = int(metric.get("executed_tests", 0))
        summary_line = str(metric.get("summary_line", "")).replace("|", "\\|")
        lines.append(
            f"| `{metric_id}` | `{status}` | `{trend}` | `{pass_rate:.4f}` | {executed_tests} | {summary_line} |"
        )

    lines.extend(
        [
            "",
            "## Commands",
            "",
            "Regenerate metrics + dashboard locally:",
            "",
            "```bash",
            "make check-objective-metrics",
            "```",
            "",
            "Raw JSON report:",
            "- `Docs/implementation/reports/objective_metrics_latest.json`",
            "",
            "Trend history outputs:",
            "- `Docs/implementation/reports/objective_metrics_history.jsonl`",
            "- `Docs/implementation/reports/objective_metrics_timeline.md`",
        ]
    )

    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _history_entry(report: dict[str, Any]) -> dict[str, Any]:
    metric_statuses: dict[str, str] = {}
    metric_pass_rates: dict[str, float] = {}
    metric_executed_tests: dict[str, int] = {}
    for metric in report.get("metrics", []):
        metric_id = metric.get("id")
        if not isinstance(metric_id, str):
            continue
        metric_statuses[metric_id] = str(metric.get("status", "unknown"))
        metric_pass_rates[metric_id] = float(metric.get("pass_rate", 0.0))
        metric_executed_tests[metric_id] = int(metric.get("executed_tests", 0))
    overall = report.get("overall", {})
    return {
        "generated_at": report.get("generated_at"),
        "objective": report.get("objective"),
        "overall": {
            "status": overall.get("status"),
            "required_metrics": overall.get("required_metrics"),
            "passed_metrics": overall.get("passed_metrics"),
            "pass_rate": overall.get("pass_rate"),
        },
        "metric_statuses": metric_statuses,
        "metric_pass_rates": metric_pass_rates,
        "metric_executed_tests": metric_executed_tests,
    }


def _append_history(history_path: Path, report: dict[str, Any]) -> list[dict[str, Any]]:
    history_entry = _history_entry(report)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(history_entry, sort_keys=True) + "\n")
    return _read_jsonl(history_path)


def _format_metric_status(value: str | None) -> str:
    if value is None or value == "":
        return "-"
    return f"`{value}`"


def _write_timeline(
    report: dict[str, Any],
    history_entries: list[dict[str, Any]],
    timeline_path: Path,
    history_path: Path,
    run_limit: int,
) -> None:
    generated_at = str(report.get("generated_at", "unknown"))
    overall = report.get("overall", {})
    overall_status = str(overall.get("status", "unknown"))
    metric_ids = [metric.metric_id for metric in METRIC_SUITES]
    metric_headers = [metric_id.replace("_", " ") for metric_id in metric_ids]
    header_cells = ["Generated at", "Overall", *metric_headers, "Passed metrics"]

    lines = [
        "# Objective Metrics Timeline",
        "",
        f"Generated at: `{generated_at}`",
        f"Latest overall status: `{overall_status}`",
        f"Recorded runs: `{len(history_entries)}`",
        "",
        "## Recent Runs",
        "",
        "| " + " | ".join(header_cells) + " |",
        "| " + " | ".join(["---", "---", *(["---"] * len(metric_headers)), "---:"]) + " |",
    ]

    recent_entries = history_entries[-run_limit:] if run_limit > 0 else history_entries
    for entry in reversed(recent_entries):
        entry_overall = entry.get("overall", {})
        metric_statuses = entry.get("metric_statuses", {})
        if not isinstance(metric_statuses, dict):
            metric_statuses = {}
        metric_cells = [_format_metric_status(metric_statuses.get(metric_id)) for metric_id in metric_ids]
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{entry.get('generated_at', 'unknown')}`",
                    f"`{entry_overall.get('status', 'unknown')}`",
                    *metric_cells,
                    str(entry_overall.get("passed_metrics", 0)),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Query Examples",
            "",
            "Inspect the append-only history store with `jq`:",
            "",
            "```bash",
            f"jq -c '.' {history_path}",
            "```",
            "",
            "List timestamps where overall status failed:",
            "",
            "```bash",
            f"jq -r 'select(.overall.status == \"fail\") | .generated_at' {history_path}",
            "```",
            "",
            "List citation integrity status by run:",
            "",
            "```bash",
            f"jq -r '.generated_at + \" \" + .metric_statuses.citation_integrity' {history_path}",
            "```",
        ]
    )

    timeline_path.parent.mkdir(parents=True, exist_ok=True)
    timeline_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run objective metric regression suites and write summary report."
    )
    parser.add_argument(
        "--report",
        default="Docs/implementation/reports/objective_metrics_latest.json",
        help="Path to objective metrics JSON report output.",
    )
    parser.add_argument(
        "--python-bin",
        default=sys.executable,
        help="Python executable to use when invoking pytest.",
    )
    parser.add_argument(
        "--dashboard",
        default="Docs/implementation/reports/objective_metrics_dashboard.md",
        help="Path to rendered objective metrics dashboard markdown output.",
    )
    parser.add_argument(
        "--history",
        default="Docs/implementation/reports/objective_metrics_history.jsonl",
        help="Path to append-only objective metrics history output.",
    )
    parser.add_argument(
        "--timeline",
        default="Docs/implementation/reports/objective_metrics_timeline.md",
        help="Path to rendered objective metrics timeline markdown output.",
    )
    parser.add_argument(
        "--timeline-limit",
        type=int,
        default=40,
        help="Max number of most recent history runs to render in timeline view.",
    )
    args = parser.parse_args()

    report_path = Path(args.report)
    dashboard_path = Path(args.dashboard)
    history_path = Path(args.history)
    timeline_path = Path(args.timeline)
    previous = _read_json(report_path)
    previous_metrics = {}
    if isinstance(previous, dict):
        for metric in previous.get("metrics", []):
            metric_id = metric.get("id")
            if isinstance(metric_id, str):
                previous_metrics[metric_id] = metric.get("status")

    metric_results = [_run_suite(metric, args.python_bin) for metric in METRIC_SUITES]
    passed_metrics = sum(1 for metric in metric_results if metric["status"] == "pass")
    required_metrics = len(metric_results)
    overall_status = "pass" if passed_metrics == required_metrics else "fail"

    for metric in metric_results:
        metric["trend"] = _metric_trend(metric["status"], previous_metrics.get(metric["id"]))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "objective": "Docs/manifest/00_overview.md#Core Objective",
        "metrics": metric_results,
        "overall": {
            "status": overall_status,
            "required_metrics": required_metrics,
            "passed_metrics": passed_metrics,
            "pass_rate": round((passed_metrics / required_metrics) if required_metrics else 0.0, 4),
        },
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_dashboard(report, dashboard_path)
    history_entries = _append_history(history_path, report)
    _write_timeline(
        report,
        history_entries=history_entries,
        timeline_path=timeline_path,
        history_path=history_path,
        run_limit=max(args.timeline_limit, 0),
    )

    print(
        "objective_metrics_summary "
        f"status={overall_status} "
        f"required_metrics={required_metrics} "
        f"passed_metrics={passed_metrics} "
        f"report={report_path} "
        f"dashboard={dashboard_path} "
        f"history={history_path} "
        f"timeline={timeline_path}"
    )
    for metric in metric_results:
        print(
            "objective_metric "
            f"id={metric['id']} "
            f"status={metric['status']} "
            f"trend={metric['trend']} "
            f"pass_rate={metric['pass_rate']:.4f} "
            f"executed_tests={metric['executed_tests']} "
            f"duration_seconds={metric['duration_seconds']}"
        )

    return 0 if overall_status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
