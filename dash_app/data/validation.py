from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dash_app.data.catalog import dataset_spec_by_id, dataset_specs
from dash_app.data.loaders import (
    load_all_datasets,
    load_dataset,
    repo_root_path,
)


STATUS_PASS = "pass"
STATUS_FAIL = "fail"


@dataclass(frozen=True)
class ValidationResult:
    dataset_id: str
    rule_id: str
    severity: str
    status: str
    message: str
    metrics: dict[str, Any]
    offending_rows: list[dict[str, Any]]


def _result(
    dataset_id: str,
    rule_id: str,
    severity: str,
    status: str,
    message: str,
    metrics: dict[str, Any] | None = None,
    offending_rows: list[dict[str, Any]] | None = None,
) -> ValidationResult:
    return ValidationResult(
        dataset_id=dataset_id,
        rule_id=rule_id,
        severity=severity,
        status=status,
        message=message,
        metrics=metrics or {},
        offending_rows=offending_rows or [],
    )


def _is_nullish(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _parse_iso(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _check_required_fields(dataset_id: str, records: list[dict[str, Any]]) -> ValidationResult:
    spec = dataset_spec_by_id(dataset_id)
    missing_columns: list[str] = []
    for field in spec.required_fields:
        if not any(field in row for row in records):
            missing_columns.append(field)

    null_violations: list[dict[str, Any]] = []
    for idx, row in enumerate(records):
        for field in spec.required_fields:
            if field in row and _is_nullish(row.get(field)):
                null_violations.append({"row_index": idx, "field": field, "value": row.get(field)})

    if missing_columns or null_violations:
        return _result(
            dataset_id,
            "required_fields",
            "error",
            STATUS_FAIL,
            "Required field check failed.",
            metrics={
                "missing_columns": missing_columns,
                "null_violations": len(null_violations),
            },
            offending_rows=(null_violations[:10]),
        )

    return _result(
        dataset_id,
        "required_fields",
        "error",
        STATUS_PASS,
        "Required fields present with no null violations in required fields.",
        metrics={"rows_checked": len(records)},
    )


def _check_uniqueness(dataset_id: str, records: list[dict[str, Any]]) -> ValidationResult:
    key_field = "id" if dataset_id == "artifact_registry" else "generated_at"
    if dataset_id == "objective_metrics_latest":
        key_field = "id"

    seen: set[Any] = set()
    duplicates: list[dict[str, Any]] = []
    for idx, row in enumerate(records):
        key = row.get(key_field)
        if key in seen:
            duplicates.append({"row_index": idx, "key_field": key_field, "key": key})
        else:
            seen.add(key)

    if duplicates:
        return _result(
            dataset_id,
            "uniqueness",
            "error",
            STATUS_FAIL,
            f"Duplicate values detected for {key_field}.",
            metrics={"duplicate_count": len(duplicates), "key_field": key_field},
            offending_rows=duplicates[:10],
        )

    return _result(
        dataset_id,
        "uniqueness",
        "error",
        STATUS_PASS,
        f"Uniqueness check passed for {key_field}.",
        metrics={"rows_checked": len(records), "key_field": key_field},
    )


def _check_numeric_ranges(dataset_id: str, records: list[dict[str, Any]]) -> ValidationResult:
    violations: list[dict[str, Any]] = []

    for idx, row in enumerate(records):
        for key, value in row.items():
            if value is None:
                continue
            if isinstance(value, (int, float)) and "pass_rate" in key:
                if value < 0 or value > 1:
                    violations.append({"row_index": idx, "field": key, "value": value, "range": "[0,1]"})
            if isinstance(value, (int, float)) and key.endswith("coverage_percent"):
                if value < 0 or value > 100:
                    violations.append({"row_index": idx, "field": key, "value": value, "range": "[0,100]"})
            if isinstance(value, int) and value < 0:
                if key.endswith("_count") or key.endswith("_total") or key.endswith("_metrics") or key.endswith("_streak"):
                    violations.append({"row_index": idx, "field": key, "value": value, "range": "non-negative"})

    if violations:
        return _result(
            dataset_id,
            "numeric_ranges",
            "error",
            STATUS_FAIL,
            "Numeric range check failed.",
            metrics={"violation_count": len(violations)},
            offending_rows=violations[:10],
        )

    return _result(
        dataset_id,
        "numeric_ranges",
        "error",
        STATUS_PASS,
        "Numeric range check passed.",
        metrics={"rows_checked": len(records)},
    )


def _check_enum_values(dataset_id: str, records: list[dict[str, Any]]) -> ValidationResult:
    allowed_by_field = {
        "status": {"pass", "fail", "block", "running", "completed"},
        "overall_status": {"pass", "fail", "warn", "warning"},
        "artifact_status": {"pass", "fail", "warn", "warning"},
        "objective_status": {"pass", "fail", "warn", "warning"},
        "coverage_pass": {True, False},
        "kind": {"web_page", "paper"},
    }

    violations: list[dict[str, Any]] = []
    for idx, row in enumerate(records):
        for field, allowed in allowed_by_field.items():
            if field not in row:
                continue
            value = row.get(field)
            if value is None:
                continue
            if value not in allowed:
                violations.append(
                    {
                        "row_index": idx,
                        "field": field,
                        "value": value,
                        "allowed": sorted(str(item) for item in allowed),
                    }
                )

    if violations:
        return _result(
            dataset_id,
            "enum_values",
            "warn",
            STATUS_FAIL,
            "Enum-domain check failed.",
            metrics={"violation_count": len(violations)},
            offending_rows=violations[:10],
        )

    return _result(
        dataset_id,
        "enum_values",
        "warn",
        STATUS_PASS,
        "Enum-domain check passed.",
        metrics={"rows_checked": len(records)},
    )


def _check_freshness(dataset_id: str, metadata: dict[str, Any], max_age_hours: float = 72.0) -> ValidationResult:
    generated_at = metadata.get("generated_at")
    if not generated_at:
        return _result(
            dataset_id,
            "freshness",
            "warn",
            STATUS_FAIL,
            "Freshness timestamp is missing.",
            metrics={"max_age_hours": max_age_hours},
        )

    age_hours = (datetime.now(timezone.utc) - _parse_iso(generated_at)).total_seconds() / 3600.0
    if age_hours > max_age_hours:
        return _result(
            dataset_id,
            "freshness",
            "warn",
            STATUS_FAIL,
            "Dataset freshness is outside the expected window.",
            metrics={"age_hours": round(age_hours, 2), "max_age_hours": max_age_hours},
        )

    return _result(
        dataset_id,
        "freshness",
        "warn",
        STATUS_PASS,
        "Dataset freshness is within expected bounds.",
        metrics={"age_hours": round(age_hours, 2), "max_age_hours": max_age_hours},
    )


def _check_referential_integrity(payloads: dict[str, Any]) -> ValidationResult:
    objective = payloads.get("objective_metrics_latest")
    observability = payloads.get("observability_snapshot_latest")

    if not objective or not observability:
        return _result(
            "cross_dataset",
            "referential_integrity",
            "error",
            STATUS_FAIL,
            "Required datasets are missing for referential integrity checks.",
            metrics={
                "objective_metrics_latest_present": bool(objective),
                "observability_snapshot_latest_present": bool(observability),
            },
        )

    metric_ids = {row.get("id") for row in objective.records if row.get("id")}
    observability_metric_ids = {
        item.strip()
        for item in (observability.records[0].get("metric_ids") or "").split(",")
        if item.strip()
    }

    missing = sorted(observability_metric_ids - metric_ids)
    if missing:
        return _result(
            "cross_dataset",
            "referential_integrity",
            "error",
            STATUS_FAIL,
            "Observability snapshot references missing objective metric IDs.",
            metrics={"missing_metric_ids": missing},
            offending_rows=[{"metric_id": value} for value in missing],
        )

    return _result(
        "cross_dataset",
        "referential_integrity",
        "error",
        STATUS_PASS,
        "Cross-dataset metric ID references are consistent.",
        metrics={"metric_ids_checked": len(observability_metric_ids)},
    )


def _check_completeness(root: Path, payloads: dict[str, Any]) -> ValidationResult:
    missing_paths: list[str] = []
    for spec in dataset_specs():
        path = root / spec.path
        if not path.exists():
            missing_paths.append(spec.path)

    if missing_paths:
        return _result(
            "cross_dataset",
            "completeness",
            "error",
            STATUS_FAIL,
            "One or more required dataset artifacts are missing.",
            metrics={"missing_paths": missing_paths},
            offending_rows=[{"path": path} for path in missing_paths],
        )

    return _result(
        "cross_dataset",
        "completeness",
        "error",
        STATUS_PASS,
        "All required dataset artifacts are present.",
        metrics={"datasets_checked": len(list(dataset_specs()))},
    )


def run_validation(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = repo_root_path(repo_root)
    payloads = load_all_datasets(root)

    results: list[ValidationResult] = []

    for dataset_id, payload in payloads.items():
        if payload.records:
            results.append(_check_required_fields(dataset_id, payload.records))
            results.append(_check_uniqueness(dataset_id, payload.records))
            results.append(_check_numeric_ranges(dataset_id, payload.records))
            results.append(_check_enum_values(dataset_id, payload.records))

        if dataset_id in {"objective_metrics_latest", "observability_snapshot_latest"}:
            results.append(_check_freshness(dataset_id, payload.metadata))

    results.append(_check_referential_integrity(payloads))
    results.append(_check_completeness(root, payloads))

    total = len(results)
    failed = sum(1 for result in results if result.status == STATUS_FAIL)
    passed = total - failed
    overall_status = STATUS_PASS if failed == 0 else STATUS_FAIL

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(root),
        "overall_status": overall_status,
        "summary": {
            "total_rules": total,
            "passed_rules": passed,
            "failed_rules": failed,
        },
        "results": [asdict(result) for result in results],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Dash data quality validation checks.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    args = parser.parse_args()

    report = run_validation(args.repo_root)

    output = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output + "\n", encoding="utf-8")
        print(f"Wrote validation report: {output_path}")
    else:
        print(output)

    return 0 if report["overall_status"] == STATUS_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
