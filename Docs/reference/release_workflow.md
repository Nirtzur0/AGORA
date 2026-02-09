# Reference: Release Workflow

This page defines AGORA release policy and how local release actions map to CI gates.

## Current State (Implemented)

- Push/PR CI gates enforce `CMD-11`, `CMD-25`, `CMD-27`, `CMD-30`, `CMD-31`, `CMD-37`, and `CMD-38`.
- Nightly full-suite promotion job is implemented as `cmd-13-nightly-full-suite` (`AR-C05`).
- Tag-triggered release validation path is implemented as `release-tag-gate` (`AR-C04`).
- Runtime/flake policy is now codified for nightly and release heavy gates (`AR-C10`).
- Runtime/flake trend artifacts are now emitted for nightly and release heavy gates (`AR-C11`).
- External observability sink routing is implemented with fail-open controls (`AR-C12`).
- First remote run evidence is captured:
  - dispatch run `21813367976`: `cmd-13-nightly-full-suite` pass (`62929945541`) with sink publish step pass (`active`, `httpbin.org`, response `200`)
  - dispatch run `21813014551`: `cmd-13-nightly-full-suite` pass (`62928919065`) with `cmd-13-nightly-runtime-trend` artifact publication
  - dispatch run `21811670648`: `release-tag-gate` pass (`62924827121`) and `cmd-13-nightly-full-suite` pass (`62924827118`)
  - PR run `21811670116`: `cmd-37-38-dash-data-quality` pass (`62924847427`)

## Local Release Preparation

1. Complete release checklist: `Docs/implementation/checklists/06_release_readiness.md`.
2. Confirm alignment gate inputs:
   - latest artifact-feature alignment checklist/report: `Docs/implementation/checklists/08_artifact_feature_alignment.md`, `Docs/implementation/reports/artifact_feature_alignment.md`
   - explicit handling of any open alignment outcomes in release decision notes.
3. Update `CHANGELOG.md` and finalize release-specific upgrade notes from `Docs/how_to/upgrade_notes_template.md`.
4. Run required command set from `Docs/manifest/09_runbook.md`:
   - `CMD-11` (`make test`)
   - `CMD-25` (`make test-all-guarded`)
   - `CMD-27` (`make test-e2e-critical`)
   - `CMD-13` (`make test-e2e`, budgeted by `E2E_FULL_WARNING_BUDGET`) as full-suite release gate
   - `CMD-37` and `CMD-38` (Dash data-quality gate)
5. Record command outcomes in release notes and release-readiness evidence.

## CMD-13 Promotion Strategy (AR-C05 Policy)

| Trigger | Required coverage | Owner | Promotion/blocking rule |
|---|---|---|---|
| PR / branch push | `CMD-27`, `CMD-30`, `CMD-31`, `CMD-37`, `CMD-38` | feature author + reviewer | merge blocked by failing required gates; `CMD-13` optional local signal |
| Nightly `main` run | `CMD-13` full suite | maintainers | latest nightly `CMD-13` must be green and <=24h old before release cut |
| `v*` release tag run | `CMD-11`, `CMD-25`, `CMD-27`, `CMD-13`, `CMD-37`, `CMD-38` | release owner | tag release blocked on any failure |
| Manual release candidate | same as tag run command set | release owner | candidate cannot be promoted without full pass evidence |

Promotion from critical-only coverage to release approval requires:

1. Latest nightly full-suite `CMD-13` pass on `main` (<=24h).
2. Passing tag candidate run from `release-tag-gate`.
3. Completed release-readiness checklist + changelog and upgrade notes.
4. `CMD-13` warning budget is respected (`E2E_FULL_WARNING_BUDGET`, default `200`).

## Runtime and Flake Budget Policy (`AR-C10`)

| Gate | Runtime target | Hard timeout | Flake retry budget | Promotion behavior |
|---|---|---|---|---|
| `cmd-13-nightly-full-suite` | 90 minutes (`NIGHTLY_RUNTIME_TARGET_MINUTES`) | 180 minutes (`timeout-minutes`) | 1 retry for transient failures (`NIGHTLY_FLAKE_RETRY_BUDGET=1`) | If retries are exhausted or timeout is hit, nightly stays red and release promotion is blocked until a fresh green nightly run exists |
| `release-tag-gate` (`CMD-13` segment) | 120 minutes (`RELEASE_RUNTIME_TARGET_MINUTES`) | 210 minutes (`timeout-minutes`) | 0 retries (`RELEASE_FLAKE_RETRY_BUDGET=0`) | Any failure, runtime-target breach, or timeout blocks release publication (fail-closed) |

Operational notes:

1. Both gates emit `runtime_policy_summary ...` lines and persist summary artifacts for auditability.
2. Release job enforces parsed runtime/attempt policy before release evidence bundling.
3. Exceeding release runtime target or retry budget is treated as a promotion blocker, not a warning.

## Runtime and Flake Trend Artifacts (`AR-C11`)

- `cmd-13-nightly-full-suite` now publishes `cmd-13-nightly-runtime-trend` artifact containing:
  - `/tmp/cmd-13-nightly-runtime-policy.txt`
  - `/tmp/cmd-13-nightly-runtime-trend-latest.json`
  - `/tmp/cmd-13-nightly-runtime-trend-history.jsonl`
  - `/tmp/cmd-13-nightly-runtime-trend-dashboard.md`
- `release-tag-gate` now publishes equivalent trend files in `release-tag-gate-artifacts`:
  - `/tmp/release-tag-runtime-policy.txt`
  - `/tmp/release-tag-runtime-trend-latest.json`
  - `/tmp/release-tag-runtime-trend-history.jsonl`
  - `/tmp/release-tag-runtime-trend-dashboard.md`
