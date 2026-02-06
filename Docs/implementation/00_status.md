# Test Stabilization Status

Last updated: 2026-02-06

## Done

- Established test command map (see `docs/manifest/10_testing.md`).
- Confirmed pytest markers and strict marker configuration (`pytest.ini`).
- Confirmed CI jobs currently do not run pytest (see `docs/manifest/11_ci.md`).
- Added CI guardrail job enforcing status + checklist updates on PRs that change tests/CI/runtime (`.github/workflows/ci.yml`).
- Wrote final stabilization report (`Docs/implementation/reports/test_stabilization_final_report.md`).

## In Progress

- None.

### Baseline Results (2026-02-06)

- Unit (3x): `make test-unit` -> PASS (15 tests each run)
- Unit data contracts (3x): `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/data_contracts` -> PASS (6 tests each run)
- Integration: `make test-integration` -> PASS (169 tests)
- E2E: `make test-e2e` -> PASS (8 tests)
  - Notes: high warning volume (mostly `datetime.utcnow()` deprecations from core-api/worker and third-party libs; some Pydantic v2 `.dict()` deprecations).

## Next

- None.

## Commands

- Unit: `make test-unit`
- Unit (data contracts): `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/data_contracts`
- Integration: `make test-integration`
- E2E: `make test-e2e`
