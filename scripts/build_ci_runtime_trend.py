#!/usr/bin/env python3
"""Build runtime/flake trend artifacts from CI runtime policy summaries.

This script consumes one or more `runtime_policy_summary` text files emitted by
heavy CI gates (nightly/release), then writes:
- latest JSON report
- append-only-ish JSONL history (deduped by run_id/run_attempt/gate)
- markdown dashboard with recent trend rollups
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PAIR_RE = re.compile(r"(\w+)=([^\s]+)")


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


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value))
    except Exception:
        return default


def _parse_runtime_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"summary file not found: {path}")

    selected_line = ""
    for raw_line in reversed(path.read_text(encoding="utf-8").splitlines()):
        line = raw_line.strip()
        if "runtime_policy_summary" in line:
            selected_line = line
            break

    if not selected_line:
        raise ValueError(f"missing runtime_policy_summary line in {path}")

    fields = {k: v for k, v in PAIR_RE.findall(selected_line)}
    gate = str(fields.get("gate", "")).strip()
    status = str(fields.get("status", "")).strip() or "unknown"
    if not gate:
        raise ValueError(f"missing gate= in runtime summary line: {selected_line}")

    attempts_used = max(_to_int(fields.get("attempts_used"), 0), 0)
    retry_budget = max(_to_int(fields.get("retry_budget"), 0), 0)
    timeout_minutes = max(_to_int(fields.get("timeout_minutes"), 0), 0)
    runtime_target_minutes = max(_to_int(fields.get("runtime_target_minutes"), 0), 0)
    elapsed_seconds = max(_to_int(fields.get("elapsed_seconds"), 0), 0)
    retries_used = max(attempts_used - 1, 0)

    runtime_target_seconds = runtime_target_minutes * 60
    runtime_delta_seconds = elapsed_seconds - runtime_target_seconds
    runtime_target_met = True if runtime_target_minutes <= 0 else elapsed_seconds <= runtime_target_seconds
    retry_budget_met = attempts_used <= (retry_budget + 1)

    return {
        "gate": gate,
        "status": status,
        "attempts_used": attempts_used,
        "retry_budget": retry_budget,
        "retries_used": retries_used,
        "timeout_minutes": timeout_minutes,
        "runtime_target_minutes": runtime_target_minutes,
        "runtime_target_seconds": runtime_target_seconds,
        "elapsed_seconds": elapsed_seconds,
        "elapsed_minutes": round(elapsed_seconds / 60.0, 2),
        "runtime_delta_seconds": runtime_delta_seconds,
        "runtime_delta_minutes": round(runtime_delta_seconds / 60.0, 2),
        "runtime_target_met": runtime_target_met,
        "retry_budget_met": retry_budget_met,
    }


def _history_key(entry: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(entry.get("run_id", "")),
        str(entry.get("run_attempt", "")),
        str(entry.get("gate", "")),
    )


def _append_history(history_path: Path, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing_rows = _read_jsonl(history_path)
    existing_keys = {_history_key(row) for row in existing_rows}

    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        for entry in entries:
            key = _history_key(entry)
            if key in existing_keys:
                continue
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
            existing_keys.add(key)

    return _read_jsonl(history_path)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _trend_by_gate(history_rows: list[dict[str, Any]], window: int) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in history_rows:
        gate = str(row.get("gate", "unknown"))
        buckets.setdefault(gate, []).append(row)

    trend_rows: list[dict[str, Any]] = []
    for gate in sorted(buckets):
        gate_rows = buckets[gate][-window:] if window > 0 else buckets[gate]
        durations = [float(row.get("elapsed_seconds", 0.0)) for row in gate_rows]
        retries = [int(row.get("retries_used", 0)) for row in gate_rows]
        statuses = [str(row.get("status", "unknown")) for row in gate_rows]
        runtime_misses = [not bool(row.get("runtime_target_met", False)) for row in gate_rows]

        latest_duration = durations[-1] if durations else 0.0
        previous_duration = durations[-2] if len(durations) > 1 else latest_duration

        trend_rows.append(
            {
                "gate": gate,
                "runs_considered": len(gate_rows),
                "pass_rate": round(sum(1 for s in statuses if s == "pass") / len(statuses), 4) if statuses else 0.0,
                "avg_elapsed_minutes": round(_mean(durations) / 60.0, 2),
                "latest_elapsed_minutes": round(latest_duration / 60.0, 2),
                "delta_vs_previous_minutes": round((latest_duration - previous_duration) / 60.0, 2),
                "retry_event_rate": round(sum(1 for v in retries if v > 0) / len(retries), 4) if retries else 0.0,
                "runtime_target_miss_count": sum(1 for miss in runtime_misses if miss),
            }
        )

    return trend_rows


def _write_dashboard(
    *,
    dashboard_path: Path,
    report: dict[str, Any],
    history_rows: list[dict[str, Any]],
    history_path: Path,
    trend_rows: list[dict[str, Any]],
    timeline_limit: int,
) -> None:
    context = report.get("context", {})
    summaries = report.get("summaries", [])
    overall = report.get("overall", {})

    lines = [
        "# CI Runtime and Flake Trend Dashboard",
        "",
        f"Generated at: `{report.get('generated_at', 'unknown')}`",
        f"Objective anchor: `{report.get('objective', 'unknown')}`",
        (
            "Run context: "
            f"workflow=`{context.get('workflow', 'unknown')}`, "
            f"run_id=`{context.get('run_id', 'unknown')}`, "
            f"attempt=`{context.get('run_attempt', 'unknown')}`, "
            f"event=`{context.get('event_name', 'unknown')}`"
        ),
        "",
        (
            "Overall summary: "
            f"`{overall.get('status', 'unknown')}` "
            f"(signals={overall.get('signals_total', 0)}, "
            f"gate_failures={overall.get('gate_failures', 0)}, "
            f"runtime_target_misses={overall.get('runtime_target_misses', 0)}, "
            f"retry_budget_misses={overall.get('retry_budget_misses', 0)})"
        ),
        "",
        "## Current Run Signals",
        "",
        "| Gate | Status | Elapsed (min) | Target (min) | Delta (min) | Attempts | Retry budget | Retries used | Runtime target met | Retry budget met |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]

    for signal in summaries:
        lines.append(
            "| "
            f"`{signal.get('gate', 'unknown')}` | "
            f"`{signal.get('status', 'unknown')}` | "
            f"{float(signal.get('elapsed_minutes', 0.0)):.2f} | "
            f"{int(signal.get('runtime_target_minutes', 0))} | "
            f"{float(signal.get('runtime_delta_minutes', 0.0)):.2f} | "
            f"{int(signal.get('attempts_used', 0))} | "
            f"{int(signal.get('retry_budget', 0))} | "
            f"{int(signal.get('retries_used', 0))} | "
            f"`{str(signal.get('runtime_target_met', False)).lower()}` | "
            f"`{str(signal.get('retry_budget_met', False)).lower()}` |"
        )

    lines.extend(
        [
            "",
            "## Recent Trend Snapshot",
            "",
            "| Gate | Runs | Pass rate | Avg elapsed (min) | Latest elapsed (min) | Delta vs previous (min) | Retry-event rate | Runtime target misses |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for trend in trend_rows:
        lines.append(
            "| "
            f"`{trend.get('gate', 'unknown')}` | "
            f"{int(trend.get('runs_considered', 0))} | "
            f"{float(trend.get('pass_rate', 0.0)):.4f} | "
            f"{float(trend.get('avg_elapsed_minutes', 0.0)):.2f} | "
            f"{float(trend.get('latest_elapsed_minutes', 0.0)):.2f} | "
            f"{float(trend.get('delta_vs_previous_minutes', 0.0)):.2f} | "
            f"{float(trend.get('retry_event_rate', 0.0)):.4f} | "
            f"{int(trend.get('runtime_target_miss_count', 0))} |"
        )

    lines.extend(
        [
            "",
            "## Recent History Rows",
            "",
            f"History path: `{history_path}`",
            "",
            "| Recorded at | Gate | Status | Elapsed (min) | Attempts | Retry budget | Retries used |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )

    recent_rows = history_rows[-timeline_limit:] if timeline_limit > 0 else history_rows
    for row in recent_rows:
        lines.append(
            "| "
            f"`{row.get('generated_at', 'unknown')}` | "
            f"`{row.get('gate', 'unknown')}` | "
            f"`{row.get('status', 'unknown')}` | "
            f"{float(row.get('elapsed_seconds', 0.0)) / 60.0:.2f} | "
            f"{int(row.get('attempts_used', 0))} | "
            f"{int(row.get('retry_budget', 0))} | "
            f"{int(row.get('retries_used', 0))} |"
        )

    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_context(args: argparse.Namespace) -> dict[str, str]:
    return {
        "workflow": args.workflow,
        "run_id": args.run_id,
        "run_attempt": args.run_attempt,
        "event_name": args.event_name,
        "ref": args.ref,
        "sha": args.sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CI runtime+flake trend artifacts.")
    parser.add_argument(
        "--summary-file",
        action="append",
        dest="summary_files",
        required=True,
        help="Path to a runtime policy summary text file. Can be provided multiple times.",
    )
    parser.add_argument(
        "--latest",
        default="Docs/implementation/reports/ci_runtime_flake_trend_latest.json",
        help="Path to latest JSON report output.",
    )
    parser.add_argument(
        "--history",
        default="Docs/implementation/reports/ci_runtime_flake_trend_history.jsonl",
        help="Path to append-only trend history JSONL output.",
    )
    parser.add_argument(
        "--dashboard",
        default="Docs/implementation/reports/ci_runtime_flake_trend_dashboard.md",
        help="Path to dashboard markdown output.",
    )
    parser.add_argument(
        "--trend-window",
        type=int,
        default=20,
        help="Number of recent rows per gate to include in trend rollups.",
    )
    parser.add_argument(
        "--timeline-limit",
        type=int,
        default=15,
        help="Number of recent history rows rendered in dashboard.",
    )
    parser.add_argument(
        "--objective",
        default="Docs/manifest/00_overview.md#Core Objective",
        help="Objective anchor string stored in output artifacts.",
    )
    parser.add_argument("--run-id", default=os.getenv("GITHUB_RUN_ID", "local"))
    parser.add_argument("--run-attempt", default=os.getenv("GITHUB_RUN_ATTEMPT", "1"))
    parser.add_argument("--workflow", default=os.getenv("GITHUB_WORKFLOW", "local"))
    parser.add_argument("--event-name", default=os.getenv("GITHUB_EVENT_NAME", "local"))
    parser.add_argument("--ref", default=os.getenv("GITHUB_REF", "local"))
    parser.add_argument("--sha", default=os.getenv("GITHUB_SHA", "local"))
    args = parser.parse_args()

    generated_at = datetime.now(timezone.utc).isoformat()
    latest_path = Path(args.latest)
    history_path = Path(args.history)
    dashboard_path = Path(args.dashboard)

    context = _build_context(args)
    parsed_summaries: list[dict[str, Any]] = []
    for path_str in args.summary_files:
        summary = _parse_runtime_summary(Path(path_str))
        parsed_summaries.append(summary)

    if not parsed_summaries:
        raise ValueError("at least one --summary-file with runtime_policy_summary data is required")

    history_entries: list[dict[str, Any]] = []
    for summary in parsed_summaries:
        entry = {
            "generated_at": generated_at,
            "objective": args.objective,
            "workflow": context["workflow"],
            "run_id": context["run_id"],
            "run_attempt": context["run_attempt"],
            "event_name": context["event_name"],
            "ref": context["ref"],
            "sha": context["sha"],
            **summary,
        }
        history_entries.append(entry)

    history_rows = _append_history(history_path, history_entries)

    runtime_target_misses = sum(1 for summary in parsed_summaries if not bool(summary.get("runtime_target_met", False)))
    retry_budget_misses = sum(1 for summary in parsed_summaries if not bool(summary.get("retry_budget_met", False)))
    gate_failures = sum(1 for summary in parsed_summaries if str(summary.get("status", "unknown")) != "pass")
    status = "pass" if runtime_target_misses == 0 and retry_budget_misses == 0 and gate_failures == 0 else "fail"

    trend_rows = _trend_by_gate(history_rows, window=max(args.trend_window, 1))
    report = {
        "generated_at": generated_at,
        "objective": args.objective,
        "context": context,
        "overall": {
            "status": status,
            "signals_total": len(parsed_summaries),
            "gate_failures": gate_failures,
            "runtime_target_misses": runtime_target_misses,
            "retry_budget_misses": retry_budget_misses,
        },
        "summaries": parsed_summaries,
        "history_path": str(history_path),
        "dashboard_path": str(dashboard_path),
        "trend_by_gate": trend_rows,
    }

    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    _write_dashboard(
        dashboard_path=dashboard_path,
        report=report,
        history_rows=history_rows,
        history_path=history_path,
        trend_rows=trend_rows,
        timeline_limit=max(args.timeline_limit, 1),
    )

    print(
        "ci_runtime_trend_summary "
        f"status={status} "
        f"signals={len(parsed_summaries)} "
        f"history_rows={len(history_rows)} "
        f"latest={latest_path} "
        f"dashboard={dashboard_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