- Trend synthesis source:
  - `python scripts/build_ci_runtime_trend.py ...`
- Operational interpretation:
  1. Runtime-target misses across two consecutive heavy runs are treated as release-operability drift.
  2. Retry usage in 3 of the latest 5 heavy runs is treated as flake-signal degradation requiring maintainer triage.
  3. Artifacts are retained as release evidence and mirrored into GitHub job summaries for quick review.

## External Sink Ownership and Rollout Readiness (`AR-C12`)

Status: implemented with fail-open rollout; fail-closed tightening deferred.

Escalation ownership before implementation:

| Severity class | Primary owner | Secondary owner | Release impact rule |
|---|---|---|---|
| SEV-1 | Maintainer on-call | Release owner | release cut is blocked until triage outcome is explicit |
| SEV-2 | Maintainer on-call | Core API/Worker maintainer | release owner decides go/no-go with documented rationale |
| SEV-3 | Next working cycle owner | Maintainer on-call | no immediate release block unless trend worsens |

Signal mapping source of truth:

- `Docs/manifest/07_observability.md` (`Severity Routing` + `External Sink Ownership and Escalation Policy`).
- `Docs/manifest/11_ci.md` (`External Sink Routing Plan`).

Rollout and fallback policy:

1. `workflow_dispatch` supports `observability_sink_mode` (`disabled`, `dry_run`, `active`) and optional `observability_sink_url` override.
2. Publish steps run with fail-open policy (`--fail-open true`) so sink-delivery failures do not block release promotion.
3. During any sink outage, release decisions rely on in-repo signals from `CMD-29`, `CMD-32`, `CMD-39`, and `CMD-40` outputs.
4. Future tightening can selectively move sink failures to fail-closed once destination reliability and pager workflows are stable.

First remote evidence:

- Run `21813367976`, job `62929945541` (`cmd-13-nightly-full-suite`) passed sink publish in `active` mode and uploaded:
  - `cmd-13-nightly-observability-sink-report.json`
  - `cmd-13-nightly-observability-sink-summary.md`

## Tag-Triggered Release Path (AR-C04 Implemented Trigger Spec)

Implemented workflow trigger in `.github/workflows/ci.yml`:

```yaml
on:
  push:
    branches:
      - main
      - develop
    tags:
      - "v*"
  schedule:
    - cron: "0 7 * * *"
  workflow_dispatch:
    inputs:
      run_release_gate:
      run_full_e2e:
      observability_sink_mode:
      observability_sink_url:
```

Implemented release job sequence:

1. Checkout and dependency setup.
2. Bring up infra (`CMD-01`) and Temporal preflight (`CMD-24`).
3. Run quality gates: `CMD-11`, `CMD-25`, `CMD-27`, `CMD-13`, `CMD-37`, `CMD-38`.
4. Validate release docs evidence (`CHANGELOG.md`, `Docs/how_to/upgrade_notes_template.md`, `Docs/implementation/checklists/06_release_readiness.md`).
5. Publish release evidence artifacts (test reports + readiness checklist snapshot).
6. Tear down infra (`CMD-02`).

Fail-closed policy:

- Any failed required gate blocks release publication.
- Runtime/flake policy violations in `release-tag-gate` block release publication.
- Missing release-readiness evidence blocks release publication.
- Missing artifact-feature alignment references blocks release publication.

## CI Mapping Snapshot

Current mapping (implemented):

- `cmd-11-fast-checks` -> `CMD-11`
- `cmd-12-integration` -> `CMD-25`
- `cmd-13-e2e-critical-flow` -> `CMD-27`
- `cmd-13-nightly-full-suite` -> `CMD-13`
- `cmd-13-nightly-full-suite` runtime trend synthesis -> `CMD-39`
- `cmd-13-nightly-full-suite` sink publish -> `CMD-40`
- `cmd-30-ui-smoke-cross-browser` -> `CMD-30`
- `cmd-31-ui-smoke-mobile` -> `CMD-31`
- `cmd-37-38-dash-data-quality` -> `CMD-37` + `CMD-38`
- `release-tag-gate` -> `CMD-11`, `CMD-25`, `CMD-27`, `CMD-13`, `CMD-37`, `CMD-38`
- `release-tag-gate` runtime trend synthesis -> `CMD-39`
- `release-tag-gate` sink publish -> `CMD-40`
- `smoke-test` -> `CMD-01` + `CMD-02` + `CMD-04`

## Release Candidate Verification Snapshot (2026-02-08)

- `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test` -> PASS
- `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test-all` -> PASS
- `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test-e2e` -> PASS

## Implementation Handoff

- CI implementation completed by `prompt-02-app-development-playbook` follow-through (2026-02-09).
- Runtime/flake policy codification (`AR-C10`) completed by `prompt-02-app-development-playbook` follow-through (2026-02-09).
- Runtime/flake trend telemetry (`AR-C11`) completed by `prompt-02-app-development-playbook` follow-through (2026-02-09).
- AR-C11 remote evidence follow-through completed by workflow dispatch run `21813014551` (`cmd-13-nightly-full-suite` + `cmd-13-nightly-runtime-trend` artifact).
- `prompt-11-docs-diataxis-release` follow-through completed ownership/escalation/fallback shaping for `AR-C12` (2026-02-09).
- `prompt-02-app-development-playbook` follow-through implemented external sink delivery and captured first remote evidence for `AR-C12` via run `21813367976` (2026-02-09).
- Next non-redundant packet: `prompt-03-alignment-review-gate` to rerank residual risks after `AR-C12` implementation evidence.
