#!/usr/bin/env python3
"""Publish CI observability payloads to an external sink endpoint.

The command is designed for fail-open rollout:
- mode=disabled: no publish attempt
- mode=dry_run: build payload/report only
- mode=active: POST payload to sink URL

Delivery failures can remain non-blocking via --fail-open true.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl_tail(path: Path, max_rows: int) -> list[Any]:
    rows: list[Any] = []
    if max_rows <= 0:
        return rows
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-max_rows:]


def _read_text(path: Path, max_chars: int) -> str:
    text = path.read_text(encoding="utf-8")
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _maybe_add_json_signal(
    signals: dict[str, Any],
    signal_stats: dict[str, Any],
    missing: list[str],
    signal_key: str,
    path_str: str,
) -> None:
    if not path_str:
        return
    path = Path(path_str)
    if not path.exists():
        missing.append(path_str)
        return
    try:
        payload = _read_json(path)
    except Exception:
        missing.append(path_str)
        return
    signals[signal_key] = payload
    signal_stats[signal_key] = {
        "path": str(path),
        "kind": "json",
    }


def _maybe_add_jsonl_signal(
    signals: dict[str, Any],
    signal_stats: dict[str, Any],
    missing: list[str],
    signal_key: str,
    path_str: str,
    max_rows: int,
) -> None:
    if not path_str:
        return
    path = Path(path_str)
    if not path.exists():
        missing.append(path_str)
        return
    rows = _read_jsonl_tail(path, max_rows=max_rows)
    signals[signal_key] = rows
    signal_stats[signal_key] = {
        "path": str(path),
        "kind": "jsonl_tail",
        "rows": len(rows),
    }


def _maybe_add_text_signal(
    signals: dict[str, Any],
    signal_stats: dict[str, Any],
    missing: list[str],
    signal_key: str,
    path_str: str,
    max_chars: int,
) -> None:
    if not path_str:
        return
    path = Path(path_str)
    if not path.exists():
        missing.append(path_str)
        return
    text = _read_text(path, max_chars=max_chars)
    signals[signal_key] = text
    signal_stats[signal_key] = {
        "path": str(path),
        "kind": "text",
        "chars": len(text),
    }


def _build_payload(args: argparse.Namespace) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    missing: list[str] = []
    signals: dict[str, Any] = {}
    signal_stats: dict[str, Any] = {}

    _maybe_add_json_signal(
        signals,
        signal_stats,
        missing,
        "objective_metrics_latest",
        args.objective_latest,
    )
    _maybe_add_jsonl_signal(
        signals,
        signal_stats,
        missing,
        "objective_metrics_history_tail",
        args.objective_history,
        max_rows=args.objective_history_tail,
    )
    _maybe_add_json_signal(
        signals,
        signal_stats,
        missing,
        "observability_snapshot_latest",
        args.observability_latest,
    )
    _maybe_add_json_signal(
        signals,
        signal_stats,
        missing,
        "runtime_trend_latest",
        args.runtime_trend_latest,
    )
    _maybe_add_text_signal(
        signals,
        signal_stats,
        missing,
        "runtime_trend_dashboard",
        args.runtime_trend_dashboard,
        max_chars=args.max_dashboard_chars,
    )
    _maybe_add_text_signal(
        signals,
        signal_stats,
        missing,
        "runtime_policy_summary",
        args.runtime_policy_summary,
        max_chars=args.max_policy_chars,
    )

    payload = {
        "generated_at": _now_iso(),
        "objective": args.objective,
        "source": {
            "workflow": args.workflow,
            "job": args.job,
            "event_name": args.event_name,
            "ref": args.ref,
            "sha": args.sha,
            "run_id": args.run_id,
            "run_attempt": args.run_attempt,
        },
        "signals": signals,
    }
    return payload, missing, signal_stats


def _sink_host(url: str) -> str:
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc


def _post_payload(url: str, payload: dict[str, Any], timeout_seconds: int) -> tuple[int | None, str]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "agora-observability-sink/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status_code = response.getcode()
            return status_code, ""
    except urllib.error.HTTPError as exc:
        return exc.code, f"http_error:{exc.reason}"
    except Exception as exc:  # pragma: no cover - exercised via subprocess tests
        return None, f"request_error:{exc}"


def _write_summary_markdown(report: dict[str, Any], path: Path) -> None:
    signals = report.get("signals_included", [])
    missing = report.get("signals_missing", [])
    lines = [
        "## Observability Sink Publish",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Mode: `{report.get('mode')}`",
        f"- Fail-open: `{report.get('fail_open')}`",
        f"- Sink host: `{report.get('sink_host') or 'none'}`",
        f"- Response code: `{report.get('response_code')}`",
        f"- Signals included: `{', '.join(signals) if signals else 'none'}`",
        f"- Signals missing: `{', '.join(missing) if missing else 'none'}`",
    ]
    if report.get("error"):
        lines.append(f"- Error: `{report['error']}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish observability payload to external sink.")
    parser.add_argument(
        "--mode",
        choices=["disabled", "dry_run", "active"],
        default="dry_run",
        help="Publish mode.",
    )
    parser.add_argument(
        "--sink-url",
        default="",
        help="External sink URL to POST JSON payload to.",
    )
    parser.add_argument(
        "--fail-open",
        type=_parse_bool,
        default=True,
        help="Treat delivery failures as non-blocking.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=15,
        help="HTTP timeout for active mode.",
    )
    parser.add_argument(
        "--objective",
        default="Docs/manifest/00_overview.md#Core Objective",
        help="Objective anchor included in sink payload.",
    )
    parser.add_argument("--workflow", default="")
    parser.add_argument("--job", default="")
    parser.add_argument("--event-name", default="")
    parser.add_argument("--ref", default="")
    parser.add_argument("--sha", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-attempt", default="")

    parser.add_argument("--objective-latest", default="")
    parser.add_argument("--objective-history", default="")
    parser.add_argument("--objective-history-tail", type=int, default=20)
    parser.add_argument("--observability-latest", default="")
    parser.add_argument("--runtime-trend-latest", default="")
    parser.add_argument("--runtime-trend-dashboard", default="")
    parser.add_argument("--runtime-policy-summary", default="")
    parser.add_argument("--max-dashboard-chars", type=int, default=12000)
    parser.add_argument("--max-policy-chars", type=int, default=2000)

    parser.add_argument(
        "--report",
        default="/tmp/observability-sink-publish-report.json",
        help="Output JSON report path.",
    )
    parser.add_argument(
        "--summary-markdown",
        default="",
        help="Optional markdown summary output path.",
    )
    args = parser.parse_args()

    payload, missing, signal_stats = _build_payload(args)
    payload_bytes = len(json.dumps(payload).encode("utf-8"))
    signals_included = sorted(payload.get("signals", {}).keys())

    status = "dry_run"
    response_code: int | None = None
    error = ""

    if args.mode == "disabled":
        status = "disabled"
    elif args.mode == "dry_run":
        status = "dry_run"
    else:
        if not args.sink_url:
            if args.fail_open:
                status = "warn_no_sink_url"
            else:
                status = "fail_no_sink_url"
                error = "missing_sink_url"
        elif not signals_included:
            if args.fail_open:
                status = "warn_no_signals"
            else:
                status = "fail_no_signals"
                error = "no_signals_to_publish"
        else:
            response_code, error = _post_payload(
                url=args.sink_url,
                payload=payload,
                timeout_seconds=args.timeout_seconds,
            )
            if response_code is not None and 200 <= response_code < 300:
                status = "pass"
            elif args.fail_open:
                status = "warn_delivery_failed"
            else:
                status = "fail_delivery_failed"

    report = {
        "generated_at": _now_iso(),
        "status": status,
        "mode": args.mode,
        "fail_open": bool(args.fail_open),
        "sink_url_set": bool(args.sink_url),
        "sink_host": _sink_host(args.sink_url),
        "response_code": response_code,
        "error": error,
        "signals_included": signals_included,
        "signals_missing": sorted(set(missing)),
        "signal_stats": signal_stats,
        "payload_bytes": payload_bytes,
        "source": payload["source"],
        "objective": payload["objective"],
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.summary_markdown:
        _write_summary_markdown(report, Path(args.summary_markdown))

    print(
        "observability_sink_publish "
        f"status={status} "
        f"mode={args.mode} "
        f"fail_open={str(bool(args.fail_open)).lower()} "
        f"sink_url_set={str(bool(args.sink_url)).lower()} "
        f"response_code={response_code if response_code is not None else 'none'} "
        f"signals={','.join(signals_included) if signals_included else 'none'} "
        f"report={report_path}"
    )

    return 0 if not status.startswith("fail") else 2


if __name__ == "__main__":
    raise SystemExit(main())
