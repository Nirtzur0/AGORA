# Versioning Policy

AGORA follows Semantic Versioning for tagged releases.

## Policy

- MAJOR: breaking API/contract or migration-incompatible changes.
- MINOR: backward-compatible feature additions.
- PATCH: backward-compatible fixes and documentation/operational fixes.

## Compatibility Rules

- Contract-breaking endpoint/schema changes require MAJOR version bump and migration notes.
- New optional fields and backward-compatible endpoints can be MINOR.
- Pure fixes/docs updates are PATCH unless they alter external behavior.

## Migration and Deprecation

- Any breaking change must include upgrade notes.
- Deprecations should include timeline and replacement guidance in release notes.
- DB migration requirements must be listed in release-readiness checklist.
