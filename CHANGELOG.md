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

## [0.1.0] - 2026-02-06

### Added

- Core MVP implementation slices aligned to `Docs/04-system-implementation-spec.md`.
- Test stabilization checklist/report and CI docs guardrail.
