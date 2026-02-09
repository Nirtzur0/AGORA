#!/usr/bin/env python3
"""Generate an objective observability snapshot from repo-local signals.

This command consolidates:
- artifact provenance/freshness coverage state
- objective metrics latest status and trend history

It writes machine-readable JSON and a human-readable markdown dashboard.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_iso8601_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


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


def _load_artifacts(index_path: Path) -> list[dict[str, Any]]:
    data = _read_json(index_path)
    if not data:
        return []
    artifacts = data.get("artifacts")
    return artifacts if isinstance(artifacts, list) else []


def _build_artifact_snapshot(index_path: Path, warn_age_days: int, max_age_days: int) -> dict[str, Any]:
    artifacts = _load_artifacts(index_path)
    now = datetime.now(timezone.utc)
    required_fields = ("id", "url", "retrieved_at")

    missing = 0
    invalid_timestamps = 0
    warnings = 0
    stale = 0

    for artifact in artifacts:
        missing_fields = [field for field in required_fields if not artifact.get(field)]
        if missing_fields:
            missing += 1
            continue

        retrieved_at = str(artifact["retrieved_at"])
        try:
            age_days = int((now - _parse_iso8601_utc(retrieved_at)).total_seconds() // 86400)
        except Exception:
            invalid_timestamps += 1
            continue

        if age_days > max_age_days:
            stale += 1
        elif age_days > warn_age_days:
            warnings += 1

    valid_entries = len(artifacts) - missing - invalid_timestamps
    coverage_percent = (
        0.0 if not artifacts else round((valid_entries / len(artifacts)) * 100.0, 1)
    )
    if missing or invalid_timestamps or stale:
        status = "fail"
    elif warnings:
        status = "warn"
    else:
        status = "pass"

    return {
        "status": status,
        "index_path": str(index_path),
        "artifacts": len(artifacts),
        "coverage_percent": coverage_percent,
        "warnings": warnings,
        "stale": stale,
        "missing": missing,
        "invalid_timestamps": invalid_timestamps,
        "warn_age_days": warn_age_days,
        "max_age_days": max_age_days,
    }


def _status_sequence(history_entries: list[dict[str, Any]], limit: int) -> list[str]:
    if limit <= 0:
        return []
    statuses: list[str] = []
    for entry in history_entries[-limit:]:
        overall = entry.get("overall", {})
        if isinstance(overall, dict):
            statuses.append(str(overall.get("status", "unknown")))
        else:
            statuses.append("unknown")
    return statuses


def _pass_streak(history_entries: list[dict[str, Any]]) -> int:
    streak = 0
    for entry in reversed(history_entries):
        overall = entry.get("overall", {})
        status = str(overall.get("status", "unknown")) if isinstance(overall, dict) else "unknown"
        if status != "pass":
            break
        streak += 1
    return streak


def _build_objective_snapshot(latest_path: Path, history_path: Path) -> dict[str, Any]:
    latest = _read_json(latest_path)
    history = _read_jsonl(history_path)

    if not latest:
        return {
            "status": "fail",
            "latest_path": str(latest_path),
            "history_path": str(history_path),
            "error": "missing_or_invalid_objective_latest",
            "history_runs": len(history),
            "recent_statuses": _status_sequence(history, 10),
            "pass_streak": _pass_streak(history),
        }

    overall = latest.get("overall", {})
    metrics = latest.get("metrics", [])
    status = str(overall.get("status", "fail"))
    return {
        "status": "pass" if status == "pass" else "fail",
        "latest_path": str(latest_path),
        "history_path": str(history_path),
        "generated_at": latest.get("generated_at"),
        "required_metrics": int(overall.get("required_metrics", 0)),
        "passed_metrics": int(overall.get("passed_metrics", 0)),
        "pass_rate": float(overall.get("pass_rate", 0.0)),
        "metric_ids": [
            str(metric.get("id", "unknown")) for metric in metrics if isinstance(metric, dict)
        ],
        "history_runs": len(history),
        "recent_statuses": _status_sequence(history, 10),
        "pass_streak": _pass_streak(history),
    }


def _overall_status(artifact_status: str, objective_status: str) -> str:
    if artifact_status == "fail" or objective_status == "fail":
        return "fail"
    if artifact_status == "warn":
        return "warn"
    return "pass"


def _write_dashboard(report: dict[str, Any], dashboard_path: Path) -> None:
    artifacts = report.get("artifact_snapshot", {})
    objective = report.get("objective_snapshot", {})
    overall = str(report.get("overall_status", "unknown"))
    generated_at = str(report.get("generated_at", "unknown"))

    lines = [
        "# Observability Snapshot Dashboard",
        "",
        f"Generated at: `{generated_at}`",
        f"Overall status: `{overall}`",
        "",
        "## Signal Summary",
        "",
        "| Signal | Status | Key values |",
        "|---|---|---|",
        (
            "| Artifact freshness/provenance | "
            f"`{artifacts.get('status', 'unknown')}` | "
            f"coverage={artifacts.get('coverage_percent', 0.0)}%, "
            f"warnings={artifacts.get('warnings', 0)}, "
            f"stale={artifacts.get('stale', 0)}, "
            f"missing={artifacts.get('missing', 0)}, "
            f"invalid_ts={artifacts.get('invalid_timestamps', 0)} |"
        ),
        (
            "| Objective metrics | "
            f"`{objective.get('status', 'unknown')}` | "
            f"passed={objective.get('passed_metrics', 0)}/{objective.get('required_metrics', 0)}, "
            f"history_runs={objective.get('history_runs', 0)}, "
            f"pass_streak={objective.get('pass_streak', 0)} |"
        ),
        "",
        "## Commands",
        "",
        "```bash",
        "make check-observability-slos",
        "make check-objective-metrics",
        "make check-observability-snapshot",
        "```",
        "",
        "## Outputs",
        "",
        "- `Docs/implementation/reports/observability_snapshot_latest.json`",
        "- `Docs/implementation/reports/observability_snapshot_dashboard.md`",
    ]

    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate observability snapshot report/dashboard.")
    parser.add_argument(
        "--index",
        default="Docs/artifacts/index.json",
        help="Path to artifact index.json",
    )
    parser.add_argument(
        "--warn-age-days",
        type=int,
        default=75,
        help="Warn threshold for artifact freshness age (days).",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=90,
        help="Fail threshold for artifact freshness age (days).",
    )
    parser.add_argument(
        "--objective-latest",
        default="Docs/implementation/reports/objective_metrics_latest.json",
        help="Path to objective metrics latest JSON output.",
    )
    parser.add_argument(
        "--objective-history",
        default="Docs/implementation/reports/objective_metrics_history.jsonl",
        help="Path to objective metrics history JSONL output.",
    )
    parser.add_argument(
        "--report",
        default="Docs/implementation/reports/observability_snapshot_latest.json",
        help="Path to observability snapshot JSON output.",
    )
    parser.add_argument(
        "--dashboard",
        default="Docs/implementation/reports/observability_snapshot_dashboard.md",
        help="Path to observability snapshot markdown dashboard output.",
    )
    args = parser.parse_args()

    artifact_snapshot = _build_artifact_snapshot(
        index_path=Path(args.index),
        warn_age_days=args.warn_age_days,
        max_age_days=args.max_age_days,
    )
    objective_snapshot = _build_objective_snapshot(
        latest_path=Path(args.objective_latest),
        history_path=Path(args.objective_history),
    )
    overall_status = _overall_status(
        artifact_status=str(artifact_snapshot.get("status", "fail")),
        objective_status=str(objective_snapshot.get("status", "fail")),
    )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "objective": "Docs/manifest/00_overview.md#Core Objective",
        "overall_status": overall_status,
        "artifact_snapshot": artifact_snapshot,
        "objective_snapshot": objective_snapshot,
    }

    report_path = Path(args.report)
    dashboard_path = Path(args.dashboard)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_dashboard(report, dashboard_path)

    print(
        "observability_snapshot_summary "
        f"status={overall_status} "
        f"artifact_status={artifact_snapshot.get('status', 'unknown')} "
        f"objective_status={objective_snapshot.get('status', 'unknown')} "
        f"report={report_path} "
        f"dashboard={dashboard_path}"
    )

    return 0 if overall_status != "fail" else 2


if __name__ == "__main__":
    raise SystemExit(main())
