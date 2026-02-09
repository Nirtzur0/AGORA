# Epic: Artifacts and Evidence Reliability

## Goal

Keep artifact storage immutable and evidence resolution deterministic across all critical flows.

## User Stories

- As a researcher, I need citations to resolve to exact artifact versions.
- As a reviewer, I need deterministic evidence failures when pointers are invalid.

## Tasks

- Expand edge-case tests for evidence location parsing/validation.
- Confirm overwrite prevention for artifact versions remains enforced end-to-end.
- Validate repository and sandbox ingestion outputs remain traceable as artifacts.
