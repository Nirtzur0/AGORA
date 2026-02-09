# Dash Data Explorer UX Notes

Date: 2026-02-09
Prompt packet: `prompt-08-dash-data-explorer`

## Bet Tracking

- Appetite: `medium`
- `Now` slice: build one complete vertical slice over existing AGORA report/artifact datasets with:
  - multi-page Dash app (`Overview`, `Datasets`, `Outputs`, `Data Quality`)
  - headless validation engine with explicit rule outcomes and failing-sample drilldown
  - loader/validation tests and runbook docs
- `Now` state:
  - `uphill` while dataset inventory, schema expectations, and rule semantics are being mapped
  - `downhill` once loader contracts and validation report schema are stable
- `Not now`:
  - role-aware auth for the Dash explorer
  - full visual regression snapshots for the Dash UI
  - large-table virtualization and CSV export API for >10k-row datasets

## UX Decisions

- Navigation: fixed top nav with direct links to four task-oriented pages.
- Start-here guidance: `Overview` explains where to click first for common questions.
- Defaults: dataset picker defaults to artifact registry (broadest coverage signal).
- Drilldown pattern: tables support single-row selection with JSON panel details.
- Failure affordance: data-quality page provides pass/fail summary plus offending rows per rule.
- Verification traceability: `Outputs` page includes command-level "How to verify" panel.

## Data Quality Product Choices

- Rule model includes `rule_id`, `severity`, `status`, `metrics`, `offending_rows`.
- Required checks implemented in-app and headless:
  - missingness and required columns
  - numeric range checks
  - enum-domain checks
  - uniqueness
  - referential integrity across datasets
  - freshness windows for latest snapshots
  - completeness of required input artifacts

## External References Used

The following external references materially influenced API usage and table/interaction design:

- `EXT-DASH-001` - Dash official docs (pages/callback/navigation patterns)
- `EXT-DASH-DATATABLE-001` - Dash DataTable docs (sorting/filtering/page-size behavior)
- `EXT-PLOTLY-001` - Plotly Python docs (bar/line chart patterns)
- `EXT-FLASK-CACHING-001` - Flask-Caching docs (future cache strategy for heavier datasets)

## Remaining Improvements

- Add chart-to-table crossfilter callbacks (currently table filters are manual/native).
- Add explicit loading spinners for each dataset callback path.
- Add accessibility audit pass (color-only signaling and keyboard navigation checks).
- Add release dashboard panel once release-tag artifacts are machine-generated.
