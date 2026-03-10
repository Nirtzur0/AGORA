from __future__ import annotations

import http.server
import json
import socketserver
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_sink_evidence_recency.py"


def _run_check(
    *,
    api_base_url: str,
    now: str,
    report_path: Path,
    summary_path: Path,
    allow_current_release_candidate: bool = False,
    current_run_id: str = "",
) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(SCRIPT_PATH),
        "--repo",
        "acme/agora",
        "--workflow-file",
        "ci.yml",
        "--api-base-url",
        api_base_url,
        "--max-runs",
        "20",
        "--now",
        now,
        "--report",
        str(report_path),
        "--summary-markdown",
        str(summary_path),
    ]
    if allow_current_release_candidate:
        cmd.extend(["--allow-current-release-candidate", "true"])
    if current_run_id:
        cmd.extend(["--current-run-id", current_run_id])

    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class _GitHubStubHandler(http.server.BaseHTTPRequestHandler):
    runs: list[dict] = []
    jobs_by_run: dict[int, list[dict]] = {}
    artifacts_by_run: dict[int, list[dict]] = {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/repos/acme/agora/actions/workflows/ci.yml/runs":
            self._send_json({"workflow_runs": _GitHubStubHandler.runs})
            return

        if path.startswith("/repos/acme/agora/actions/runs/") and path.endswith("/jobs"):
            run_id = self._extract_run_id(path)
            payload = _GitHubStubHandler.jobs_by_run.get(run_id, [])
            self._send_json({"jobs": payload})
            return

        if path.startswith("/repos/acme/agora/actions/runs/") and path.endswith("/artifacts"):
            run_id = self._extract_run_id(path)
            payload = _GitHubStubHandler.artifacts_by_run.get(run_id, [])
            self._send_json({"artifacts": payload})
            return

        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"not found")

    @staticmethod
    def _extract_run_id(path: str) -> int:
        parts = path.split("/")
        try:
            return int(parts[6])
        except Exception as exc:  # pragma: no cover - defensive branch
            raise ValueError(f"could not parse run id from path: {path}") from exc

    def _send_json(self, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def _start_stub_server() -> tuple[socketserver.TCPServer, int, threading.Thread]:
    server = socketserver.TCPServer(("127.0.0.1", 0), _GitHubStubHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port, thread


def _read_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_check_sink_evidence_recency_passes_when_all_gates_are_fresh(tmp_path: Path) -> None:
    _GitHubStubHandler.runs = [
        {
            "id": 301,
            "conclusion": "success",
            "updated_at": "2026-02-08T10:00:00Z",
            "html_url": "https://github.com/acme/agora/actions/runs/301",
        },
        {
            "id": 302,
            "conclusion": "success",
            "updated_at": "2026-02-06T10:00:00Z",
            "html_url": "https://github.com/acme/agora/actions/runs/302",
        },
        {
            "id": 303,
            "conclusion": "success",
            "updated_at": "2026-01-25T10:00:00Z",
            "html_url": "https://github.com/acme/agora/actions/runs/303",
        },
    ]
    _GitHubStubHandler.jobs_by_run = {
        301: [{"name": "CMD-13 nightly full-suite gate", "conclusion": "success"}],
        302: [{"name": "Objective metrics gate", "conclusion": "success"}],
        303: [{"name": "Release tag gate (v* fail-closed)", "conclusion": "success"}],
    }
    _GitHubStubHandler.artifacts_by_run = {
        301: [{"name": "cmd-13-nightly-runtime-trend", "expired": False}],
        302: [{"name": "observability-snapshot-report", "expired": False}],
        303: [{"name": "release-tag-gate-artifacts", "expired": False}],
    }

    server, port, thread = _start_stub_server()
    report_path = tmp_path / "report.json"
    summary_path = tmp_path / "summary.md"
    try:
        run = _run_check(
            api_base_url=f"http://127.0.0.1:{port}",
            now="2026-02-09T12:00:00Z",
            report_path=report_path,
            summary_path=summary_path,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert run.returncode == 0
    assert "sink_evidence_recency_summary status=pass" in run.stdout
    report = _read_report(report_path)
    assert report["overall_status"] == "pass"
    assert report["failing_checks"] == 0
    statuses = {entry["gate"]: entry["status"] for entry in report["checks"]}
    assert statuses["objective-metrics-gate"] == "pass"
    assert statuses["cmd-13-nightly-full-suite"] == "pass"
    assert statuses["release-tag-gate"] == "pass"


def test_check_sink_evidence_recency_fails_for_stale_and_missing_evidence(tmp_path: Path) -> None:
    _GitHubStubHandler.runs = [
        {
            "id": 401,
            "conclusion": "success",
            "updated_at": "2026-02-09T04:00:00Z",
            "html_url": "https://github.com/acme/agora/actions/runs/401",
        },
        {
            "id": 402,
            "conclusion": "success",
            "updated_at": "2026-01-10T04:00:00Z",
            "html_url": "https://github.com/acme/agora/actions/runs/402",
        },
        {
            "id": 403,
            "conclusion": "success",
            "updated_at": "2026-02-05T04:00:00Z",
            "html_url": "https://github.com/acme/agora/actions/runs/403",
        },
    ]
    _GitHubStubHandler.jobs_by_run = {
        401: [{"name": "Objective metrics gate", "conclusion": "success"}],
        402: [{"name": "CMD-13 nightly full-suite gate", "conclusion": "success"}],
        403: [{"name": "Release tag gate (v* fail-closed)", "conclusion": "success"}],
    }
    _GitHubStubHandler.artifacts_by_run = {
        401: [{"name": "objective-metrics-report", "expired": False}],
        402: [{"name": "cmd-13-nightly-runtime-trend", "expired": False}],
        403: [{"name": "release-tag-gate-artifacts", "expired": False}],
    }

    server, port, thread = _start_stub_server()
    report_path = tmp_path / "report.json"
    summary_path = tmp_path / "summary.md"
    try:
        run = _run_check(
            api_base_url=f"http://127.0.0.1:{port}",
            now="2026-02-09T12:00:00Z",
            report_path=report_path,
            summary_path=summary_path,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert run.returncode == 2
    assert "sink_evidence_recency_summary status=fail" in run.stdout
    report = _read_report(report_path)
    assert report["overall_status"] == "fail"
    assert report["missing_checks"] == 1
    assert report["stale_checks"] == 1
    statuses = {entry["gate"]: entry["status"] for entry in report["checks"]}
    assert statuses["objective-metrics-gate"] == "missing"
    assert statuses["cmd-13-nightly-full-suite"] == "stale"
    assert statuses["release-tag-gate"] == "pass"


def test_check_sink_evidence_recency_allows_inflight_release_candidate(tmp_path: Path) -> None:
    _GitHubStubHandler.runs = [
        {
            "id": 501,
            "conclusion": "success",
            "updated_at": "2026-02-08T09:00:00Z",
            "html_url": "https://github.com/acme/agora/actions/runs/501",
        },
        {
            "id": 502,
            "conclusion": "success",
            "updated_at": "2026-02-06T09:00:00Z",
            "html_url": "https://github.com/acme/agora/actions/runs/502",
        },
        {
            "id": 503,
            "conclusion": "success",
            "updated_at": "2025-12-01T09:00:00Z",
            "html_url": "https://github.com/acme/agora/actions/runs/503",
        },
    ]
    _GitHubStubHandler.jobs_by_run = {
        501: [{"name": "CMD-13 nightly full-suite gate", "conclusion": "success"}],
        502: [{"name": "Objective metrics gate", "conclusion": "success"}],
        503: [{"name": "Release tag gate (v* fail-closed)", "conclusion": "success"}],
    }
    _GitHubStubHandler.artifacts_by_run = {
        501: [{"name": "cmd-13-nightly-runtime-trend", "expired": False}],
        502: [{"name": "observability-snapshot-report", "expired": False}],
        503: [{"name": "release-tag-gate-artifacts", "expired": False}],
    }

    server, port, thread = _start_stub_server()
    report_path = tmp_path / "report.json"
    summary_path = tmp_path / "summary.md"
    try:
        run = _run_check(
            api_base_url=f"http://127.0.0.1:{port}",
            now="2026-02-09T12:00:00Z",
            report_path=report_path,
            summary_path=summary_path,
            allow_current_release_candidate=True,
            current_run_id="999999999",
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert run.returncode == 0
    report = _read_report(report_path)
    assert report["overall_status"] == "pass"
    statuses = {entry["gate"]: entry for entry in report["checks"]}
    assert statuses["release-tag-gate"]["status"] == "pass_candidate_run"
    assert statuses["release-tag-gate"]["run_id"] == "999999999"
