# Dash Data Explorer Data Catalog

Date: 2026-02-09
Prompt packet: `prompt-08-dash-data-explorer`
Objective anchor: `Docs/manifest/00_overview.md#Core Objective`

## Dataset Inventory Matrix

| Dataset | Path | Source of truth / producer | Grain / primary key | Time semantics | Required fields | Optional fields | Expected ranges / constraints | Typical size + freshness | PII / security notes |
|---|---|---|---|---|---|---|---|---|---|
| Artifact registry | `Docs/artifacts/index.json` | Manual curation + prompt packet updates | 1 row per artifact / `artifacts.id` | `retrieved_at` (UTC ISO timestamp) | `id`, `kind`, `title`, `url`, `retrieved_at` | `notes`, `tags`, `source` | `id` unique; `retrieved_at` parseable ISO timestamp; `kind` non-empty | ~10-100 rows; keep operational refs <=90 days old | No PII expected |
| Objective metrics (latest) | `Docs/implementation/reports/objective_metrics_latest.json` | `scripts/check_objective_metrics.py` (`CMD-29`) | 1 row per metric / `metrics.id` | top-level `generated_at` (UTC ISO timestamp) | `id`, `status`, `pass_rate`, `executed_tests`, `threshold` | `summary_line`, `duration_seconds`, `trend` | `pass_rate` in `[0,1]`; `executed_tests` non-negative; `status` in `pass|fail` | 2+ rows; should be regenerated in active release window (<=72h) | No PII expected |
| Objective metrics history | `Docs/implementation/reports/objective_metrics_history.jsonl` | `scripts/check_objective_metrics.py` (`CMD-29`) | 1 row per run / `generated_at` | per-row `generated_at` (UTC ISO timestamp) | `generated_at`, `metric_pass_rates`, `metric_statuses`, `overall` | `metric_executed_tests` | `overall.pass_rate` in `[0,1]`; append-only history semantics | 10-1000 rows over time; recent run expected <=72h | No PII expected |
| Observability snapshot (latest) | `Docs/implementation/reports/observability_snapshot_latest.json` | `scripts/check_observability_snapshot.py` (`CMD-32`) | single snapshot row / `generated_at` | `generated_at` (UTC ISO timestamp) | `overall_status`, `artifact_snapshot`, `objective_snapshot`, `generated_at` | `objective` | `artifact_snapshot.coverage_percent` in `[0,100]`; objective pass metrics non-negative and bounded | 1 row; should be regenerated in active release window (<=72h) | No PII expected |
| Paper verification snapshot | `paper/artifacts/verification_snapshot.json` | `scripts/generate_paper_verification_snapshot.py` (`CMD-34`) | single snapshot artifact | generated on demand (no embedded timestamp) | `citation_sample`, `phase_graph` | none | counts non-negative; `coverage_pass` boolean | 1 row; refresh when paper/contracts change | No PII expected |

## Display + Exploration Plan

### Artifact registry

- Primary visualization: bar chart by `kind` to detect source diversity and skew.
- Primary table: `id`, `kind`, `title`, `url`, `retrieved_at`, `age_days`.
- Filters: dataset selector + table-native filter/sort.
- Drilldown: row JSON panel for tags/notes/source payload details.
- Cross-filtering: selecting `kind` in chart informs expected table filter (manual in this slice).
- Export: table copy/export is deferred (not now); JSON remains source-of-truth artifact.

### Objective metrics (latest)

- Primary visualization: pass-rate bars by metric id.
- Primary table: id/status/pass_rate/executed_tests/threshold/trend.
- Filters: status filter on data-quality page; table-native filter/sort on dataset page.
- Drilldown: row JSON panel includes full command/summary context.
- Cross-filtering: output status table and data-quality checks align to the same metric ids.
- Export: headless validation report output (`--output`) acts as machine-readable export.

### Objective metrics history

- Primary visualization: line chart of `overall_pass_rate` over `generated_at`.
- Primary table: generated_at/status/pass_rate/required/passed metrics.
- Filters: table-native filter/sort; dataset selector.
- Drilldown: row JSON for exact historical metric-status payload.
- Cross-filtering: referential-integrity check links historical metric ids to latest snapshot.
- Export: raw JSONL remains canonical append-only export.

### Observability snapshot (latest)

- Primary visualization: normalized percent bars for artifact coverage and objective pass rate.
- Primary table: overall status + artifact/objective signal fields.
- Filters: dataset selector + table-native filter/sort.
- Drilldown: row JSON for nested signal payloads.
- Cross-filtering: metric IDs are validated against objective metrics dataset.
- Export: `Docs/implementation/reports/observability_snapshot_latest.json` remains canonical export.

### Paper verification snapshot

- Primary visualization: grouped count bars for citation/phase graph metrics.
- Primary table: cites/claims/materialization counts + phase graph totals.
- Filters: dataset selector.
- Drilldown: row JSON for nested sections.
- Cross-filtering: outputs page aligns this dataset with objective metrics outputs.
- Export: `paper/artifacts/verification_snapshot.json` is the deterministic export artifact.

## TODOs (Data not yet integrated)

- Add release-tag metadata dataset once automated release tagging artifacts are produced.
- Add alert-routing/pager event dataset when observability routing depth is implemented.
- Add CSV export endpoint for filtered table views when a stable product requirement exists.
