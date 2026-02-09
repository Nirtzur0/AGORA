from __future__ import annotations

import json
from pathlib import Path

from dash_app.data.validation import run_validation


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _build_fixture_repo(root: Path) -> None:
    _write_json(
        root / "Docs/artifacts/index.json",
        {
            "version": 1,
            "artifacts": [
                {
                    "id": "EXT-TEST-001",
                    "kind": "web_page",
                    "title": "Test Artifact",
                    "url": "https://example.com",
                    "retrieved_at": "2026-02-09T00:00:00+00:00",
                    "tags": ["test"],
                }
            ],
        },
    )

    _write_json(
        root / "Docs/implementation/reports/objective_metrics_latest.json",
        {
            "generated_at": "2026-02-09T00:00:00+00:00",
            "objective": "Docs/manifest/00_overview.md#Core Objective",
            "metrics": [
                {
                    "id": "citation_integrity",
                    "status": "pass",
                    "pass_rate": 1.0,
                    "executed_tests": 10,
                    "threshold": 1.0,
                }
            ],
            "overall": {"status": "pass", "required_metrics": 1, "passed_metrics": 1, "pass_rate": 1.0},
        },
    )

    _write_jsonl(
        root / "Docs/implementation/reports/objective_metrics_history.jsonl",
        [
            {
                "generated_at": "2026-02-09T00:00:00+00:00",
                "metric_pass_rates": {"citation_integrity": 1.0},
                "metric_statuses": {"citation_integrity": "pass"},
                "overall": {"status": "pass", "required_metrics": 1, "passed_metrics": 1, "pass_rate": 1.0},
            }
        ],
    )

    _write_json(
        root / "Docs/implementation/reports/observability_snapshot_latest.json",
        {
            "generated_at": "2026-02-09T00:00:00+00:00",
            "overall_status": "pass",
            "artifact_snapshot": {
                "status": "pass",
                "artifacts": 1,
                "coverage_percent": 100.0,
                "stale": 0,
                "missing": 0,
                "invalid_timestamps": 0,
            },
            "objective_snapshot": {
                "status": "pass",
                "required_metrics": 1,
                "passed_metrics": 1,
                "pass_rate": 1.0,
                "pass_streak": 1,
                "metric_ids": ["citation_integrity"],
            },
        },
    )

    _write_json(
        root / "paper/artifacts/verification_snapshot.json",
        {
            "citation_sample": {
                "cites_total": 1,
                "claims_total": 1,
                "coverage_failures": [],
                "coverage_pass": True,
                "materialization_count": 1,
            },
            "phase_graph": {"edges_total": 1, "states_total": 1, "terminal_phases": ["ARCHIVED"]},
        },
    )


def _find_result(report: dict, dataset_id: str, rule_id: str) -> dict:
    for result in report["results"]:
        if result["dataset_id"] == dataset_id and result["rule_id"] == rule_id:
            return result
    raise AssertionError(f"Missing result: {dataset_id}/{rule_id}")


def test_data_validation__happy_path__passes(tmp_path: Path):
    _build_fixture_repo(tmp_path)
    report = run_validation(tmp_path)

    assert report["overall_status"] == "pass"
    assert report["summary"]["failed_rules"] == 0


def test_data_validation__missing_required_field__fails(tmp_path: Path):
    _build_fixture_repo(tmp_path)

    payload = json.loads((tmp_path / "Docs/artifacts/index.json").read_text(encoding="utf-8"))
    payload["artifacts"][0].pop("id")
    _write_json(tmp_path / "Docs/artifacts/index.json", payload)

    report = run_validation(tmp_path)
    result = _find_result(report, "artifact_registry", "required_fields")

    assert result["status"] == "fail"
    assert result["metrics"]["null_violations"] >= 1


def test_data_validation__range_violation__fails(tmp_path: Path):
    _build_fixture_repo(tmp_path)

    payload = json.loads(
        (tmp_path / "Docs/implementation/reports/objective_metrics_latest.json").read_text(encoding="utf-8")
    )
    payload["metrics"][0]["pass_rate"] = 1.5
    _write_json(tmp_path / "Docs/implementation/reports/objective_metrics_latest.json", payload)

    report = run_validation(tmp_path)
    result = _find_result(report, "objective_metrics_latest", "numeric_ranges")

    assert result["status"] == "fail"
    assert result["metrics"]["violation_count"] >= 1


def test_data_validation__referential_integrity__fails_on_unknown_metric(tmp_path: Path):
    _build_fixture_repo(tmp_path)

    payload = json.loads(
        (tmp_path / "Docs/implementation/reports/observability_snapshot_latest.json").read_text(encoding="utf-8")
    )
    payload["objective_snapshot"]["metric_ids"] = ["unknown_metric"]
    _write_json(tmp_path / "Docs/implementation/reports/observability_snapshot_latest.json", payload)

    report = run_validation(tmp_path)
    result = _find_result(report, "cross_dataset", "referential_integrity")

    assert result["status"] == "fail"
    assert result["metrics"]["missing_metric_ids"] == ["unknown_metric"]


def test_data_validation__golden_summary_snapshot(tmp_path: Path):
    _build_fixture_repo(tmp_path)

    report = run_validation(tmp_path)
    snapshot = {
        "overall_status": report["overall_status"],
        "summary": report["summary"],
        "rule_ids": sorted({result["rule_id"] for result in report["results"]}),
    }

    assert snapshot == {
        "overall_status": "pass",
        "summary": {"total_rules": 24, "passed_rules": 24, "failed_rules": 0},
        "rule_ids": [
            "completeness",
            "enum_values",
            "freshness",
            "numeric_ranges",
            "referential_integrity",
            "required_fields",
            "uniqueness",
        ],
    }
