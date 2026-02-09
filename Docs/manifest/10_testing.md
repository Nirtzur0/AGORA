# Testing

## Canonical Command Source

The canonical command map is `Docs/manifest/09_runbook.md`.
Use runbook command IDs instead of duplicating command tables across docs:

- Unit: `CMD-11`
- Unit + integration: `CMD-12`
- E2E: `CMD-13`
- UI browser smoke: `CMD-23`
- UI cross-browser smoke matrix: `CMD-30`
- UI mobile-width smoke: `CMD-31`
- Dash data-quality headless validation: `CMD-37`
- Dash loader/validation regression tests: `CMD-38`
- Paper invariant harness + map contract: `CMD-33`
- Paper snapshot generation: `CMD-34`
- Stub/TODO guardrail: `CMD-14`
- Infra lifecycle for integration/E2E setup: `CMD-01`, `CMD-02`, `CMD-03`

## Test Runner and Config

- Runner: `pytest`
- Config: `pytest.ini`
- Default pattern: disable global plugin autoload, explicitly load `pytest_asyncio.plugin`

## Markers

Markers are strict (`--strict-markers`) and defined in `pytest.ini`:

- `unit`
- `integration`
- `e2e`
- `slow`
- `docker`
- `postgres`
- `minio`
- `external`
- `asyncio`

## Test Pyramid (Current)

- Unit tests: fast checks for module behavior and contracts.
- Integration tests: DB/storage/workflow integration behaviors.
- E2E tests: critical user/system flows.
- Contract checks: evidence and data invariants (primarily unit/integration today).
- Paper verification contract checks: equation-to-code drift and invariant harness (`tests/unit/paper/*`).
- Dash data explorer checks: loader smoke + validation rule regression (`tests/test_loaders_smoke.py`, `tests/test_data_validation.py`).

## Critical E2E Warning Budget

- `CMD-27` (`make test-e2e-critical`) enforces a warning budget via `scripts/check_critical_e2e_warning_budget.py`.
- Default budget is `40` warnings (configurable via `E2E_CRITICAL_WARNING_BUDGET`).
- Budget breaches fail the command even if the test itself passes.

## Full E2E Warning Budget

- `CMD-13` (`make test-e2e`) now enforces a warning budget via `scripts/check_full_e2e_warning_budget.py`.
- Default budget is `200` warnings (configurable via `E2E_FULL_WARNING_BUDGET`).
- Budget breaches fail the command even if all e2e tests pass.

## Full E2E Promotion Strategy (`CMD-13`, AR-C05 Policy)

- Required coverage by trigger:
  - PR/branch push: `CMD-27`, `CMD-30`, `CMD-31`, `CMD-37`, `CMD-38`.
  - Nightly `main` (`cmd-13-nightly-full-suite`): `CMD-13`.
  - `v*` tag release gate (`release-tag-gate`): `CMD-11`, `CMD-25`, `CMD-27`, `CMD-13`, `CMD-37`, `CMD-38`.
- Ownership:
  - Feature author/reviewer owns PR-scope failures.
  - Maintainers own nightly `CMD-13` triage and release-gate readiness.
  - Release owner owns tag-run pass/fail and promotion decision.
- Promotion rule:
  - A release candidate is promoted only when the latest nightly `CMD-13` pass is fresh (<=24h old), respects the full-e2e warning budget, tag-run required checks pass, and release-readiness docs are complete.

## Contract Ownership and Change Policy

Contract modules and owners:

- `tests/unit/data_contracts/*`: Core API + Worker maintainers
- `tests/integration/data_contracts/*`: Core API maintainers
- `tests/e2e/data_contracts/*`: workflow maintainers
- `tests/test_data_validation.py`, `tests/test_loaders_smoke.py`: data explorer maintainers

Threshold change policy:

- Any contract threshold/domain change must include:
  - rationale in `Docs/manifest/03_decisions.md`
  - owner attribution
  - impacted test module paths
- Changes that relax constraints must include replacement safeguards (equal or stronger signal) and updated acceptance evidence in `Docs/implementation/03_worklog.md`.

## Environment Notes

Integration and e2e runs assume local infra from `infra/docker-compose.yml` is available.
Reference required env vars in `Docs/manifest/09_runbook.md`.
