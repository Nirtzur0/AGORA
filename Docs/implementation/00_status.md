# Test Stabilization Status

Last updated: 2026-02-06

## Done

- Established test command map (see `docs/manifest/10_testing.md`).
- Confirmed pytest markers and strict marker configuration (`pytest.ini`).
- Confirmed CI jobs currently do not run pytest (see `docs/manifest/11_ci.md`).

## In Progress

- Baseline runs (unit + data contracts, then integration, then e2e) with non-flake proof reruns.

## Next

1. Run unit suite (baseline + 3x reruns for flake proof).
2. Run unit `data_contracts` suite (baseline + 3x reruns).
3. Run integration suite; ensure intended skips are explicit and documented.
4. Run e2e suite; gate as needed with markers and documented environment requirements.

## Commands

- Unit: `make test-unit`
- Unit (data contracts): `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -p pytest_asyncio.plugin -q tests/unit/data_contracts`
- Integration: `make test-integration`
- E2E: `make test-e2e`

