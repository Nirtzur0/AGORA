from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    name: str
    description: str
    path: str
    produced_by: str
    grain: str
    primary_key: str
    time_semantics: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    expected_ranges: dict[str, str]
    freshness_expectation: str
    pii_notes: str
    quality_owner: str


DATASET_SPECS: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        dataset_id="artifact_registry",
        name="External Artifact Registry",
        description="Curated external sources and literature references used by AGORA.",
        path="Docs/artifacts/index.json",
        produced_by="Manual curation + prompt packet updates",
        grain="One row per external artifact",
        primary_key="artifacts.id",
        time_semantics="retrieved_at timestamp (UTC)",
        required_fields=("id", "kind", "title", "url", "retrieved_at"),
        optional_fields=("notes", "tags", "source"),
        expected_ranges={
            "kind": "non-empty string (commonly web_page or paper)",
            "retrieved_at": "ISO-8601 timestamp",
        },
        freshness_expectation="No artifact older than 90 days for operational references.",
        pii_notes="No PII expected.",
        quality_owner="Docs/implementation + maintainers",
    ),
    DatasetSpec(
        dataset_id="objective_metrics_latest",
        name="Objective Metrics (Latest)",
        description="Latest automated objective metrics report for citation and authority regression suites.",
        path="Docs/implementation/reports/objective_metrics_latest.json",
        produced_by="scripts/check_objective_metrics.py (CMD-29)",
        grain="One row per objective metric",
        primary_key="metrics.id",
        time_semantics="generated_at timestamp (UTC)",
        required_fields=("id", "status", "pass_rate", "executed_tests", "threshold"),
        optional_fields=("summary_line", "failure_excerpt", "duration_seconds", "trend"),
        expected_ranges={
            "pass_rate": "[0, 1]",
            "executed_tests": "non-negative integer",
            "status": "pass|fail",
        },
        freshness_expectation="Generated in the current release-validation window (<=72h).",
        pii_notes="No PII expected.",
        quality_owner="Reliability/test maintainers",
    ),
    DatasetSpec(
        dataset_id="objective_metrics_history",
        name="Objective Metrics History",
        description="Append-only JSONL history of objective metric runs.",
        path="Docs/implementation/reports/objective_metrics_history.jsonl",
        produced_by="scripts/check_objective_metrics.py (CMD-29)",
        grain="One row per objective-metrics run",
        primary_key="generated_at",
        time_semantics="generated_at timestamp (UTC)",
        required_fields=("generated_at", "metric_pass_rates", "metric_statuses", "overall_pass_rate"),
        optional_fields=("required_metrics", "passed_metrics"),
        expected_ranges={
            "overall.pass_rate": "[0, 1]",
            "overall.passed_metrics": "non-negative integer",
        },
        freshness_expectation="History should include at least one recent run (<=72h).",
        pii_notes="No PII expected.",
        quality_owner="Reliability/test maintainers",
    ),
    DatasetSpec(
        dataset_id="observability_snapshot_latest",
        name="Observability Snapshot (Latest)",
        description="Consolidated freshness/provenance + objective signal snapshot.",
        path="Docs/implementation/reports/observability_snapshot_latest.json",
        produced_by="scripts/check_observability_snapshot.py (CMD-32)",
        grain="Single snapshot row",
        primary_key="generated_at",
        time_semantics="generated_at timestamp (UTC)",
        required_fields=(
            "generated_at",
            "overall_status",
            "artifact_status",
            "artifact_coverage_percent",
            "objective_status",
            "objective_pass_rate",
        ),
        optional_fields=("artifact_count", "objective_required_metrics", "objective_passed_metrics", "metric_ids"),
        expected_ranges={
            "artifact_snapshot.coverage_percent": "[0, 100]",
            "objective_snapshot.pass_rate": "[0, 1]",
        },
        freshness_expectation="Generated in the current release-validation window (<=72h).",
        pii_notes="No PII expected.",
        quality_owner="Observability maintainers",
    ),
    DatasetSpec(
        dataset_id="paper_verification_snapshot",
        name="Paper Verification Snapshot",
        description="Deterministic summary of paper/code verification checks.",
        path="paper/artifacts/verification_snapshot.json",
        produced_by="scripts/generate_paper_verification_snapshot.py (CMD-34)",
        grain="Single verification snapshot",
        primary_key="paper/artifacts/verification_snapshot.json",
        time_semantics="Generated on-demand; no internal timestamp field.",
        required_fields=(
            "cites_total",
            "claims_total",
            "coverage_pass",
            "materialization_count",
            "edges_total",
            "states_total",
        ),
        optional_fields=("terminal_phases",),
        expected_ranges={
            "citation_sample.cites_total": "non-negative integer",
            "citation_sample.claims_total": "non-negative integer",
            "phase_graph.edges_total": "non-negative integer",
        },
        freshness_expectation="Regenerated whenever paper artifacts are updated.",
        pii_notes="No PII expected.",
        quality_owner="Paper verification maintainers",
    ),
)


def dataset_specs() -> list[DatasetSpec]:
    return list(DATASET_SPECS)


def dataset_spec_by_id(dataset_id: str) -> DatasetSpec:
    for spec in DATASET_SPECS:
        if spec.dataset_id == dataset_id:
            return spec
    raise KeyError(f"Unknown dataset_id: {dataset_id}")


def dataset_exists(repo_root: Path, dataset_id: str) -> bool:
    spec = dataset_spec_by_id(dataset_id)
    return (repo_root / spec.path).exists()


def spec_to_row(spec: DatasetSpec, *, exists: bool) -> dict[str, Any]:
    return {
        "dataset_id": spec.dataset_id,
        "name": spec.name,
        "path": spec.path,
        "exists": exists,
        "produced_by": spec.produced_by,
        "grain": spec.grain,
        "primary_key": spec.primary_key,
        "time_semantics": spec.time_semantics,
        "required_fields": ", ".join(spec.required_fields),
        "optional_fields": ", ".join(spec.optional_fields),
        "freshness_expectation": spec.freshness_expectation,
        "pii_notes": spec.pii_notes,
        "quality_owner": spec.quality_owner,
    }
