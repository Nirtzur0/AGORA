from __future__ import annotations

import http.server
import json
import socketserver
import subprocess
import sys
import threading
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "publish_observability_sink.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_publish(
    *,
    mode: str,
    report_path: Path,
    summary_path: Path,
    sink_url: str = "",
    fail_open: bool = True,
    objective_latest: Path | None = None,
    objective_history: Path | None = None,
    observability_latest: Path | None = None,
    runtime_trend_latest: Path | None = None,
    runtime_dashboard: Path | None = None,
    runtime_policy: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(SCRIPT_PATH),
        "--mode",
        mode,
        "--sink-url",
        sink_url,
        "--fail-open",
        "true" if fail_open else "false",
        "--workflow",
        "CI",
        "--job",
        "objective-metrics-gate",
        "--event-name",
        "workflow_dispatch",
        "--ref",
        "refs/heads/main",
        "--sha",
        "abc123",
        "--run-id",
        "42",
        "--run-attempt",
        "1",
        "--report",
        str(report_path),
        "--summary-markdown",
        str(summary_path),
    ]
    if objective_latest:
        cmd.extend(["--objective-latest", str(objective_latest)])
    if objective_history:
        cmd.extend(["--objective-history", str(objective_history)])
    if observability_latest:
        cmd.extend(["--observability-latest", str(observability_latest)])
    if runtime_trend_latest:
        cmd.extend(["--runtime-trend-latest", str(runtime_trend_latest)])
    if runtime_dashboard:
        cmd.extend(["--runtime-trend-dashboard", str(runtime_dashboard)])
    if runtime_policy:
        cmd.extend(["--runtime-policy-summary", str(runtime_policy)])
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _read_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class _CaptureHandler(http.server.BaseHTTPRequestHandler):
    request_count = 0
    last_payload: dict | None = None

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        _CaptureHandler.request_count += 1
        _CaptureHandler.last_payload = json.loads(body.decode("utf-8"))
        self.send_response(202)
        self.end_headers()
        self.wfile.write(b"accepted")

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def _start_capture_server() -> tuple[socketserver.TCPServer, int, threading.Thread]:
    server = socketserver.TCPServer(("127.0.0.1", 0), _CaptureHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port, thread


def test_publish_observability_sink_dry_run_writes_report_and_summary(tmp_path: Path) -> None:
    objective_latest = tmp_path / "objective_latest.json"
    objective_history = tmp_path / "objective_history.jsonl"
    observability_latest = tmp_path / "observability_latest.json"
    report_path = tmp_path / "publish_report.json"
    summary_path = tmp_path / "publish_summary.md"

    _write_json(
        objective_latest,
        {
            "overall": {"status": "pass", "required_metrics": 2, "passed_metrics": 2, "pass_rate": 1.0},
            "metrics": [{"id": "citation_integrity"}, {"id": "authority_boundary"}],
        },
    )
    _write_jsonl(
        objective_history,
        [
            {"overall": {"status": "pass"}},
            {"overall": {"status": "pass"}},
        ],
    )
    _write_json(
        observability_latest,
        {
            "overall_status": "pass",
            "artifact_snapshot": {"status": "pass"},
            "objective_snapshot": {"status": "pass"},
        },
    )

    run = _run_publish(
        mode="dry_run",
        report_path=report_path,
        summary_path=summary_path,
        objective_latest=objective_latest,
        objective_history=objective_history,
        observability_latest=observability_latest,
    )

    assert run.returncode == 0
    assert "observability_sink_publish status=dry_run" in run.stdout
    assert report_path.exists()
    assert summary_path.exists()

    report = _read_report(report_path)
    assert report["status"] == "dry_run"
    assert "objective_metrics_latest" in report["signals_included"]
    assert "observability_snapshot_latest" in report["signals_included"]
    assert report["payload_bytes"] > 0


def test_publish_observability_sink_active_posts_payload(tmp_path: Path) -> None:
    _CaptureHandler.request_count = 0
    _CaptureHandler.last_payload = None
    server, port, thread = _start_capture_server()
    report_path = tmp_path / "report.json"
    summary_path = tmp_path / "summary.md"
    runtime_latest = tmp_path / "runtime_latest.json"

    _write_json(
        runtime_latest,
        {
            "overall": {"status": "pass", "signals_total": 1},
            "summaries": [{"gate": "cmd-13-nightly-full-suite", "status": "pass"}],
        },
    )

    try:
        run = _run_publish(
            mode="active",
            sink_url=f"http://127.0.0.1:{port}/sink",
            report_path=report_path,
            summary_path=summary_path,
            runtime_trend_latest=runtime_latest,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert run.returncode == 0
    assert "status=pass" in run.stdout
    report = _read_report(report_path)
    assert report["status"] == "pass"
    assert report["response_code"] == 202
    assert _CaptureHandler.request_count == 1
    assert _CaptureHandler.last_payload is not None
    assert "runtime_trend_latest" in _CaptureHandler.last_payload["signals"]


def test_publish_observability_sink_fail_open_on_delivery_error(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    summary_path = tmp_path / "summary.md"
    runtime_policy = tmp_path / "runtime_policy.txt"
    runtime_policy.write_text("runtime_policy_summary gate=cmd-13-nightly-full-suite status=pass\n", encoding="utf-8")

    run = _run_publish(
        mode="active",
        sink_url="http://127.0.0.1:9/sink",
        fail_open=True,
        report_path=report_path,
        summary_path=summary_path,
        runtime_policy=runtime_policy,
    )

    assert run.returncode == 0
    report = _read_report(report_path)
    assert report["status"] == "warn_delivery_failed"
    assert report["error"].startswith("request_error:")


def test_publish_observability_sink_fail_closed_on_delivery_error(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    summary_path = tmp_path / "summary.md"
    runtime_policy = tmp_path / "runtime_policy.txt"
    runtime_policy.write_text("runtime_policy_summary gate=release-tag-gate status=fail\n", encoding="utf-8")

    run = _run_publish(
        mode="active",
        sink_url="http://127.0.0.1:9/sink",
        fail_open=False,
        report_path=report_path,
        summary_path=summary_path,
        runtime_policy=runtime_policy,
    )

    assert run.returncode == 2
    report = _read_report(report_path)
    assert report["status"] == "fail_delivery_failed"
