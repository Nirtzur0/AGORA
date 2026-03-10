# UI Verification Final Report

Date: 2026-02-09
Prompt packet: `prompt-06-ui-e2e-verification-loop` (DIR-07)
Objective anchor: `Docs/manifest/00_overview.md#Core Objective`

## 1) UI Entry Points and Run Commands

UI/runtime entrypoints:
- `apps/web/src/main.jsx`: React mount entry.
- `apps/web/src/App.jsx`: router + auth guard wiring.
- `apps/web/src/pages/LoginPage.jsx`: token verification and dev-login behavior.
- `apps/web/src/pages/WorkspacePage.jsx`: core audit tabs and provenance drill-down surfaces.

Run commands used in this packet:
- `make up`
- `make dev-core-api`
- `npm --prefix apps/web run dev`
- `npm --prefix apps/web run smoke:artifact-viewer`
- `npm --prefix apps/web run smoke:artifact-viewer:matrix`
- `npm --prefix apps/web run smoke:artifact-viewer:mobile`
- `npm --prefix apps/web run build`
- `make test-e2e`
- `make down`

Command map source: `Docs/manifest/09_runbook.md` (`CMD-01`, `CMD-02`, `CMD-04`, `CMD-13`, `CMD-21`, `CMD-22`, `CMD-23`, `CMD-30`, `CMD-31`).

## 2) Capability Inventory Summary

Validated:
- Auth + guarded routing (`/login` -> `/projects` -> `/projects/:workspaceId/:tab`).
- Projects/workspace surfaces.
- Artifact viewer load path.
- Claims evidence drawer resolution and provenance drill-down.
- Draft citation evidence drawer and provenance drill-down.

Remaining / gated:
- Cross-browser visual regression snapshot diffs are still out of scope.

## 3) Critical Flows Validation

- Flow A: Dev login and route guard.
  - Evidence: `apps/web/scripts/smoke_artifact_viewer.mjs` waits for `/projects` redirect after `Dev Login`.
- Flow B: Deterministic fixture setup (workspace/artifact/claim/draft).
  - Evidence: smoke script seeds all required entities via API before UI assertions.
- Flow C: Claims evidence -> provenance artifact viewer.
  - Evidence: smoke script clicks `Evidence 1`, checks snippet, then `Open Artifact Version` and asserts no viewer error.
- Flow D: Draft cite chip -> provenance artifact viewer.
  - Evidence: smoke script opens draft cite chip, evidence drawer, then provenance viewer.
- Flow E: Artifact tab viewer health.
  - Evidence: smoke script opens `Artifacts`, selects seeded artifact, and validates viewer state.

## 4) Tests Added or Changed

- Updated `apps/web/scripts/smoke_artifact_viewer.mjs`.
  - Rationale:
    - Removed dependence on pre-existing workspace/artifact data.
    - Added deterministic setup through authenticated API calls.
    - Added claims and drafts provenance drill-down assertions.
    - Added browser parameterization (`AGORA_SMOKE_BROWSER`) for Chromium/Firefox/WebKit execution.
    - Added viewport parameterization (`AGORA_SMOKE_VIEWPORT`) and mobile-mode all-tab reachability assertions.
    - Kept diagnostics strong by failing on resolver/viewer error states.
- Updated `apps/web/package.json` smoke scripts.
  - Added browser-specific commands, `smoke:artifact-viewer:matrix`, and `smoke:artifact-viewer:mobile`.
- Updated `.github/workflows/ci.yml`.
  - Added `cmd-30-ui-smoke-cross-browser` matrix gate and per-browser screenshot artifacts.
  - Added `cmd-31-ui-smoke-mobile` gate and mobile screenshot artifact.

No framework additions were required; existing Playwright usage was retained.

## 5) Bugs Found and Fixed

- Symptom: smoke flow could fail when selected workspace had no artifacts/claims/drafts.
  - Root cause: script depended on ambient repo data instead of deterministic setup.
  - Fix: create isolated workspace + fixtures during test run (`apps/web/scripts/smoke_artifact_viewer.mjs`).
  - Regression coverage: rerun smoke script and assert provenance/drill-down flows.

## 6) How to Run Everything

From repo root:
- Infra up: `make up`
- Core API: `make dev-core-api`
- Web dev: `npm --prefix apps/web run dev`
- UI smoke flow: `npm --prefix apps/web run smoke:artifact-viewer`
- UI smoke matrix: `npm --prefix apps/web run smoke:artifact-viewer:matrix`
- UI mobile smoke: `npm --prefix apps/web run smoke:artifact-viewer:mobile`
- Build check: `npm --prefix apps/web run build`
- Existing e2e suite: `make test-e2e`
- Infra down: `make down`

## 7) Gating

- Cross-browser smoke matrix is now automated via `CMD-30`.
  - Scope: deterministic provenance drill-down + artifact viewer flows across Chromium/Firefox/WebKit.
  - CI gate: `cmd-30-ui-smoke-cross-browser` publishes `/tmp/agora-smoke-artifact-viewer-<browser>.png` artifacts.
- Responsive/mobile tab coverage is now automated via `CMD-31`.
  - Scope: mobile viewport smoke validates all workspace tabs and provenance flows.
  - CI gate: `cmd-31-ui-smoke-mobile` publishes `/tmp/agora-smoke-artifact-viewer-chromium-mobile.png`.

## Verification Snapshot

- `npm --prefix apps/web run build` -> PASS (2026-02-09)
- `make up` -> PASS (2026-02-09)
- `npm --prefix apps/web run smoke:artifact-viewer` -> PASS (2026-02-09)
- `npm --prefix apps/web run smoke:artifact-viewer:mobile` -> PASS (2026-02-09)
- `npm --prefix apps/web run smoke:artifact-viewer:matrix` -> PASS (2026-02-09)
- `rg -n "cmd-30-ui-smoke-cross-browser|cmd-31-ui-smoke-mobile|smoke:artifact-viewer:matrix|smoke:artifact-viewer:mobile|firefox|webkit" .github/workflows/ci.yml apps/web/package.json` -> PASS (2026-02-09)
- `make test-e2e` -> PASS (2026-02-08)
- `make down` -> PASS (2026-02-09)
