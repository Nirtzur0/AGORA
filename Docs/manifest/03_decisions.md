# Decisions

This is a date-stamped decision log for changes that affect testing policy, CI policy, or repository structure.

- 2026-02-06: Introduced `docs/` as the audit trail for test stabilization work (without changing canonical spec location in `Docs/`).
- 2026-02-06: Added a CI guardrail job that requires updates to `Docs/implementation/00_status.md` and `Docs/implementation/checklists/04_test_stabilization.md` when PRs change tests/CI/runtime.
