# Documentation Index

AGORA documentation serves three audiences: new users onboarding locally, power users operating research workflows, and contributors evolving the system safely. This index is the single navigation entrypoint.

Quick Links: [Getting Started](./getting_started/quickstart.md) | [Tutorials](./tutorials/README.md) | [How-To](./how_to/run_end_to_end.md) | [Reference](./reference/configuration.md) | [Troubleshooting](./troubleshooting.md)

## Docs Bet Tracking

- Appetite: `medium`
- Not now:
  - External sink delivery implementation and first remote evidence capture for `AR-C12`
  - Expanded tutorial set beyond one end-to-end path

## Navigation Tree

### Canonical Product/System Specs

- [System Implementation Spec](./04-system-implementation-spec.md)
- [Implementation Checklist](./06-implementation-checklist.md)
- [Engineering Overview](./00-engineering-overview.md)
- [System Architecture (legacy overview)](./01-system-architecture.md)
- [Primitives and Grounding](./02-primitives-and-grounding.md)
- [Collaboration Protocol](./03-collaboration-protocol.md)
- [Evaluation and Risks](./05-evaluation-and-risks.md)

### Getting Started

- [Installation](./getting_started/installation.md)
- [Quickstart](./getting_started/quickstart.md)

### Tutorials

- [End-to-End Tutorial](./tutorials/README.md)

### How-To Guides

- [Configuration](./how_to/configuration.md)
- [Run End-to-End](./how_to/run_end_to_end.md)
- [Interpret Outputs](./how_to/interpret_outputs.md)
- [Upgrade Notes Template](./how_to/upgrade_notes_template.md)

### Dash Data Explorer

- [Data Catalog](./dash_data_explorer/data_catalog.md)
- [UX Notes](./dash_data_explorer/ux_notes.md)
- [Runbook](./dash_data_explorer/runbook.md)

### Reference

- [CLI and Commands](./reference/cli.md)
- [Configuration Reference](./reference/configuration.md)
- [Data Formats](./reference/data_formats.md)
- [Versioning Policy](./reference/versioning_policy.md)
- [Release Workflow](./reference/release_workflow.md)

### Explanation

- [Architecture Explanation](./explanation/architecture.md)
- [Design Decisions](./explanation/design_decisions.md)

### Operations

- [Troubleshooting](./troubleshooting.md)
- [Glossary](./glossary.md)
- [External Artifacts Store](./artifacts/README.md)
- [Changelog](../CHANGELOG.md)
- [Verification Paper Package](../paper/README.md)

## Engineering Docs (Manifest + Implementation)

These pages are internal engineering control-plane docs and should not be duplicated elsewhere.

### Manifest

- [Overview and Core Objective](./manifest/00_overview.md)
- [Architecture Source of Truth](./manifest/01_architecture.md)
- [Tech Stack](./manifest/02_tech_stack.md)
- [Decisions](./manifest/03_decisions.md)
- [API Contracts](./manifest/04_api_contracts.md)
- [Data Model](./manifest/05_data_model.md)
- [Security](./manifest/06_security.md)
- [Observability](./manifest/07_observability.md)
- [Deployment](./manifest/08_deployment.md)
- [Runbook Command Map](./manifest/09_runbook.md)
- [Testing](./manifest/10_testing.md)
- [CI](./manifest/11_ci.md)
- [Conventions](./manifest/12_conventions.md)
- [Literature Review](./manifest/20_literature_review.md)

### Implementation

- [Status](./implementation/00_status.md)
- [Worklog](./implementation/03_worklog.md)
- [Architecture Coherence Checklist](./implementation/checklists/00_architecture_coherence.md)
- [Plan Checklist](./implementation/checklists/01_plan.md)
- [Milestones Checklist](./implementation/checklists/02_milestones.md)
- [Test Stabilization Checklist](./implementation/checklists/04_test_stabilization.md)
- [UI Verification Checklist](./implementation/checklists/05_ui_verification.md)
- [Release Readiness Checklist](./implementation/checklists/06_release_readiness.md)
- [Alignment Review Checklist](./implementation/checklists/07_alignment_review.md)
- [Artifact-Feature Alignment Checklist](./implementation/checklists/08_artifact_feature_alignment.md)
- [Literature Review Checklist](./implementation/checklists/20_literature_review.md)
- [Reports Index](./implementation/reports/README.md)

## Where To Look Next

- New users: start at [Installation](./getting_started/installation.md), then [Quickstart](./getting_started/quickstart.md).
- Power users: go to [Run End-to-End](./how_to/run_end_to_end.md), then [Interpret Outputs](./how_to/interpret_outputs.md).
- Contributors: read [Conventions](./manifest/12_conventions.md), [Milestones](./implementation/checklists/02_milestones.md), and [Release Readiness](./implementation/checklists/06_release_readiness.md).

## Remaining Improvements

- Implement external observability sink delivery (`AR-C12`) and capture first remote publish evidence.
- Expand troubleshooting matrix with concrete error signatures from future incidents.
