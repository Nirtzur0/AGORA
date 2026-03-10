# Changelog

All notable changes to this project should be documented in this file.

The format is based on Keep a Changelog and this project uses Semantic Versioning for tagged releases.

## [Unreleased]

### Added

- Prompt-library submodule integration at `packages/project-prompts`.
- Prompt-driven engineering docs baseline under `Docs/manifest/` and `Docs/implementation/`.
- Architecture coherence and alignment review gate artifacts.
- Diataxis + release-discipline documentation set under `Docs/`.

### Changed

- Test stabilization report updated with 2026-02-08 revalidation evidence.
- CI workflow now enforces runbook-equivalent fast checks (`CMD-11`) and integration matrix checks (`CMD-12`).
- Docs guardrail now requires status/worklog + active checklist updates for runtime/test/CI changes.
- Release workflow and release-readiness checklist updated with concrete command evidence.
- CI now includes implemented nightly full-suite gate (`cmd-13-nightly-full-suite`) and tag-triggered release gate (`release-tag-gate`) for `AR-C04`/`AR-C05`, with fail-closed release evidence checks.
- Observability/release docs now define `AR-C12` external sink ownership, severity routing, and dry-run fallback policy ahead of implementation.
- CI now publishes observability payloads to an external sink via `scripts/publish_observability_sink.py` (objective metrics/snapshot + nightly/release runtime trends), with first remote active-mode evidence captured in run `21813367976`.
- Sink routing governance now defines explicit gate-class fail-open/fail-closed policy (`AR-C13`) across observability, CI, release workflow, and release-readiness docs.

## [0.1.0] - 2026-02-06

### Added

- Core MVP implementation slices aligned to `Docs/manifest/04_api_contracts.md`.
- Test stabilization checklist/report and CI docs guardrail.
