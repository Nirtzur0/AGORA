# Checklist: UI/UX Redesign and Figma Handoff

Date: 2026-03-11  
Packet: manual AGORA UI/UX audit + redesign handoff  
Objective anchor: `Docs/manifest/00_overview.md#Core Objective`

## Scope lock

- [x] Primary UI audience fixed to maintainers/reviewers.
  - Why: AGORA's highest-value dashboard job is triage, provenance inspection, gate readiness, and review orchestration.
- [x] Scope fixed to full product redesign packet.
  - Included: login, portfolio, workspace overview, investigation, research record, operations, review/governance, team/settings, system guidance.
- [x] No backend contract or data-model changes in this packet.
  - Constraint: any route hierarchy or component boundaries described here remain frontend handoff guidance until a later implementation packet.

## Design artifacts

- [x] Public redesign preview routes added under `/design-preview/agora-redesign/*`.
  - Files: `apps/web/src/App.jsx`, `apps/web/src/design-preview/AgoraRedesignPage.jsx`, `apps/web/src/design-preview/AgoraRedesignPage.css`
- [x] Deterministic current-state fixture seeder added for captureable AGORA routes.
  - File: `apps/web/scripts/seed_ui_audit_fixture.mjs`
- [x] New Figma file created.
  - URL: `https://www.figma.com/design/jLSN22ajGiadKjsJvuTOnK`
  - File key: `jLSN22ajGiadKjsJvuTOnK`
- [x] Initial current-state capture completed in Figma.
  - Captured route: `/projects`
- [x] Additional current-state/redesign capture tabs launched against the documented preview routes.
  - Evidence source: `Docs/implementation/reports/ui_ux_audit_redesign.md`
- [ ] Key node-level Figma URLs and node IDs recorded for every main redesign screen.
  - Blocker: Figma MCP tool-call quota was exhausted after file creation and follow-on capture launch, so node extraction must be appended when quota resets.

## Report and planning docs

- [x] Added the full audit/redesign report with sections `# 1` through `# 17`.
  - File: `Docs/implementation/reports/ui_ux_audit_redesign.md`
- [x] Expanded the UI epic from verification-only to redesign + handoff.
  - File: `Docs/implementation/epics/epic_ui_audit_and_release.md`
- [x] Added milestone-level tracking for the redesign packet.
  - File: `Docs/implementation/checklists/02_milestones.md`
- [x] Updated project plan / PRD references to include the redesign packet and maintainers-first dashboard requirements.
  - Files: `Docs/implementation/reports/project_plan.md`, `Docs/implementation/reports/prd.md`
- [x] Updated status, worklog, and decision trail for this packet.
  - Files: `Docs/implementation/00_status.md`, `Docs/implementation/03_worklog.md`, `Docs/manifest/03_decisions.md`

## Validation

- [x] `npm --prefix apps/web run build`
- [x] Browser route check for redesign preview + seeded current overview
  - Command: `node --input-type=module` Playwright route check
- [x] `npm --prefix apps/web run smoke:artifact-viewer`
- [x] Figma file creation confirmed through MCP
- [x] Real AGORA API seeding used instead of static fake capture data for current-state routes

## Residual risk

- [x] The file-level Figma artifact is durable and usable now.
- [ ] Node-level Figma references are still missing due MCP quota and should be appended in a small follow-up.
