# AGORA UI/UX Audit + Figma Redesign Handoff

Date: 2026-03-11  
Audience: Maintainers and reviewers first; contributors second  
Objective anchor: `Docs/manifest/00_overview.md#Core Objective`  
Figma file: [AGORA UI Audit + Redesign - 2026-03-11](https://www.figma.com/design/jLSN22ajGiadKjsJvuTOnK)  
Current-state capture sources:
- `http://127.0.0.1:3000/projects`
- `http://127.0.0.1:3000/projects/b797be9e-eb5c-4223-a291-be104bcd0f5d/overview`
Redesign capture sources:
- `http://127.0.0.1:3000/design-preview/agora-redesign/login`
- `http://127.0.0.1:3000/design-preview/agora-redesign/portfolio`
- `http://127.0.0.1:3000/design-preview/agora-redesign/workspace-overview`
- `http://127.0.0.1:3000/design-preview/agora-redesign/investigation`
- `http://127.0.0.1:3000/design-preview/agora-redesign/research-record`
- `http://127.0.0.1:3000/design-preview/agora-redesign/operations`
- `http://127.0.0.1:3000/design-preview/agora-redesign/review-governance`
- `http://127.0.0.1:3000/design-preview/agora-redesign/team-settings`
- `http://127.0.0.1:3000/design-preview/agora-redesign/system`

## 1. Executive verdict

AGORA is credible, serious, and technically grounded, but the current UI is not yet elegant, calm, or truly dashboard-grade. It behaves like a capable internal console assembled around available endpoints: useful once you already understand the system, but too flat, too ledger-first, and too form-heavy to feel premium or immediately legible.

The redesign direction is to treat AGORA as an operational review product rather than a pile of adjacent CRUD tabs. The new structure elevates decisions, blockers, gate readiness, provenance hotspots, and work queues before raw registries or creation forms. The resulting product should feel like a maintainers' control tower with deliberate investigation and research-record modes, not an index of system nouns.

## 2. What is working

- The product has a real point of view. Immutable artifacts, evidence resolution, critiques, rule checks, and authority boundaries are meaningful product concepts, not generic project-management filler.
- The current UI already exposes a valuable provenance drill-down. Claim and draft evidence can lead to exact artifact-version views, which is one of the strongest product ideas and should be preserved.
- The existing warm palette and serif-plus-sans mix give AGORA a distinct, trustworthy tone. It does not feel like a stock SaaS starter.
- The current shell and overview copy signal that the product is about governed research work, not generic notes or files.
- The current tab coverage is broad. The product surface is functionally rich enough to support a more opinionated and useful information architecture.

## 3. What is not working

- The workspace experience is too flat. Eleven peer tabs imply equal importance for overview, requests, claims, drafts, team management, search, rule checks, and timeline, which is not how real users think about the work.
- The landing surfaces are not decision-first. They show counts and registries, but they do not aggressively answer: what is wrong, what changed, what needs me now, and can this workspace move forward?
- Creation and editing forms occupy too much primary space. The product shows "make a thing" controls before it has earned context, synthesis, or workflow guidance.
- Investigation is fragmented. Artifacts, claims, drafts, search, and provenance all belong to one mental model, but today they are split across separate surfaces that force context switching.
- Review and governance are visually under-aggregated. Blocking critiques, failed checks, and task blockers exist, but the product does not orchestrate them into a coherent queue or decision lane.
- Team and request flows feel bolted on instead of systematized. They exist, but they do not inherit a clear design-system or workflow rhythm.

## 4. UX/UI anti-patterns found

- Too many peer-level tabs for one workspace.
- Forms and ledgers competing with summary content on the same level.
- Equal-weight cards where some content should be primary and some should be background context.
- Raw activity and raw rule-check lists shown before synthesized operational meaning.
- Search results that expose metadata and snippets but do not unify with artifact and claim investigation.
- Governance state split between overview, drafts, requests, critiques, and rule checks rather than being one explicit review flow.
- Empty states that are mechanically informative but not task-directing.
- Component families that are close, but not fully normalized. Some surfaces feel considered, some still feel assembled.

## 5. Information design critique

The current product mixes five very different user intents into one level of navigation:

1. understand overall workspace health  
2. investigate evidence and provenance  
3. author or update the research record  
4. run operations and requests  
5. review governance and team state

That flattening hurts almost every workflow. New users do not get clear information scent. Repeat users have to remember which tab holds which piece of state. Power users can work around the product, but the UI does not actively support their scanning patterns.

The main structural correction is to separate:

- Overview: workspace health, blockers, gate readiness, recent critical changes
- Investigation: search, artifacts, evidence, provenance, comparison
- Research record: claims, drafts, citation coverage, review context
- Operations: requests, tasks, timelines, runtime signals
- Review and governance: critiques, rule checks, decision queue, sign-off
- Team and settings: roles, approvals, integrations, workspace configuration

## 6. Dashboard/data-presentation critique

AGORA is a data-dense operational product, but the current UI often presents data as lists of objects rather than as decision-support information.

- Counts are present, but relationships are weak. A blocker count without ownership, age, or affected gate state is only mildly useful.
- Timeline data is available, but it is not summarized into "what changed that matters."
- Rule checks are exposed as a ledger instead of as a gate-health model.
- Claims, drafts, artifacts, and search results should work as an evidence cluster, but they currently read as separate registries.
- The product wisely avoids noisy chart spam, but it needs more elegant rollups: gate readiness strips, blocker digests, attention queues, and small trend modules.
- The right home for low-level records is detail-on-demand, not the first thing users see.

What should be aggregated:

- blocking critiques + failing rule checks + blocked tasks -> one workspace decision queue
- recent logs/events/requests -> one operational signal digest
- artifacts + claims + draft citations + search hits -> one investigation model
- task status + ownership + outputs -> one maintainers' work queue

## 7. Redesign principles

- Overview first, detail on demand.
- Summary before ledger.
- One mental model per screen.
- Separate command surfaces from reading surfaces.
- Treat provenance as a first-class investigation pattern, not a side drawer attached to random tabs.
- Preserve the product's seriousness and warmth, but reduce surface noise.
- Optimize for scanning and triage for repeat users.
- Make empty, loading, partial-data, and blocked states feel intentional.

## 8. Proposed new information architecture

Global structure:

- Portfolio
- Workspace Overview
- Investigation
- Research Record
- Operations
- Review and Governance
- Team and Settings

Behavioral intent:

- Portfolio is the maintainers' watchlist and prioritization view.
- Workspace Overview is the control tower for a single workspace.
- Investigation is where users ask "what happened?" and "what supports this?"
- Research Record is where users read and assess claims and drafts together.
- Operations is where requests and task execution live.
- Review and Governance is where decisions, critiques, checks, and sign-off readiness are managed.
- Team and Settings is where approvals, roles, and configuration live without competing with day-to-day work.

## 9. Proposed screen set

- Login and first-run orientation
- Portfolio dashboard
- Workspace overview
- Investigation workspace
- Artifact and provenance detail
- Research record workspace
- Operations queue
- Review and governance queue
- Team and settings
- System/tokens/components page
- Empty-state and low-data variants
- Responsive laptop/tablet/mobile adaptations for overview, investigation, and review

## 10. Proposed component system

- App shell with persistent left navigation and top command rail
- Context header with workspace health, ownership, and quick actions
- KPI cluster cards
- Alert digest cards
- Gate readiness strip
- Investigation result cards
- Artifact detail panel
- Provenance chain panel / drawer
- Dense review table
- Work queue row
- Request pipeline stage cards
- Role matrix table
- Settings section card
- Structured empty state
- Loading skeleton set
- Error and permission banners

## 11. Interaction model

- Global command/search should work as a navigation and investigation accelerator, not just a filter input.
- Filters should live with the workflow they affect and support saved views for repeat users.
- Detail drawers should be used for contextual drill-downs; full-screen views should be used for reading and comparing.
- Inline editing should be limited to low-risk metadata and status changes. Complex authoring belongs in dedicated forms or panes.
- Bulk actions belong in tables and review queues, not on overview surfaces.
- Confirmation should be proportional: soft confirmation for low-risk changes, explicit confirmation for governance or destructive actions.
- Keyboard support should prioritize search, table navigation, queue triage, and artifact opening.

## 12. Visual design direction

- Keep AGORA's warm cream, gold, and deep teal tone, but make it more disciplined.
- Use serif display sparingly for framing and page identity; keep operational content in a dense sans.
- Increase contrast between primary content, supportive context, and low-priority metadata.
- Reduce the number of card treatments and border/shadow combinations.
- Prefer compact, information-dense panels over oversized cards.
- Use semantic colors carefully: alert colors only for actual exceptions, not generic emphasis.
- Use micro-trend bars and status strips instead of gratuitous dashboard charts.

## 13. States and edge cases

- Empty states must explain what the screen is for, what it unlocks, and what action should happen next.
- Loading states should preserve layout so dense operational screens do not jump.
- Partial data should distinguish "not loaded yet," "not available," and "not applicable."
- Permission differences should state what the user can do instead of only denying access.
- Long text needs collapse/expand patterns in claims, critiques, and timeline surfaces.
- Stale data and disconnected integrations should have clear freshness markers.
- Search with no results should suggest adjacent workflows rather than ending in a dead wall.

## 14. Accessibility review

- The existing product already includes a skip link and visible focus treatment, which is worth preserving.
- The redesign must keep color from being the only signal; blocker, warning, and success states should combine color with text and iconography.
- Dense tables and ledgers need row grouping, sticky headers where useful, and keyboard-friendly actions.
- Typography should preserve readability at compact density.
- Interactive pills and chips need clear hit targets and selected states.
- Investigation detail views must support keyboard navigation between result list and detail panel.

## 15. Figma file structure recommendation

Recommended page structure inside the Figma file:

- `00 Current State`
- `01 IA and Principles`
- `02 Portfolio`
- `03 Workspace Overview`
- `04 Investigation`
- `05 Research Record`
- `06 Operations`
- `07 Review and Governance`
- `08 Team and Settings`
- `09 System`

Recorded artifact:

- File URL: [AGORA UI Audit + Redesign - 2026-03-11](https://www.figma.com/design/jLSN22ajGiadKjsJvuTOnK)
- File key: `jLSN22ajGiadKjsJvuTOnK`

Note:

- The Figma file was created successfully and the initial current-state capture completed.
- Additional current-state/redesign capture tabs were launched against the routes listed at the top of this report.
- Post-capture node-link extraction was blocked by the Figma MCP tool-call quota for the current seat, so file-level links are recorded here and node-level links should be appended in a follow-up when the quota resets.

## 16. Implementation-aware handoff for Codex

### Screen-level handoff

- Portfolio
  - Purpose: rank workspaces by urgency and maintainers' attention
  - User goal: decide where to go first
  - Main blocks: KPI strip, watchlist, trend module, ranked workspace cards
  - Primary actions: open workspace, switch saved view, filter by risk
  - States: healthy portfolio, mixed-risk, empty portfolio
  - Data dependencies: workspaces, blockers, tasks, critiques, rule checks, phase metadata
  - Reusable parts: KPI card, watchlist row, workspace card, saved-view filter

- Workspace Overview
  - Purpose: summarize health and gate readiness for one workspace
  - User goal: decide whether to investigate, assign work, or review governance
  - Main blocks: KPI strip, blocker queue, gate strip, recent critical changes
  - Primary actions: open investigation, open review queue, assign task
  - States: healthy, blocked, partially seeded
  - Data dependencies: critiques, rule checks, tasks, events, logs, claims, artifacts
  - Reusable parts: gate strip, blocker row, signal digest

- Investigation
  - Purpose: unify artifacts, claims, search, and provenance
  - User goal: inspect evidence and understand why a workspace is blocked
  - Main blocks: search/filter builder, result list, detail panel, provenance chain
  - Primary actions: open artifact, compare evidence, jump to claim or draft
  - States: results, empty search, stale/missing evidence
  - Data dependencies: search, artifacts, artifact versions, evidence resolver, claims, critiques
  - Reusable parts: query builder, result card, detail panel, provenance node

- Research Record
  - Purpose: review claims and drafts together
  - User goal: assess confidence and citation coverage in one reading flow
  - Main blocks: draft summary, reading pane, claims table, coverage indicators
  - Primary actions: open citation, update draft, create or review claim
  - States: no draft, draft ready, coverage incomplete
  - Data dependencies: drafts, draft versions, claims, evidence, critiques, gate status
  - Reusable parts: reading pane, claims table, coverage chip

- Operations
  - Purpose: manage requests, tasks, and operational history
  - User goal: unblock execution work fast
  - Main blocks: request pipeline, task queue, signal digest
  - Primary actions: open request detail, update task, jump to affected artifact
  - States: quiet queue, active queue, blocked queue
  - Data dependencies: requests, tasks, logs, events, sandbox/rule-check status
  - Reusable parts: stage card, work row, timeline digest

- Review and Governance
  - Purpose: concentrate critiques, rule checks, and sign-off readiness
  - User goal: make or prepare governance decisions
  - Main blocks: decision queue, critique lanes, gate matrix
  - Primary actions: resolve critique, rerun check, open draft section
  - States: pass, warn, fail, pending review
  - Data dependencies: critiques, rule checks, gate status, drafts, claims
  - Reusable parts: governance lane, gate cell, decision row

### Suggested route structure

- `/projects`
- `/projects/:workspaceId/overview`
- `/projects/:workspaceId/investigation`
- `/projects/:workspaceId/research-record`
- `/projects/:workspaceId/operations`
- `/projects/:workspaceId/review`
- `/projects/:workspaceId/settings`

### Suggested component hierarchy

- `AppShell`
- `WorkspaceCommandRail`
- `WorkspaceStatusRail`
- `MetricCluster`
- `AlertDigest`
- `EvidenceExplorer`
- `ResearchRecordPane`
- `OperationsQueue`
- `GovernanceBoard`
- `SettingsSections`

## 17. Prioritized roadmap

1. Restructure IA and shipping route hierarchy around overview, investigation, research record, operations, review, and settings.
2. Replace the current workspace landing tab with a real summary-first overview.
3. Unify artifacts, claims, drafts, search, and provenance into one investigation model.
4. Build a review and governance queue that treats critiques and rule checks as one decision flow.
5. Normalize the design system and state patterns across tables, cards, drawers, forms, and banners.
6. Move or demote raw creation forms so overview screens stop competing with authoring controls.
