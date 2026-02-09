# Observability Snapshot Dashboard

Generated at: `2026-02-09T02:37:03.713784+00:00`
Overall status: `pass`

## Signal Summary

| Signal | Status | Key values |
|---|---|---|
| Artifact freshness/provenance | `pass` | coverage=100.0%, warnings=0, stale=0, missing=0, invalid_ts=0 |
| Objective metrics | `pass` | passed=2/2, history_runs=4, pass_streak=4 |

## Commands

```bash
make check-observability-slos
make check-objective-metrics
make check-observability-snapshot
```

## Outputs

- `Docs/implementation/reports/observability_snapshot_latest.json`
- `Docs/implementation/reports/observability_snapshot_dashboard.md`
