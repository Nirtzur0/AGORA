# Docs Index

This repository has two documentation roots:

- `Docs/` (canonical product/system specification)
  - Source-of-truth contracts live in `Docs/04-system-implementation-spec.md` and the build order/acceptance checks live in `Docs/06-implementation-checklist.md`.
- `docs/` (engineering manifest + implementation audit trail)
  - This folder exists to keep operational decisions, CI/test command mapping, and stabilization work auditable.

## Contents

- Manifest (living reference)
  - `docs/manifest/03_decisions.md`: significant engineering decisions (date-stamped).
  - `docs/manifest/10_testing.md`: how to run tests, markers, and environment requirements.
  - `docs/manifest/11_ci.md`: CI workflow mapping and required checks.

- Implementation (work tracking)
  - `docs/implementation/00_status.md`: current stabilization status and commands.
  - `docs/implementation/03_worklog.md`: chronological log of stabilization work.
  - `docs/implementation/checklists/04_test_stabilization.md`: acceptance checklist (checkboxes).
  - `docs/implementation/reports/test_stabilization_final_report.md`: final summary report.

