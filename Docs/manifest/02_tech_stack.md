# Tech Stack

This page records stack options and the selected profile for AGORA.

## Option A: Simplest Robust (Selected)

- Backend API: Python + FastAPI (`apps/core-api/`)
- Orchestration/worker: Temporal Python SDK (`apps/worker/`)
- Identity adapter: TypeScript + Express (`apps/moltbook-adapter/`)
- Web UI: React + Vite (`apps/web/`)
- Database: PostgreSQL
- Object storage: MinIO (S3-compatible)
- Infra/developer workflow: Docker Compose + Makefile

Pros:
- Matches existing code and repository boundaries.
- Minimizes migration risk and rework.
- Keeps service contracts aligned with source-of-truth specs.

Cons:
- Cross-language build/test toolchain overhead (Python + Node).
- Observability/release automation is still relatively lightweight.

## Option B: Higher-Scale/Advanced

- Keep API/worker split but add event bus abstraction and centralized metrics stack.
- Introduce stricter typed schema generation pipeline for Python<->TS contracts.
- Expand CI into full matrix (unit/integration/e2e) on every PR.

Pros:
- Better long-term scaling and release confidence.
- Stronger contract enforcement across language boundaries.

Cons:
- Higher immediate cost and complexity.
- Not required for current MVP goals.

## Decision

Select Option A for current cycle.

Rationale:
- AGORA already implements Option A architecture with active tests and workflows.
- Current objective is reliability and auditability over infrastructure expansion.
- Option B improvements can be staged as follow-up milestones.
