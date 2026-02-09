# Checklist: UI Verification

Date: 2026-02-09
Prompt packet: `prompt-06-ui-e2e-verification-loop` (DIR-07 UI critical-flow verification)
Objective anchor: `Docs/manifest/00_overview.md#Core Objective`

## Bet Tracking

- [x] Appetite set (`medium`) for this packet.
  - Now: prove deterministic critical-flow coverage for login -> workspace -> claims/drafts provenance drill-down (`downhill`) and close cross-browser matrix gap.
  - Not now: visual-regression expansion (`large`).

## Stage 0: Command Map

- [x] Canonical command map includes the UI packet commands in `Docs/manifest/09_runbook.md`.
  - `CMD-01`: `make up`
  - `CMD-04`: `make dev-core-api`
  - `CMD-13`: `make test-e2e`
  - `CMD-21`: `npm --prefix apps/web run dev`
  - `CMD-22`: `npm --prefix apps/web run build`
  - `CMD-23`: `npm --prefix apps/web run smoke:artifact-viewer`
  - `CMD-30`: `npm --prefix apps/web run smoke:artifact-viewer:matrix`
  - `CMD-31`: `npm --prefix apps/web run smoke:artifact-viewer:mobile`
  - `CMD-02`: `make down`
- [x] Runtime assumptions captured for packet execution.
  - Core API reachable at `http://localhost:8000`.
  - Vite dev server reachable at `http://localhost:3000`.
  - Docker infra started before UI smoke run.

## Stage 1: Capability Inventory

- [x] **Auth + route guard**
  - Routes/screens: `/login`, `/projects`, `/projects/:workspaceId/:tab`
  - UI entry code paths: `apps/web/src/App.jsx`, `apps/web/src/pages/LoginPage.jsx`
  - Data/API dependencies: `POST /auth/moltbook`, `POST /auth/verify`, `GET /agents/me`
  - Evidence: `apps/web/scripts/smoke_artifact_viewer.mjs` dev-login path.

- [x] **Projects list + project creation**
  - Routes/screens: `/projects`
  - UI entry code paths: `apps/web/src/pages/ProjectsPage.jsx`, `apps/web/src/components/CreateWorkspaceModal.jsx`
  - Data/API dependencies: `GET /workspaces`, `POST /workspaces`
  - Evidence: smoke script creates deterministic workspace via API and navigates to it in UI.

- [x] **Workspace audit tabs (overview/tasks/timeline/artifacts/claims/drafts/rule-checks/critiques)**
  - Routes/screens: `/projects/:workspaceId/:tab`
  - UI entry code paths: `apps/web/src/pages/WorkspacePage.jsx`
  - Data/API dependencies: workspace, artifacts, claims, drafts, logs/events, rule-checks, critiques endpoints.
  - Evidence: tab navigation checks in smoke flow and existing e2e workflow coverage under `tests/e2e/workflows/`.

- [x] **Artifact viewer rendering**
  - Routes/screens: workspace artifacts panel + provenance drill-down cards
  - UI entry code paths: `apps/web/src/components/ArtifactViewer.jsx`, `apps/web/src/pages/WorkspacePage.jsx`
  - Data/API dependencies: `GET /artifacts/{id}`, `GET /artifacts/{id}/versions`, `GET /artifact-versions/{id}/view`
  - Evidence: smoke flow validates viewer load and fails on `.artifact-viewer-error`.

- [x] **Evidence resolver drawer + provenance drill-down**
  - Routes/screens: claims evidence buttons + drafts cite chips
  - UI entry code paths: `apps/web/src/components/EvidenceDrawer.jsx`, `apps/web/src/pages/WorkspacePage.jsx`
  - Data/API dependencies: `GET /evidence/resolve`
  - Evidence: smoke flow opens drawer, validates snippet render, triggers `Open Artifact Version`.

## Stage 2: Critical Flows

- [x] **Flow 1: Dev login to authenticated workspace navigation**
  - Preconditions: infra and core-api running; Vite dev mode enabled.
  - Steps:
    1. Open `/login`.
    2. Click `Dev Login`.
    3. Wait for redirect to `/projects`.
  - Expected results: auth token stored, projects route accessible.
  - Failure signals: login error banner, redirect timeout.
  - Gating: none.

- [x] **Flow 2: Deterministic workspace + artifact fixture creation**
  - Preconditions: authenticated token is available.
  - Steps:
    1. Create workspace through API.
    2. Create log artifact + version.
    3. Create claim and bind evidence pointer.
    4. Create draft + cited version marker.
  - Expected results: workspace contains artifacts, claim evidence, and draft citation data.
  - Failure signals: non-2xx responses from create endpoints.
  - Gating: none.

