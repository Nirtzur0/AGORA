from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dash_app.data.catalog import dataset_specs, dataset_spec_by_id, spec_to_row


@dataclass(frozen=True)
class DatasetPayload:
    dataset_id: str
    path: Path
    records: list[dict[str, Any]]
    metadata: dict[str, Any]


def repo_root_path(repo_root: str | Path | None = None) -> Path:
    if repo_root is not None:
        return Path(repo_root).resolve()
    return Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _iso_to_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_days(timestamp: str) -> float:
    ts = _iso_to_utc(timestamp)
    delta = datetime.now(timezone.utc) - ts
    return max(delta.total_seconds() / 86400.0, 0.0)


def load_artifact_registry(repo_root: str | Path | None = None) -> DatasetPayload:
    root = repo_root_path(repo_root)
    path = root / "Docs/artifacts/index.json"
    payload = _read_json(path)

    artifacts = payload.get("artifacts", [])
    records: list[dict[str, Any]] = []
    for artifact in artifacts:
        row = {
            "id": artifact.get("id"),
            "kind": artifact.get("kind"),
            "title": artifact.get("title"),
            "url": artifact.get("url"),
            "retrieved_at": artifact.get("retrieved_at"),
            "tags": ", ".join(artifact.get("tags", [])),
            "notes": artifact.get("notes", ""),
        }
        retrieved_at = row["retrieved_at"]
        if isinstance(retrieved_at, str) and retrieved_at:
            row["age_days"] = round(_age_days(retrieved_at), 2)
        else:
            row["age_days"] = None
        records.append(row)

    return DatasetPayload(
        dataset_id="artifact_registry",
        path=path,
        records=records,
        metadata={"version": payload.get("version")},
    )


def load_objective_metrics_latest(repo_root: str | Path | None = None) -> DatasetPayload:
    root = repo_root_path(repo_root)
    path = root / "Docs/implementation/reports/objective_metrics_latest.json"
    payload = _read_json(path)

    records: list[dict[str, Any]] = []
    for metric in payload.get("metrics", []):
        records.append(
            {
                "id": metric.get("id"),
                "description": metric.get("description"),
                "status": metric.get("status"),
                "pass_rate": metric.get("pass_rate"),
                "executed_tests": metric.get("executed_tests"),
                "threshold": metric.get("threshold"),
                "duration_seconds": metric.get("duration_seconds"),
                "trend": metric.get("trend"),
                "summary_line": metric.get("summary_line"),
                "command": metric.get("command"),
            }
        )

    return DatasetPayload(
        dataset_id="objective_metrics_latest",
        path=path,
        records=records,
        metadata={
            "generated_at": payload.get("generated_at"),
            "overall": payload.get("overall", {}),
            "objective": payload.get("objective"),
        },
    )


def load_objective_metrics_history(repo_root: str | Path | None = None) -> DatasetPayload:
    root = repo_root_path(repo_root)
    path = root / "Docs/implementation/reports/objective_metrics_history.jsonl"
    rows = _read_jsonl(path)

    records: list[dict[str, Any]] = []
    for row in rows:
        overall = row.get("overall", {})
        records.append(
            {
                "generated_at": row.get("generated_at"),
                "overall_status": overall.get("status"),
                "overall_pass_rate": overall.get("pass_rate"),
                "required_metrics": overall.get("required_metrics"),
                "passed_metrics": overall.get("passed_metrics"),
                "metric_statuses": json.dumps(row.get("metric_statuses", {}), sort_keys=True),
                "metric_pass_rates": json.dumps(row.get("metric_pass_rates", {}), sort_keys=True),
            }
        )

    return DatasetPayload(
        dataset_id="objective_metrics_history",
        path=path,
        records=records,
        metadata={"rows": len(records)},
    )


def load_observability_snapshot_latest(repo_root: str | Path | None = None) -> DatasetPayload:
    root = repo_root_path(repo_root)
    path = root / "Docs/implementation/reports/observability_snapshot_latest.json"
    payload = _read_json(path)

    artifact_snapshot = payload.get("artifact_snapshot", {})
    objective_snapshot = payload.get("objective_snapshot", {})
    records = [
        {
            "generated_at": payload.get("generated_at"),
            "overall_status": payload.get("overall_status"),
            "artifact_status": artifact_snapshot.get("status"),
            "artifact_count": artifact_snapshot.get("artifacts"),
            "artifact_coverage_percent": artifact_snapshot.get("coverage_percent"),
            "artifact_stale": artifact_snapshot.get("stale"),
            "artifact_missing": artifact_snapshot.get("missing"),
            "objective_status": objective_snapshot.get("status"),
            "objective_required_metrics": objective_snapshot.get("required_metrics"),
            "objective_passed_metrics": objective_snapshot.get("passed_metrics"),
            "objective_pass_rate": objective_snapshot.get("pass_rate"),
            "objective_pass_streak": objective_snapshot.get("pass_streak"),
            "metric_ids": ", ".join(objective_snapshot.get("metric_ids", [])),
        }
    ]

    return DatasetPayload(
        dataset_id="observability_snapshot_latest",
        path=path,
        records=records,
        metadata={
            "generated_at": payload.get("generated_at"),
            "artifact_snapshot": artifact_snapshot,
            "objective_snapshot": objective_snapshot,
        },
    )


def load_paper_verification_snapshot(repo_root: str | Path | None = None) -> DatasetPayload:
    root = repo_root_path(repo_root)
    path = root / "paper/artifacts/verification_snapshot.json"
    payload = _read_json(path)

    citation = payload.get("citation_sample", {})
    phase = payload.get("phase_graph", {})
    records = [
        {
            "cites_total": citation.get("cites_total"),
            "claims_total": citation.get("claims_total"),
            "coverage_pass": citation.get("coverage_pass"),
            "materialization_count": citation.get("materialization_count"),
            "edges_total": phase.get("edges_total"),
            "states_total": phase.get("states_total"),
            "terminal_phases": ", ".join(phase.get("terminal_phases", [])),
        }
    ]

    return DatasetPayload(
        dataset_id="paper_verification_snapshot",
        path=path,
        records=records,
        metadata=payload,
    )


def load_catalog_rows(repo_root: str | Path | None = None) -> list[dict[str, Any]]:
    root = repo_root_path(repo_root)
    rows: list[dict[str, Any]] = []
    for spec in dataset_specs():
        rows.append(spec_to_row(spec, exists=(root / spec.path).exists()))
    return rows


def load_dataset(dataset_id: str, repo_root: str | Path | None = None) -> DatasetPayload:
    loaders = {
        "artifact_registry": load_artifact_registry,
        "objective_metrics_latest": load_objective_metrics_latest,
        "objective_metrics_history": load_objective_metrics_history,
        "observability_snapshot_latest": load_observability_snapshot_latest,
        "paper_verification_snapshot": load_paper_verification_snapshot,
    }
    if dataset_id not in loaders:
        raise KeyError(f"Unknown dataset_id: {dataset_id}")
    return loaders[dataset_id](repo_root)


def load_all_datasets(repo_root: str | Path | None = None) -> dict[str, DatasetPayload]:
    root = repo_root_path(repo_root)
    payloads: dict[str, DatasetPayload] = {}
    for spec in dataset_specs():
        path = root / spec.path
        if not path.exists():
            continue
        payloads[spec.dataset_id] = load_dataset(spec.dataset_id, root)
    return payloads


def records_to_columns(records: Iterable[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for row in records:
        for key in row:
            if key not in seen:
                seen.add(key)
                ordered.append(key)
    return ordered
