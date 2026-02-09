# Objective Metrics Timeline

Generated at: `2026-02-09T02:37:13.662608+00:00`
Latest overall status: `pass`
Recorded runs: `5`

## Recent Runs

| Generated at | Overall | citation integrity | authority boundary | Passed metrics |
| --- | --- | --- | --- | ---: |
| `2026-02-09T02:37:13.662608+00:00` | `pass` | `pass` | `pass` | 2 |
| `2026-02-09T01:40:45.190659+00:00` | `pass` | `pass` | `pass` | 2 |
| `2026-02-09T01:16:15.740457+00:00` | `pass` | `pass` | `pass` | 2 |
| `2026-02-09T01:15:14.609552+00:00` | `pass` | `pass` | `pass` | 2 |
| `2026-02-09T01:14:00.582402+00:00` | `pass` | `pass` | `pass` | 2 |

## Query Examples

Inspect the append-only history store with `jq`:

```bash
jq -c '.' Docs/implementation/reports/objective_metrics_history.jsonl
```

List timestamps where overall status failed:

```bash
jq -r 'select(.overall.status == "fail") | .generated_at' Docs/implementation/reports/objective_metrics_history.jsonl
```

List citation integrity status by run:

```bash
jq -r '.generated_at + " " + .metric_statuses.citation_integrity' Docs/implementation/reports/objective_metrics_history.jsonl
```
