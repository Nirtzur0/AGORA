# Test Stabilization Status

Last updated: 2026-02-06

## Done

- Established test command map (see `docs/manifest/10_testing.md`).
- Confirmed pytest markers and strict marker configuration (`pytest.ini`).
- Confirmed CI jobs currently do not run pytest (see `docs/manifest/11_ci.md`).

## In Progress

- Baseline runs (unit + data contracts, then integration, then e2e) with non-flake proof reruns.

### Baseline Results (2026-02-06)

- Unit: `make test-unit` -> PASS (15 tests)
- Unit data contracts: `... pytest ... tests/unit/data_contracts` -> PASS (6 tests)
  - Notes: deprecation warnings from `apps/core-api/jwt_utils.py` (uses `datetime.utcnow()`).

## Next

1. Run integration suite once (baseline).
2. Run e2e suite once (baseline).
3. Add CI guardrail check (PRs touching tests/CI/runtime must update status + checklist).
4. Final verification: rerun unit 3x and unit data contracts 3x (flake proof).

## Commands

- Unit: `make test-unit`
- Unit (data contracts): `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/data_contracts`
- Integration: `make test-integration`
- E2E: `make test-e2e`
