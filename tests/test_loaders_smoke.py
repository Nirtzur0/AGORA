from __future__ import annotations

import json
from pathlib import Path

from dash_app.data.loaders import (
    load_all_datasets,
    load_artifact_registry,
    load_catalog_rows,
    load_dataset,
    records_to_columns,
)


def test_loaders_smoke__artifact_registry__reads_real_repo():
    payload = load_artifact_registry(".")

    assert payload.dataset_id == "artifact_registry"
    assert payload.path.exists()
    assert payload.records
    assert {"id", "kind", "title", "url", "retrieved_at"}.issubset(payload.records[0].keys())


def test_loaders_smoke__catalog_rows__contains_expected_datasets():
    rows = load_catalog_rows(".")
    dataset_ids = {row["dataset_id"] for row in rows}

    assert "artifact_registry" in dataset_ids
    assert "objective_metrics_latest" in dataset_ids
    assert "observability_snapshot_latest" in dataset_ids


def test_loaders_smoke__records_to_columns__stable_order():
    columns = records_to_columns([
        {"b": 1, "a": 2},
        {"c": 3, "a": 4},
    ])
    assert columns == ["b", "a", "c"]


def test_loaders_smoke__load_all_datasets__fixture_repo(tmp_path: Path):
    (tmp_path / "Docs/artifacts").mkdir(parents=True)
    (tmp_path / "Docs/implementation/reports").mkdir(parents=True)
    (tmp_path / "paper/artifacts").mkdir(parents=True)

    (tmp_path / "Docs/artifacts/index.json").write_text(
        json.dumps(
            {
                "version": 1,
                "artifacts": [
                    {
                        "id": "EXT-TEST-001",
                        "kind": "web_page",
                        "title": "fixture",
                        "url": "https://example.com",
                        "retrieved_at": "2026-02-09T00:00:00+00:00",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "Docs/implementation/reports/objective_metrics_latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-02-09T00:00:00+00:00",
                "metrics": [
                    {
                        "id": "citation_integrity",
                        "status": "pass",
                        "pass_rate": 1.0,
                        "executed_tests": 16,
                        "threshold": 1.0,
                    }
                ],
                "overall": {"status": "pass", "required_metrics": 1, "passed_metrics": 1, "pass_rate": 1.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "Docs/implementation/reports/objective_metrics_history.jsonl").write_text(
        json.dumps(
            {
                "generated_at": "2026-02-09T00:00:00+00:00",
                "metric_pass_rates": {"citation_integrity": 1.0},
                "metric_statuses": {"citation_integrity": "pass"},
                "overall": {"status": "pass", "required_metrics": 1, "passed_metrics": 1, "pass_rate": 1.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "Docs/implementation/reports/observability_snapshot_latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-02-09T00:00:00+00:00",
                "overall_status": "pass",
                "artifact_snapshot": {
                    "status": "pass",
                    "artifacts": 1,
                    "coverage_percent": 100.0,
                    "stale": 0,
                    "missing": 0,
                },
                "objective_snapshot": {
                    "status": "pass",
                    "required_metrics": 1,
                    "passed_metrics": 1,
                    "pass_rate": 1.0,
                    "pass_streak": 1,
                    "metric_ids": ["citation_integrity"],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "paper/artifacts/verification_snapshot.json").write_text(
        json.dumps(
            {
                "citation_sample": {
                    "cites_total": 1,
                    "claims_total": 1,
                    "coverage_failures": [],
                    "coverage_pass": True,
                    "materialization_count": 1,
                },
                "phase_graph": {"edges_total": 1, "states_total": 1, "terminal_phases": ["ARCHIVED"]},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payloads = load_all_datasets(tmp_path)
    assert sorted(payloads.keys()) == [
        "artifact_registry",
        "objective_metrics_history",
        "objective_metrics_latest",
        "observability_snapshot_latest",
        "paper_verification_snapshot",
    ]


def test_loaders_smoke__load_dataset__unknown_dataset_raises():
    try:
        load_dataset("does_not_exist", ".")
        assert False, "Expected KeyError for unknown dataset id"
    except KeyError:
        pass
