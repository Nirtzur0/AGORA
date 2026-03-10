#!/usr/bin/env python3
"""Validate periodic sink-evidence recency across key CI gate classes.

The check queries GitHub Actions workflow history and validates that the latest
successful sink-evidence artifacts for objective, nightly, and release gates
remain within standing recency thresholds.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GatePolicy:
    key: str
    job_name: str
    threshold_days: int
    required_artifact: str


POLICIES: tuple[GatePolicy, ...] = (
    GatePolicy(
        key="objective-metrics-gate",
        job_name="Objective metrics gate",
        threshold_days=14,
        required_artifact="observability-snapshot-report",
    ),
    GatePolicy(
        key="cmd-13-nightly-full-suite",
        job_name="CMD-13 nightly full-suite gate",
        threshold_days=7,
        required_artifact="cmd-13-nightly-runtime-trend",
    ),
    GatePolicy(
        key="release-tag-gate",
        job_name="Release tag gate (v* fail-closed)",
        threshold_days=30,
        required_artifact="release-tag-gate-artifacts",
    ),
)


def _parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def _now_utc(override: str) -> datetime:
    if override:
        return _parse_iso8601(override)
    return datetime.now(timezone.utc)


def _api_get_json(*, api_base_url: str, path: str, token: str, timeout_seconds: int) -> dict[str, Any]:
    url = f"{api_base_url.rstrip('/')}{path}"
    request = urllib.request.Request(
        url=url,
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "agora-sink-evidence-recency/1.0",
        },
    )
    if token:
        request.add_header("Authorization", f"Bearer {token}")

    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"unexpected API payload type from {url}")
    return payload


def _list_completed_runs(
    *,
    api_base_url: str,
    repo: str,
    workflow_file: str,
    token: str,
    max_runs: int,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    workflow_token = urllib.parse.quote(workflow_file, safe="")
    path = (
        f"/repos/{repo}/actions/workflows/{workflow_token}/runs"
        f"?status=completed&per_page={max(1, min(max_runs, 100))}"
    )
    payload = _api_get_json(
        api_base_url=api_base_url,
        path=path,
        token=token,
        timeout_seconds=timeout_seconds,
    )
    rows = payload.get("workflow_runs")
    if not isinstance(rows, list):
        raise ValueError("workflow_runs payload missing list")
    filtered: list[dict[str, Any]] = []
    for run in rows:
        if not isinstance(run, dict):
            continue
        if str(run.get("conclusion", "")).strip().lower() != "success":
            continue
        filtered.append(run)
    return filtered


def _list_run_jobs(
    *,
    api_base_url: str,
    repo: str,
    run_id: int,
    token: str,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    path = f"/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100"
    payload = _api_get_json(
        api_base_url=api_base_url,
        path=path,
        token=token,
        timeout_seconds=timeout_seconds,
    )
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return []
    return [job for job in jobs if isinstance(job, dict)]


def _list_run_artifacts(
    *,
    api_base_url: str,
    repo: str,
    run_id: int,
    token: str,
    timeout_seconds: int,
) -> set[str]:
    path = f"/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100"
    payload = _api_get_json(
        api_base_url=api_base_url,
        path=path,
        token=token,
        timeout_seconds=timeout_seconds,
    )
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        return set()

    names: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        if bool(artifact.get("expired", False)):
            continue
        name = str(artifact.get("name", "")).strip()
        if name:
            names.add(name)
    return names


def _compute_age_days(*, now: datetime, observed_at: datetime) -> int:
    age_seconds = max((now - observed_at).total_seconds(), 0.0)
    return int(age_seconds // 86400)


def _find_latest_evidence(
    *,
    policy: GatePolicy,
    repo: str,
    runs: list[dict[str, Any]],
    jobs_by_run: dict[int, list[dict[str, Any]]],
    artifacts_by_run: dict[int, set[str]],
) -> dict[str, Any] | None:
    for run in runs:
        run_id_raw = run.get("id")
        try:
            run_id = int(run_id_raw)
        except Exception:
            continue

        jobs = jobs_by_run.get(run_id, [])
        matched_job = None
        for job in jobs:
            job_name = str(job.get("name", "")).strip()
            job_conclusion = str(job.get("conclusion", "")).strip().lower()
            if job_name == policy.job_name and job_conclusion == "success":
                matched_job = job
                break
        if matched_job is None:
            continue

        artifacts = artifacts_by_run.get(run_id, set())
        if policy.required_artifact not in artifacts:
            continue

        observed_at = str(run.get("updated_at") or run.get("created_at") or "").strip()
        if not observed_at:
            continue

        run_url = str(run.get("html_url") or "").strip()
        if not run_url or "/actions/runs/" not in run_url:
            run_url = f"https://github.com/{repo}/actions/runs/{run_id}"

        return {
            "run_id": str(run_id),
            "run_url": run_url,
            "observed_at": observed_at,
            "job_name": policy.job_name,
            "artifact_name": policy.required_artifact,
        }
    return None


def _write_summary_markdown(report: dict[str, Any], output_path: Path) -> None:
    lines = [
        "## Sink Evidence Recency",
        "",
        f"- Status: `{report.get('overall_status')}`",
        f"- Repository: `{report.get('repo')}`",
        f"- Workflow file: `{report.get('workflow_file')}`",
        f"- Checked at: `{report.get('checked_at')}`",
        f"- Missing checks: `{report.get('missing_checks')}`",
        f"- Stale checks: `{report.get('stale_checks')}`",
        "",
        "| Gate | Status | Age (days) | Threshold (days) | Run ID | Artifact | Observed at |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for row in report.get("checks", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            f"`{row.get('gate', 'unknown')}` | "
            f"`{row.get('status', 'unknown')}` | "
            f"{row.get('age_days', 'n/a')} | "
            f"{row.get('threshold_days', 'n/a')} | "
            f"`{row.get('run_id', 'n/a')}` | "
            f"`{row.get('artifact_name', 'n/a')}` | "
            f"`{row.get('observed_at', 'n/a')}` |"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate periodic sink-evidence recency from GitHub Actions history.")
    parser.add_argument(
        "--repo",
        default="",
        help="GitHub repository slug (owner/repo). Defaults to GITHUB_REPOSITORY.",
    )
    parser.add_argument(
        "--workflow-file",
        default="ci.yml",
        help="Workflow filename under .github/workflows/.",
    )
    parser.add_argument(
        "--api-base-url",
        default="https://api.github.com",
        help="GitHub API base URL (override for testing).",
    )
    parser.add_argument(
        "--token",
        default="",
        help="GitHub API token (defaults to GITHUB_TOKEN env).",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=80,
        help="Maximum completed workflow runs to scan (max 100 per API request).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=20,
        help="HTTP timeout for API requests.",
    )
    parser.add_argument(
        "--now",
        default="",
        help="Override current UTC timestamp (ISO-8601) for deterministic tests.",
    )
    parser.add_argument(
        "--allow-current-release-candidate",
        type=_parse_bool,
        default=False,
        help="Allow in-flight release candidate run to satisfy release-tag recency policy.",
    )
    parser.add_argument(
        "--current-run-id",
        default="",
        help="Current run ID (used when --allow-current-release-candidate=true).",
    )
    parser.add_argument(
        "--report",
        default="/tmp/sink-evidence-recency-report.json",
        help="Output JSON report path.",
    )
    parser.add_argument(
        "--summary-markdown",
        default="/tmp/sink-evidence-recency-summary.md",
        help="Output markdown summary path.",
    )
    args = parser.parse_args()

    repo = args.repo.strip() or str(os.environ.get("GITHUB_REPOSITORY", "")).strip()
    if not repo:
        raise SystemExit("missing repository slug: pass --repo or set GITHUB_REPOSITORY")

    token = args.token.strip() or str(os.environ.get("GITHUB_TOKEN", "")).strip()
    now = _now_utc(args.now.strip())

    try:
        runs = _list_completed_runs(
            api_base_url=args.api_base_url,
            repo=repo,
            workflow_file=args.workflow_file,
            token=token,
            max_runs=args.max_runs,
            timeout_seconds=max(args.timeout_seconds, 1),
        )

        jobs_by_run: dict[int, list[dict[str, Any]]] = {}
        artifacts_by_run: dict[int, set[str]] = {}
        for run in runs:
            try:
                run_id = int(run.get("id"))
            except Exception:
                continue
            jobs_by_run[run_id] = _list_run_jobs(
                api_base_url=args.api_base_url,
                repo=repo,
                run_id=run_id,
                token=token,
                timeout_seconds=max(args.timeout_seconds, 1),
            )
            artifacts_by_run[run_id] = _list_run_artifacts(
                api_base_url=args.api_base_url,
                repo=repo,
                run_id=run_id,
                token=token,
                timeout_seconds=max(args.timeout_seconds, 1),
            )

        checks: list[dict[str, Any]] = []
        stale_checks = 0
        missing_checks = 0

        for policy in POLICIES:
            evidence = _find_latest_evidence(
                policy=policy,
                repo=repo,
                runs=runs,
                jobs_by_run=jobs_by_run,
                artifacts_by_run=artifacts_by_run,
            )

            if evidence is None:
                status = "missing"
                age_days = "n/a"
                observed_at = ""
                run_id = ""
                run_url = ""
                artifact_name = policy.required_artifact
                missing_checks += 1
            else:
                observed_at = str(evidence.get("observed_at", "")).strip()
                observed_dt = _parse_iso8601(observed_at)
                computed_age = _compute_age_days(now=now, observed_at=observed_dt)
                status = "pass" if computed_age <= policy.threshold_days else "stale"
                age_days = computed_age
                run_id = str(evidence.get("run_id", ""))
                run_url = str(evidence.get("run_url", ""))
                artifact_name = str(evidence.get("artifact_name", policy.required_artifact))
                if status == "stale":
                    stale_checks += 1

            if (
                policy.key == "release-tag-gate"
                and status in {"missing", "stale"}
                and args.allow_current_release_candidate
            ):
                if status == "missing":
                    missing_checks = max(missing_checks - 1, 0)
                if status == "stale":
                    stale_checks = max(stale_checks - 1, 0)
                status = "pass_candidate_run"
                age_days = 0
                run_id = args.current_run_id.strip() or run_id or "current-run"
                run_url = f"https://github.com/{repo}/actions/runs/{run_id}" if run_id else ""
                observed_at = now.isoformat()
                artifact_name = policy.required_artifact

            checks.append(
                {
                    "gate": policy.key,
                    "status": status,
                    "age_days": age_days,
                    "threshold_days": policy.threshold_days,
                    "run_id": run_id,
                    "run_url": run_url,
                    "observed_at": observed_at,
                    "artifact_name": artifact_name,
                }
            )

        failing_checks = stale_checks + missing_checks
        overall_status = "pass" if failing_checks == 0 else "fail"

        report = {
            "checked_at": now.isoformat(),
            "repo": repo,
            "workflow_file": args.workflow_file,
            "overall_status": overall_status,
            "failing_checks": failing_checks,
            "stale_checks": stale_checks,
            "missing_checks": missing_checks,
            "checks": checks,
        }
    except Exception as exc:
        report = {
            "checked_at": now.isoformat(),
            "repo": repo,
            "workflow_file": args.workflow_file,
            "overall_status": "error",
            "failing_checks": len(POLICIES),
            "stale_checks": 0,
            "missing_checks": len(POLICIES),
            "checks": [],
            "error": f"{type(exc).__name__}: {exc}",
        }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_summary_markdown(report, Path(args.summary_markdown))

    overall_status = str(report.get("overall_status", "error"))
    stale_checks = int(report.get("stale_checks", 0))
    missing_checks = int(report.get("missing_checks", 0))
    checks = report.get("checks", [])
    if not isinstance(checks, list):
        checks = []

    print(
        "sink_evidence_recency_summary "
        f"status={overall_status} "
        f"checks={len(checks)} "
        f"stale={stale_checks} "
        f"missing={missing_checks}"
    )
    for row in checks:
        if not isinstance(row, dict):
            continue
        print(
            "sink_evidence_recency_check "
            f"gate={row['gate']} "
            f"status={row['status']} "
            f"age_days={row['age_days']} "
            f"threshold_days={row['threshold_days']} "
            f"run_id={row['run_id'] or 'n/a'} "
            f"artifact={row['artifact_name']} "
            f"observed_at={row['observed_at'] or 'n/a'}"
        )
    if report.get("error"):
        print(f"sink_evidence_recency_error detail={report['error']}")

    if overall_status != "pass":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
