# Objective Metrics Timeline

Generated at: `2026-02-09T12:26:55.947992+00:00`
Latest overall status: `pass`
Recorded runs: `14`

## Recent Runs

| Generated at | Overall | citation integrity | authority boundary | Passed metrics |
| --- | --- | --- | --- | ---: |
| `2026-02-09T12:26:55.947992+00:00` | `pass` | `pass` | `pass` | 2 |
| `2026-02-09T12:26:43.371909+00:00` | `fail` | `fail` | `fail` | 0 |
| `2026-02-09T11:52:23.722900+00:00` | `pass` | `pass` | `pass` | 2 |
| `2026-02-09T11:52:06.079031+00:00` | `fail` | `fail` | `fail` | 0 |
| `2026-02-09T11:41:03.218207+00:00` | `pass` | `pass` | `pass` | 2 |
| `2026-02-09T05:30:19.501510+00:00` | `pass` | `pass` | `pass` | 2 |
| `2026-02-09T04:57:34.809324+00:00` | `pass` | `pass` | `pass` | 2 |
| `2026-02-09T04:40:17.323173+00:00` | `pass` | `pass` | `pass` | 2 |
| `2026-02-09T04:39:30.359723+00:00` | `fail` | `fail` | `fail` | 0 |
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
