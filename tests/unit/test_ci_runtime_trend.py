from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_ci_runtime_trend.py"


def _write_runtime_summary(
    path: Path,
    *,
    gate: str,
    status: str,
    attempts_used: int,
    retry_budget: int,
    timeout_minutes: int,
    runtime_target_minutes: int,
    elapsed_seconds: int,
) -> None:
    path.write_text(
        (
            "runtime_policy_summary "
            f"gate={gate} "
            f"status={status} "
            f"attempts_used={attempts_used} "
            f"retry_budget={retry_budget} "
            f"timeout_minutes={timeout_minutes} "
            f"runtime_target_minutes={runtime_target_minutes} "
            f"elapsed_seconds={elapsed_seconds}\n"
        ),
        encoding="utf-8",
    )


def _run_trend_script(
    *,
    summary_files: list[Path],
    latest: Path,
    history: Path,
    dashboard: Path,
    run_id: str,
    run_attempt: str,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(SCRIPT_PATH),
        "--latest",
        str(latest),
        "--history",
        str(history),
        "--dashboard",
        str(dashboard),
        "--run-id",
        run_id,
        "--run-attempt",
        run_attempt,
        "--workflow",
        "CI",
        "--event-name",
        "workflow_dispatch",
        "--ref",
        "refs/heads/main",
        "--sha",
        "abc123",
    ]
    for summary in summary_files:
        cmd.extend(["--summary-file", str(summary)])
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def test_build_ci_runtime_trend_outputs_latest_history_and_dashboard(tmp_path: Path) -> None:
    nightly_summary = tmp_path / "nightly.txt"
    release_summary = tmp_path / "release.txt"
    latest_path = tmp_path / "latest.json"
    history_path = tmp_path / "history.jsonl"
    dashboard_path = tmp_path / "dashboard.md"

    _write_runtime_summary(
        nightly_summary,
        gate="cmd-13-nightly-full-suite",
        status="pass",
        attempts_used=1,
        retry_budget=1,
        timeout_minutes=180,
        runtime_target_minutes=90,
        elapsed_seconds=3000,
    )
    _write_runtime_summary(
        release_summary,
        gate="release-tag-gate",
        status="pass",
        attempts_used=1,
        retry_budget=0,
        timeout_minutes=210,
        runtime_target_minutes=120,
        elapsed_seconds=4200,
    )

    run = _run_trend_script(
        summary_files=[nightly_summary, release_summary],
        latest=latest_path,
        history=history_path,
        dashboard=dashboard_path,
        run_id="100",
        run_attempt="1",
    )
    assert "ci_runtime_trend_summary status=pass" in run.stdout
    assert latest_path.exists()
    assert history_path.exists()
    assert dashboard_path.exists()

    latest_payload = json.loads(latest_path.read_text(encoding="utf-8"))
    assert latest_payload["overall"]["signals_total"] == 2
    assert len(latest_payload["summaries"]) == 2
    assert {entry["gate"] for entry in latest_payload["summaries"]} == {
        "cmd-13-nightly-full-suite",
        "release-tag-gate",
    }

    history_rows = _read_jsonl(history_path)
    assert len(history_rows) == 2
    assert {entry["gate"] for entry in history_rows} == {
        "cmd-13-nightly-full-suite",
        "release-tag-gate",
    }

    dashboard = dashboard_path.read_text(encoding="utf-8")
    assert "CI Runtime and Flake Trend Dashboard" in dashboard
    assert "cmd-13-nightly-full-suite" in dashboard
    assert "release-tag-gate" in dashboard


def test_build_ci_runtime_trend_dedupes_same_run_gate_entries(tmp_path: Path) -> None:
    nightly_summary = tmp_path / "nightly.txt"
    latest_path = tmp_path / "latest.json"
    history_path = tmp_path / "history.jsonl"
    dashboard_path = tmp_path / "dashboard.md"

    _write_runtime_summary(
        nightly_summary,
        gate="cmd-13-nightly-full-suite",
        status="pass",
        attempts_used=2,
        retry_budget=1,
        timeout_minutes=180,
        runtime_target_minutes=90,
        elapsed_seconds=3600,
    )

    _run_trend_script(
        summary_files=[nightly_summary],
        latest=latest_path,
        history=history_path,
        dashboard=dashboard_path,
        run_id="200",
        run_attempt="1",
    )
    _run_trend_script(
        summary_files=[nightly_summary],
        latest=latest_path,
        history=history_path,
        dashboard=dashboard_path,
        run_id="200",
        run_attempt="1",
    )
    history_rows = _read_jsonl(history_path)
    assert len(history_rows) == 1

    _run_trend_script(
        summary_files=[nightly_summary],
        latest=latest_path,
        history=history_path,
        dashboard=dashboard_path,
        run_id="200",
        run_attempt="2",
    )
    history_rows = _read_jsonl(history_path)
    assert len(history_rows) == 2


def test_build_ci_runtime_trend_fails_overall_when_gate_status_fails(tmp_path: Path) -> None:
    summary = tmp_path / "failed_gate.txt"
    latest_path = tmp_path / "latest.json"
    history_path = tmp_path / "history.jsonl"
    dashboard_path = tmp_path / "dashboard.md"

    _write_runtime_summary(
        summary,
        gate="release-tag-gate",
        status="fail",
        attempts_used=1,
        retry_budget=0,
        timeout_minutes=210,
        runtime_target_minutes=120,
        elapsed_seconds=600,
    )

    _run_trend_script(
        summary_files=[summary],
        latest=latest_path,
        history=history_path,
        dashboard=dashboard_path,
        run_id="300",
        run_attempt="1",
    )

    payload = json.loads(latest_path.read_text(encoding="utf-8"))
    assert payload["overall"]["status"] == "fail"
    assert payload["overall"]["gate_failures"] == 1
