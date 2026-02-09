# Reference: Release Workflow

This page defines AGORA release policy and how local release actions map to CI gates.

## Current State (Implemented)

- Push/PR CI gates enforce `CMD-11`, `CMD-25`, `CMD-27`, `CMD-30`, `CMD-31`, `CMD-37`, and `CMD-38`.
- Nightly full-suite promotion job is implemented as `cmd-13-nightly-full-suite` (`AR-C05`).
- Tag-triggered release validation path is implemented as `release-tag-gate` (`AR-C04`).
- First remote run evidence is captured:
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
- Missing release-readiness evidence blocks release publication.
- Missing artifact-feature alignment references blocks release publication.

## CI Mapping Snapshot

Current mapping (implemented):

- `cmd-11-fast-checks` -> `CMD-11`
- `cmd-12-integration` -> `CMD-25`
- `cmd-13-e2e-critical-flow` -> `CMD-27`
- `cmd-13-nightly-full-suite` -> `CMD-13`
- `cmd-30-ui-smoke-cross-browser` -> `CMD-30`
- `cmd-31-ui-smoke-mobile` -> `CMD-31`
- `cmd-37-38-dash-data-quality` -> `CMD-37` + `CMD-38`
- `release-tag-gate` -> `CMD-11`, `CMD-25`, `CMD-27`, `CMD-13`, `CMD-37`, `CMD-38`
- `smoke-test` -> `CMD-01` + `CMD-02` + `CMD-04`

## Release Candidate Verification Snapshot (2026-02-08)

- `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test` -> PASS
- `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test-all` -> PASS
- `make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test-e2e` -> PASS

## Implementation Handoff

- CI implementation completed by `prompt-02-app-development-playbook` follow-through (2026-02-09).
- Next non-redundant packet: `prompt-03-alignment-review-gate` to refresh residual-risk ranking after remote-evidence closure (`DIR-14`) and PR-only UI smoke failures (`CMD-30`/`CMD-31`).