- [x] **Flow 3: Claim evidence provenance drill-down**
  - Preconditions: workspace contains claim evidence pointer.
  - Steps:
    1. Navigate to `Claims` tab.
    2. Click `Evidence 1`.
    3. Confirm resolver snippet visible.
    4. Click `Open Artifact Version`.
  - Expected results: provenance card opens exact artifact/version viewer without Not Found/error states.
  - Failure signals: resolver errors, missing snippet, `.artifact-viewer-error`.
  - Gating: none.

- [x] **Flow 4: Draft citation provenance drill-down**
  - Preconditions: workspace contains draft cite marker.
  - Steps:
    1. Navigate to `Drafts` tab.
    2. Click cite chip.
    3. Click `Open Artifact Version`.
  - Expected results: provenance viewer opens and renders cited artifact content.
  - Failure signals: cite chip missing, evidence drawer missing, viewer error.
  - Gating: none.

- [x] **Flow 5: Artifact tab viewer load**
  - Preconditions: workspace contains at least one artifact.
  - Steps:
    1. Navigate to `Artifacts` tab.
    2. Select seeded artifact row.
  - Expected results: artifact viewer loads selected artifact data.
  - Failure signals: missing artifact list or viewer error container.
  - Gating: none.

## Stage 3-4: Automation + Debug Loop Outcome

- [x] Existing Playwright smoke runner hardened (no new framework introduced).
  - File: `apps/web/scripts/smoke_artifact_viewer.mjs`
  - Improvement: deterministic fixture creation and provenance validations for claims + drafts.
- [x] Cross-browser matrix wiring added for Chromium/Firefox/WebKit.
  - Files: `apps/web/package.json`, `.github/workflows/ci.yml`
  - Verification: CI job `cmd-30-ui-smoke-cross-browser` and `smoke:artifact-viewer:matrix` script.
- [x] Mobile-width tab matrix wiring added for all workspace tabs.
  - Files: `apps/web/scripts/smoke_artifact_viewer.mjs`, `apps/web/package.json`, `.github/workflows/ci.yml`
  - Verification: CI job `cmd-31-ui-smoke-mobile` and `smoke:artifact-viewer:mobile` script.
- [x] No open failure cluster after rerun; root-cause loop stayed `downhill`.
  - Verify: `npm --prefix apps/web run smoke:artifact-viewer` (PASS, 2026-02-08).

## Stage 5: Polish Scope

- [x] No additional polish pass needed for correctness/stability in this packet.
- [x] Cross-browser smoke matrix (`chromium`/`firefox`/`webkit`) is now automated.
  - Evidence path: `CMD-30` (`npm --prefix apps/web run smoke:artifact-viewer:matrix`) and CI job `cmd-30-ui-smoke-cross-browser`.
- [x] Mobile-width layout verification for all workspace tabs is now automated.
  - Evidence path: `CMD-31` (`npm --prefix apps/web run smoke:artifact-viewer:mobile`) and CI job `cmd-31-ui-smoke-mobile`.

## Final Verification

- [x] `npm --prefix apps/web run build` (PASS, 2026-02-09)
- [x] `make up` (PASS, 2026-02-09)
- [x] `npm --prefix apps/web run smoke:artifact-viewer` (PASS, 2026-02-08)
- [x] `AGORA_SMOKE_BROWSER=chromium npm --prefix apps/web run smoke:artifact-viewer` (PASS, 2026-02-09)
- [x] `AGORA_CORE_API_URL=http://localhost:8000 AGORA_WEB_BASE_URL=http://localhost:3100 npm --prefix apps/web run smoke:artifact-viewer:matrix` (PASS, 2026-02-09)
- [x] `AGORA_CORE_API_URL=http://localhost:8000 AGORA_WEB_BASE_URL=http://localhost:3100 npm --prefix apps/web run smoke:artifact-viewer:mobile` (PASS, 2026-02-09)
- [x] `rg -n "cmd-30-ui-smoke-cross-browser|cmd-31-ui-smoke-mobile|smoke:artifact-viewer:matrix|smoke:artifact-viewer:mobile|firefox|webkit" .github/workflows/ci.yml apps/web/package.json` (PASS, 2026-02-09)
- [x] `make test-e2e` (PASS, 2026-02-08)
- [x] `make down` (PASS, 2026-02-09)
