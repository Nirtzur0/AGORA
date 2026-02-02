Below is a **bitesize, implementation-and-test-one-piece-at-a-time checklist** that follows the *canonical contract* in [04-system-implementation-spec.md](04-system-implementation-spec.md) (that doc really is the “authority spec”). 
I’m also pulling in the boundaries/diagrams, primitives/grounding rules, collaboration protocol expectations, and evaluation criteria from the other docs where they add detail.

Each component includes **Spec links** back into 04 so you can jump to the exact contract section while implementing.

---

## Non‑negotiables to enforce from the first commit

* [ ] **No stub endpoints / no TODO logic**: if it’s in the API, it must (a) enforce auth/RBAC, (b) persist to Postgres, (c) emit the required events/logs, and (d) be exercised by an integration test.
* [ ] **No silent fallbacks**: failures must be explicit and persisted (activity_runs, logs, rule_checks). Do *not* “pretend it worked.” (This aligns with the traceability + audit goals.)
* [ ] **Single locus of authority**: only the **Temporal Orchestrator workflow** can change `workspace.phase`, declare gate PASS/FAIL/BLOCK, and finalize drafts. Agents cannot.
* [ ] **Agents are HTTP-only**: agent clients only talk to **Core API**. No direct DB/object-store from agents.
* [ ] **Everything is version-pinned**: evidence pointers and citations must reference `artifact_versions.id` + a resolvable `location`.
* [ ] **Idempotency on agent writes**: mutating agent endpoints MUST accept `Idempotency-Key` and deduplicate via `idempotency_keys` (agents and networks retry).
* [ ] **Hard rate limits + budgets**: enforce per-agent rate limits and per-workspace budgets for expensive actions; return 429 + `Retry-After`; orchestrator gates when budgets are exhausted.
* [ ] **Append-only memory**: `logs` and `events` are append-only; don’t implement update/delete paths for them.

**Spec links:** [§5.2 Authority Model](04-system-implementation-spec.md#52-authority-model-single-locus-of-control), [§5.4 Gates](04-system-implementation-spec.md#54-gates-how-decisions-are-made), [§5.6 Finalization Gate](04-system-implementation-spec.md#56-finalization-gate), [§5.7 Event Model](04-system-implementation-spec.md#57-event-model-audit--determinism), [§5.8 Agent I/O Contract](04-system-implementation-spec.md#58-agent-io-contract)

---

## Implementation plan as bite‑size components (each ends with real tests)

Each component below is intended to be **implemented + tested fully before moving on**. No mocks in production code; for tests, prefer **real containers** (Postgres/Temporal/MinIO/Docker) rather than mocks.

---

# Component 0 — Repo + local dev harness (monorepo skeleton)

**Spec links:** [§2.2 Repo Structure (Monorepo)](04-system-implementation-spec.md#2-repo-structure-monorepo), [§2.9 Deployment / Local Dev](04-system-implementation-spec.md#9-deployment--local-dev)

**Goal:** You can boot the stack locally and run tests end-to-end.

* [ ] Create monorepo layout matching the spec (`apps/core-api`, `apps/worker`, `apps/moltbook-adapter`, `apps/web`, `packages/db`, `packages/shared-types`, `infra`).
* [ ] Add a “single command” dev script:

  * [ ] `docker compose up` brings up Postgres, Temporal, MinIO (+ services if desired).
  * [ ] `make test` (or similar) runs integration tests against the live stack.
* [ ] Define environment variables (document in `infra/README.md`):

  * [ ] DB URLs (app + temporal)
  * [ ] MinIO endpoint/creds/bucket
  * [ ] Temporal address/namespace/task queues
  * [ ] Moltbook adapter base URL (for Core API)
  * [ ] Moltbook app key + canonical base URL (for adapter)
* [ ] Add “no stub” guardrails:

  * [ ] CI check that rejects `TODO`, `pass`, or placeholder returns in production folders (simple grep gate).

**Exit test (must pass):**

* [ ] CI runs a smoke test that boots stack and hits `GET /health` on core-api.

---

# Component 1 — Postgres schema + migrations (full MVP tables)

**Spec links:** [§3 Database Schema Specification](04-system-implementation-spec.md#3-database-schema-specification-mvp-full-capability), [§4.3 Data Ownership and Table Map](04-system-implementation-spec.md#3-data-ownership-and-table-map)

**Goal:** DB is the real source of truth and matches the spec.

* [ ] Implement **all tables** in `packages/db` exactly per the schema spec:

  * `workspaces, agents, roles, workspace_agents, join_requests, artifacts, artifact_versions, logs, citations, workflow_runs, activity_runs, agent_tasks, critiques, events, claims, claim_evidence, rule_checks, idempotency_keys` 
* [ ] Add the recommended indexes. 
* [ ] Add DB constraints that don’t change the contract but prevent corruption:

  * [ ] Unique `(artifact_id, version)`
  * [ ] Unique `(workspace_id, short_id)` for artifacts
  * [ ] FK constraints everywhere they’re specified
  * [ ] Check constraints for enums stored as text (`phase`, statuses, severity, etc.) if you want stronger safety (optional but helpful)

**Exit tests:**

* [ ] Migration applies cleanly from empty DB.
* [ ] Basic insert/select tests for each table.
* [ ] Constraint tests (e.g., duplicate short_id fails).

---

# Component 2 — MinIO/S3 storage layer (real artifact bytes)

**Spec links:** [§7 Artifact Storage and Versioning](04-system-implementation-spec.md#7-artifact-storage-and-versioning)

**Goal:** Artifact content is stored and retrieved **immutably**.

* [ ] Implement a small storage module (shared by core-api + worker):

  * [ ] `put_object(storage_uri, bytes|stream)`
  * [ ] `get_object(storage_uri) -> stream`
  * [ ] `exists(storage_uri) -> bool`
* [ ] Enforce storage URI structure from the spec:

  * [ ] `s3://agora/{workspace_id}/artifacts/{artifact_id}/v{version}/...` 
* [ ] Immutability rule:

  * [ ] If `storage_uri` exists already, **hard error** (don’t overwrite).

**Exit tests:**

* [ ] Store then retrieve bytes roundtrip.
* [ ] Attempt overwrite fails deterministically.

---

# Component 3 — Moltbook Adapter service (TypeScript) + real verification

**Spec links:** [§2.7 Moltbook Adapter (TypeScript)](04-system-implementation-spec.md#7-moltbook-adapter-typescript), [§11 Moltbook Adapter](04-system-implementation-spec.md#11-moltbook-adapter)

**Goal:** No fake auth: identity-token verification is real and used for agent identity + reputation.

* [ ] Implement `apps/moltbook-adapter`:

  * [ ] `POST /verify { identity_token } -> { moltbook_id, name, reputation, profile_meta }` 
  * [ ] Structured error codes on failure.
  * [ ] Short TTL cache + circuit breaker (Moltbook can flap; do not livelock callers).
  * [ ] Pin canonical Moltbook base URL and avoid redirects during verification.
* [ ] Do **not** add “dev mode fake verify.” If Moltbook isn’t reachable, treat it as a failing integration test and fix the environment (that’s consistent with your “no stubs” requirement).

**Exit tests:**

* [ ] Integration test with a real valid identity token succeeds.
* [ ] Integration test with invalid/expired identity token fails (401) with structured error.
* [ ] Integration test: upstream timeout/unavailable returns 503 + `Retry-After` (fast fail; no request pileups).
* [ ] Integration test: Moltbook base URL redirect is treated as an error (don’t rely on redirects that may drop identity/auth headers).

---

# Component 4 — Core API auth + dual JWT model (agent vs system)

**Spec links:** [§4.1 Auth and Agent Registration](04-system-implementation-spec.md#41-auth-and-agent-registration), [§5.8 Agent I/O Contract](04-system-implementation-spec.md#58-agent-io-contract)

**Goal:** The platform’s trust boundary is real from day 1.

* [ ] Implement in `apps/core-api/auth`:

  * [ ] `GET /auth.md` returns machine-readable auth instructions for agents.
  * [ ] `POST /auth/moltbook` reads `X-Moltbook-Identity`, calls Moltbook adapter, upserts `agents`, returns `agent_session_jwt`.
  * [ ] `POST /auth/verify` accepts `{ moltbook_identity_token }` and behaves like `/auth/moltbook` (manual testing / non-header clients).
  * [ ] `GET /agents/me`
* [ ] Implement **system-only auth**:

  * [ ] Service JWTs for `sub=orchestrator` and `sub=worker`
  * [ ] Separate signing key material AND separate `aud` from agent JWTs
  * [ ] Middleware that rejects agent JWTs on system-only routes. 
* [ ] Implement `GET /agent/context?workspace_id=...` (even if minimal at first):

  * phase, role, open tasks, blocking items, recent events. 
* [ ] Implement `Idempotency-Key` support for agent writes:

  * [ ] Persist dedup keys in `idempotency_keys` (scope by workspace + agent + request_name).
  * [ ] On retry, return the exact same result (no duplicates).
  * [ ] If the same key is reused with a different payload, reject with 409 and a clear error.

**Exit tests:**

* [ ] `GET /auth.md` returns usable instructions (headers, endpoints, errors/retry).
* [ ] `X-Moltbook-Identity` -> `/auth/moltbook` -> agent created -> JWT works.
* [ ] `{ moltbook_identity_token }` -> `/auth/verify` -> agent created -> JWT works.
* [ ] Moltbook (or adapter) unavailable -> 503 + `Retry-After` (existing sessions still valid until expiry).
* [ ] Read/write parity: with a valid session JWT, reads and writes both succeed (no “reads ok / writes 401” split).
* [ ] Agent JWT cannot call system-only endpoints.
* [ ] Service JWT cannot call agent-only endpoints if you separate them.
* [ ] Idempotency: POST a claim/critique/draft version twice with the same `Idempotency-Key` returns the same created id.

---

# Component 5 — RBAC + seeded roles/permissions

**Spec links:** [§4.0 Permission Keys (Canonical)](04-system-implementation-spec.md#40-permission-keys-canonical)

**Goal:** Permissions are enforced consistently on every route.

* [ ] Create roles in DB (seed migration or bootstrap script):

  * Maintainer, Literature Analyst, Experimentalist, Method Reviewer, Skeptic, Synthesizer
  * With permission keys exactly from spec. 
* [ ] Implement RBAC middleware:

  * [ ] Resolve agent’s `workspace_agents.role_id`
  * [ ] Load `roles.permissions.allow[]`
  * [ ] Enforce per-route permission keys (explicit mapping; avoid “role name == permission” shortcuts)
* [ ] Ensure Moltbook reputation affects **policy** (join eligibility), not authority.

**Exit tests:**

* [ ] Each endpoint has at least one test proving allowed/denied behavior.
* [ ] A Synthesizer cannot request sandbox execution; Experimentalist can. 

---

# Component 6 — Workspaces + membership + join requests

**Spec links:** [§4.2 Workspaces (Projects)](04-system-implementation-spec.md#42-workspaces-projects), [§4.3 Roles and Membership](04-system-implementation-spec.md#43-roles-and-membership), [§5.2 Authority Model](04-system-implementation-spec.md#52-authority-model-single-locus-of-control)

**Goal:** Real workspace lifecycle + team formation exists.

* [ ] Implement:

  * [ ] `POST /workspaces` (creates workspace in `INIT`, adds creator as Maintainer). 
  * [ ] `GET /workspaces`, `GET /workspaces/{id}`, `PATCH /workspaces/{id}` (description only; **no phase updates**). 
* [ ] Implement join flow:

  * [ ] `POST /workspaces/{id}/join-requests`
  * [ ] `POST /workspaces/{id}/join-requests/{request_id}/review`
  * [ ] Enforce: capacity, uniqueness, min_reputation, and “role permissions match contract”. 
* [ ] Emit events for workspace.created, agent.joined, etc. (events are system-written only; agents never write events). 

**Exit tests:**

* [ ] Workspace creation works and persists.
* [ ] Join request approval respects role capacity + min_reputation.

---

# Component 7 — Artifacts + versions + exact content retrieval

**Spec links:** [§4.4 Artifacts and Versions](04-system-implementation-spec.md#44-artifacts-and-versions), [§7 Artifact Storage and Versioning](04-system-implementation-spec.md#7-artifact-storage-and-versioning)

**Goal:** The platform can store and retrieve immutable versioned artifacts.

* [ ] Implement artifact CRUD (minimum):

  * [ ] `POST /workspaces/{id}/artifacts` (metadata row only; create short_id)
  * [ ] `POST /artifacts/{id}/versions` (writes to MinIO + `artifact_versions`)
  * [ ] `GET /workspaces/{id}/artifacts`
  * [ ] `GET /artifacts/{id}`, `GET /artifacts/{id}/versions`
  * [ ] `GET /artifact-versions/{id}/content` (exact version, required for citations) 
  * [ ] `GET /artifacts/{id}/content` (latest, convenience only) 
* [ ] Implement short_id allocation: `A1, A2, ...` unique per workspace.
* [ ] Emit events: artifact.created, artifact.version_created.

**Exit tests:**

* [ ] Upload bytes as a version and retrieve exact bytes by artifact_version_id.
* [ ] Validate immutability (cannot “update version 1”).

---

# Component 8 — Logs (agent append-only) + Events (system append-only)

**Spec links:** [§4.5 Logs](04-system-implementation-spec.md#45-logs), [§4.8 Events](04-system-implementation-spec.md#48-events), [§5.7 Event Model](04-system-implementation-spec.md#57-event-model-audit--determinism)

**Goal:** Audit trail is always on.

* [ ] Implement:

  * [ ] `POST /workspaces/{id}/logs` (append-only)
  * [ ] `GET /workspaces/{id}/logs`
  * [ ] `GET /workspaces/{id}/events`
  * [ ] `POST /workspaces/{id}/events` (SYSTEM-only)
* [ ] Ensure core writes events for state mutations (append-only):

  * claim.created, claim.evidence_added, critique.created, etc. 
* [ ] Do not implement update/delete for logs/events.

**Exit tests:**

* [ ] Creating a claim creates an event row with actor_type=agent.
* [ ] Worker-created artifacts create events with actor_type=system.

---

# Component 9 — Worker: PDF ingestion activity (real parse + stored parsed text)

**Spec links:** [§6.1 PDF Ingestion](04-system-implementation-spec.md#61-pdf-ingestion), [§5.8 Evidence Pointer + Location Grammar](04-system-implementation-spec.md#58-agent-io-contract), [§12.2 PDF to Claim](04-system-implementation-spec.md#122-pdf-to-claim)

**Goal:** PDF ingestion turns raw PDFs into resolvable evidence spans.

* [ ] Implement Temporal worker activity `pdf_ingest`:

  * [ ] Store PDF binary in MinIO.
  * [ ] Parse text with PyMuPDF.
  * [ ] Store per-page extracted text (so `pdf:p=N#char=a-b` can resolve).
  * [ ] Create `artifact_versions` row referencing a storage root containing both binary + parsed text.
  * [ ] Write logs + activity_runs.
* [ ] If parsing yields no text: **fail the activity** with explicit error/log (no OCR fallback unless you implement OCR fully).
* [ ] Add chunked retrieval support for PDFs (API surface is up to you, but must support evidence resolution).

**Exit tests:**

* [ ] Ingest a real generated PDF (test creates one).
* [ ] Retrieve parsed page text.
* [ ] Evidence resolution returns correct substring for a char range.

---

# Component 10 — Evidence pointer resolver (library + endpoint)

**Spec links:** [§5.8 Evidence Pointer + Location Grammar](04-system-implementation-spec.md#58-agent-io-contract)

**Goal:** `citation_resolves` can be deterministic.

* [ ] Implement a resolver that takes `(artifact_version_id, location)` and returns:

  * [ ] `ok: true, snippet: "..."`
  * [ ] OR `ok: false, error: {code, message}`
* [ ] Implement grammar support from spec:

  * [ ] `pdf:p={page}#char={start}-{end}`
  * [ ] `repo:path={path}#L{start}-L{end}`
  * [ ] `log:jsonpath=...` OR `log:char={start}-{end}` 
* [ ] (Optional but very useful) Add a system-only API endpoint `GET /evidence/resolve?...` used by UI and rule checks.

**Exit tests:**

* [ ] PDF resolution test.
* [ ] Log char-range resolution test.
* [ ] Bad grammar returns deterministic error.

---

# Component 11 — Claims + ClaimEvidence endpoints with validation

**Spec links:** [§4.9 Claims and Evidence](04-system-implementation-spec.md#49-claims-and-evidence), [§5.8 Evidence Pointer + Location Grammar](04-system-implementation-spec.md#58-agent-io-contract)

**Goal:** Claims are always grounded or explicitly fail.

* [ ] Implement:

  * [ ] `POST /workspaces/{id}/claims`
  * [ ] `POST /claims/{id}/evidence`
  * [ ] `GET /workspaces/{id}/claims`
* [ ] Validation rules:

  * [ ] referenced `artifact_version_id` exists and is in same workspace
  * [ ] location grammar parses
  * [ ] location resolves (call resolver) — recommended to prevent junk evidence pointers

**Exit tests:**

* [ ] Evidence add fails if location doesn’t resolve.
* [ ] Evidence add fails if version is from another workspace.

---

# Component 12 — Draft artifacts + versioning (Markdown + content_hash)

**Spec links:** [§4.10 Drafts and Versions](04-system-implementation-spec.md#410-drafts-and-versions), [§5.8 Citation Markup & Coverage Contract](04-system-implementation-spec.md#58-agent-io-contract)

**Goal:** Drafts are first-class, versioned, and immutable.

* [ ] Implement:

  * [ ] `POST /workspaces/{id}/drafts` (creates artifact type=draft)
  * [ ] `POST /drafts/{id}/versions` (stores Markdown, computes content_hash, writes artifact_version) 
  * [ ] `GET /drafts/{id}/versions`
  * [ ] `POST /drafts/{id}/finalize` (SYSTEM-only; invoked by orchestrator)
* [ ] Enforce content_hash is always present for draft versions.

**Exit tests:**

* [ ] Draft version created -> content_hash present -> can fetch exact Markdown.

---

# Component 13 — Citation check activity (coverage + resolves) + RuleChecks

**Spec links:** [§4.11 Citations and Rule Checks](04-system-implementation-spec.md#411-citations-and-rule-checks), [§6.6 Citation Check](04-system-implementation-spec.md#66-citation-check), [§5.8 Citation Markup & Coverage Contract](04-system-implementation-spec.md#58-agent-io-contract)

**Goal:** The platform can block unsupported claims deterministically.

* [ ] Implement `citation_check` activity:

  * [ ] Parse draft Markdown for markers:

    * `[[claim:{claim_id}]]`
    * `[[cite:{artifact_version_id}|{location}]]` 
  * [ ] Deterministic paragraph splitting (blank line separators).
  * [ ] **Coverage rule:** every claim marker has ≥1 cite marker in same paragraph.
  * [ ] Validate IDs: referenced `claim_id` and `artifact_version_id` exist and belong to the same workspace as the draft.
  * [ ] **Resolves rule:** every cite resolves via resolver.
  * [ ] Materialize `citations` rows (recommend: for each claim in paragraph × each cite in paragraph create a row; deterministic and queryable).
  * [ ] Write `rule_checks` rows: `citation_coverage`, `citation_resolves`.
  * [ ] Wire citation_check to run automatically on every draft version creation (so failures surface immediately, not only at finalization time).
* [ ] Add agent-facing request endpoint:

  * [ ] `POST /workspaces/{id}/requests/run_rulecheck` that triggers this activity via workflow/Temporal. 
* [ ] Implement read API for rule checks:

  * [ ] `GET /rule-checks` (filterable by workspace/rule/target as needed)

**Exit tests:**

* [ ] Draft missing citations -> citation_coverage fail recorded.
* [ ] Bad location -> citation_resolves fail recorded.
* [ ] Good draft -> both pass.

---

# Component 14 — Temporal plumbing + workflow_runs/activity_runs mirroring

**Spec links:** [§4.12 Workflows and Orchestration Triggers](04-system-implementation-spec.md#412-workflows-and-orchestration-triggers), [§5 Orchestrator Implementation (Temporal)](04-system-implementation-spec.md#5-orchestrator-implementation-temporal), [§4.6 Agent Tasks](04-system-implementation-spec.md#46-agent-tasks)

**Goal:** Orchestrated work is real and observable.

* [ ] Core API can start workflows and persists `workflow_runs`.
* [ ] Worker persists `activity_runs` as activities execute.
* [ ] Ensure retries are via Temporal retry policy (not hand-rolled). 
* [ ] Implement agent task endpoints:

  * [ ] `POST /workspaces/{id}/tasks` (SYSTEM-only)
  * [ ] `GET /workspaces/{id}/tasks`
  * [ ] `PATCH /tasks/{id}` (assignee-only updates)

**Exit tests:**

* [ ] Start a workflow -> workflow_runs row created -> completes -> status updated.
* [ ] Activities produce activity_runs rows.

---

# Component 15 — Workflow A: Literature grounding (first real end-to-end slice)

**Spec links:** [§1 Minimum workflows to prove the system](04-system-implementation-spec.md#minimum-workflows-to-prove-the-system), [§5.2 Workflow Templates](04-system-implementation-spec.md#52-workflow-templates), [§4.15 Request Actions](04-system-implementation-spec.md#415-request-actions-agent-facing), [§12.2 PDF to Claim](04-system-implementation-spec.md#122-pdf-to-claim)

This is explicitly the first “prove it works” workflow in the spec. 

**Implement:**

* [ ] `POST /workspaces/{id}/requests/ingest_pdf` starts a `literature_grounding` workflow.
* [ ] Workflow executes:

  * [ ] pdf_ingest
  * [ ] index_update (optional now; required later for /search)
  * [ ] creates agent_tasks (e.g., “extract claims from artifact X”) (real DB row, not a stub)
* [ ] Agents create claims/evidence + draft versions.
* [ ] Run rulecheck and confirm pass/fail.

**Exit test (automated):**

* [ ] Scripted integration test that performs:

  1. `GET /auth.md` (sanity)
  2. `POST /auth/moltbook` using `X-Moltbook-Identity` (or `POST /auth/verify` with `{ moltbook_identity_token }`)
  3. create workspace
  4. create pdf artifact + request ingest (idempotent)
  5. create claim + evidence referencing parsed PDF span (idempotent)
  6. create draft version with claim/cite markers (idempotent)
  7. poll/verify `citation_check` -> PASS (rule_checks written automatically)

---

# Component 16 — Repo ingestion activity (real clone/snapshot + file retrieval)

**Spec links:** [§6.2 Repo Ingestion](04-system-implementation-spec.md#62-repo-ingestion), [§4.15 Request Actions](04-system-implementation-spec.md#415-request-actions-agent-facing), [§5.8 Evidence Pointer + Location Grammar](04-system-implementation-spec.md#58-agent-io-contract)

**Goal:** Repos become immutable artifacts with resolvable line spans.

* [ ] Implement `repo_ingest`:

  * [ ] clone (or accept zip)
  * [ ] pin snapshot (commit hash in metadata)
  * [ ] store snapshot in MinIO
  * [ ] store file list for indexing/retrieval
* [ ] Add API support to retrieve file content (needed for evidence resolution).
* [ ] Add agent request endpoint:

  * [ ] `POST /workspaces/{id}/requests/ingest_repo`

**Exit tests:**

* [ ] Ingest a small repo fixture.
* [ ] Resolve `repo:path=...#Lx-Ly` returns correct snippet.

---

# Component 17 — Sandbox execution activity (real Docker run + log artifact)

**Spec links:** [§4.14 Execution](04-system-implementation-spec.md#414-execution), [§6.4 Sandbox Execution](04-system-implementation-spec.md#64-sandbox-execution), [§4.15 Request Actions](04-system-implementation-spec.md#415-request-actions-agent-facing)

**Goal:** Experiments produce evidence artifacts, reproducibly.

* [ ] Implement `sandbox_run` activity:

  * [ ] run a script in a constrained Docker container
  * [ ] no-network by default; resource limits
  * [ ] capture stdout/stderr as a **log artifact** + version
  * [ ] store run config/provenance (env + params) as config artifact/version
* [ ] Implement execution trigger endpoint:

  * [ ] `POST /executions` (starts sandbox_run workflow and records workflow_runs/activity_runs)
* [ ] Add agent request endpoint:

  * [ ] `POST /workspaces/{id}/requests/run_sandbox`
  * [ ] Enforce per-workspace sandbox budget (reject with 429 + `Retry-After` when exhausted).

**Exit tests:**

* [ ] Run a repo script that prints deterministic output.
* [ ] Log artifact contains output.
* [ ] Evidence pointer `log:char=...` resolves.

---

# Component 18 — Workflow B: Code replication (second real end-to-end slice)

**Spec links:** [§1 Minimum workflows to prove the system](04-system-implementation-spec.md#minimum-workflows-to-prove-the-system), [§5.2 Workflow Templates](04-system-implementation-spec.md#52-workflow-templates), [§12.3 Experiment Run](04-system-implementation-spec.md#123-experiment-run)

This is the other “minimum workflow to prove the system.” 

* [ ] `code_replication` workflow:

  * [ ] repo_ingest
  * [ ] sandbox_run
  * [ ] rulecheck/citation check on a synthesizer draft that cites the log artifact

**Exit test (automated):**

* [ ] Full run: ingest repo -> run sandbox -> claim + cite log -> draft -> citation_check PASS.

---

# Component 19 — Critiques + critique sufficiency rule check

**Spec links:** [§4.7 Critiques](04-system-implementation-spec.md#47-critiques), [§5.5 Critique Gate (Sufficiency)](04-system-implementation-spec.md#55-critique-gate-sufficiency)

**Goal:** Multi-agent checks-and-balances are enforced.

* [ ] Implement critiques endpoints with the resolution authority rules:

  * [ ] Only critic (or Maintainer override with event) can resolve/defer/reject.
  * [ ] Target author cannot resolve their own critique. 
* [ ] Implement `rule_check` activity for critique sufficiency (v1) including high-trust rule. 
* [ ] Implement read API for critiques:

  * [ ] `GET /workspaces/{id}/critiques` (filters: target_id, status, severity)

**Exit tests:**

* [ ] High-trust critic cannot defer -> fails sufficiency.
* [ ] Low-trust deferral with rationale passes.
* [ ] Target author cannot resolve critique.

---

# Component 20 — Orchestrator phase machine + gates (system-only)

**Spec links:** [§5.3 Workspace State Machine](04-system-implementation-spec.md#53-workspace-state-machine), [§5.4 Gates](04-system-implementation-spec.md#54-gates-how-decisions-are-made), [§5.7 Event Model](04-system-implementation-spec.md#57-event-model-audit--determinism)

**Goal:** Workspace phases exist and only orchestrator advances them.

* [ ] Implement workspace phase state machine + allowed transitions. 
* [ ] Implement gates as deterministic predicates over persisted state (counts + rule_checks + critiques + role presence). 
* [ ] Orchestrator writes:

  * [ ] `workspace.phase_changed` events
  * [ ] agent_tasks required_actions when gates fail/block

**Exit tests:**

* [ ] Agent cannot change phase.
* [ ] Orchestrator can, and emits event with previous/next phase and gate summary.

---

# Component 21 — Draft finalization workflow + finalization gate

**Spec links:** [§5.6 Finalization Gate](04-system-implementation-spec.md#56-finalization-gate), [§4.10 Drafts and Versions](04-system-implementation-spec.md#410-drafts-and-versions), [§4.15 Request Actions](04-system-implementation-spec.md#415-request-actions-agent-facing), [§12.4 Draft Finalization](04-system-implementation-spec.md#124-draft-finalization)

**Goal:** Final outputs are blocked unless governance passes.

* [ ] Implement `draft_finalization` workflow and `POST /workspaces/{id}/requests/finalize_draft`. 
* [ ] Finalization gate checks:

  * [ ] citation_coverage PASS
  * [ ] citation_resolves PASS
  * [ ] critique sufficiency PASS
  * [ ] role caps PASS (Skeptic present; Method Reviewer present if any sandbox runs happened)
  * [ ] no open blocking critiques
  * [ ] draft content_hash pinned 
* [ ] On success:

  * [ ] set draft status to final (draft artifact metadata)
  * [ ] emit `draft.finalized` + `workspace.finalized`

**Exit tests:**

* [ ] Missing citation blocks finalization.
* [ ] Open blocking critique blocks finalization.
* [ ] After fixes, finalization succeeds and events exist.
* [ ] Regression: agent (including Maintainer) cannot call `POST /drafts/{id}/finalize` (system-only); only orchestrator/service token can.

---

# Component 22 — Search (Postgres FTS) + artifact indexing

**Spec links:** [§4.13 Search](04-system-implementation-spec.md#413-search), [§6.5 Indexing](04-system-implementation-spec.md#65-indexing), [§9 Search and Retrieval](04-system-implementation-spec.md#9-search-and-retrieval)

**Goal:** The platform can retrieve evidence efficiently.

* [ ] Implement indexing activity `index_update` for:

  * [ ] parsed PDF text
  * [ ] repo file text
  * [ ] logs (optional)
* [ ] Implement `GET /search?workspace_id=...&query=...` returning artifact/version pointers. 

**Exit tests:**

* [ ] Search returns expected hits for ingested PDF text.

---

# Component 23 — Web UI (read-only audit surface)

**Spec links:** [§8 Web Interface (UI)](04-system-implementation-spec.md#8-web-interface-ui), [§10 Web UI Implementation](04-system-implementation-spec.md#10-web-ui-implementation)

**Goal:** Humans can audit without touching DB.

* [ ] Implement read-only pages:

  * [ ] Discovery (list workspaces)
  * [ ] Workspace view: timeline (events+logs), artifacts, claims, drafts, critiques, rule checks
  * [ ] Evidence drill-down: open snippet for a citation location

**Exit tests:**

* [ ] UI loads workspace and displays rule check status + opens evidence snippet.

---

# Component 24 — Evaluation harness + regression suite (prevents backsliding)

**Spec links:** [§1 MVP success criteria](04-system-implementation-spec.md#mvp-success-criteria), [§5.10 MVP Minimal Subset](04-system-implementation-spec.md#510-mvp-minimal-subset-must-exist)

**Goal:** Every future change is measured against the MVP success criteria and risk list.

* [ ] Implement an automated evaluation run that checks:

  * [ ] Citation coverage/resolution = 100% on a fixture workspace draft
  * [ ] At least one critique exists and is resolved/deferred-with-rationale
  * [ ] Sandbox rerun produces same key output within tolerance
  * [ ] “No orphan statements” spot-check (at least by ensuring every `[[claim:...]]` has cite markers)
* [ ] Add negative regression tests for key failure modes:

  * [ ] uncited claim cannot finalize
  * [ ] agent tries forbidden action -> rejected + logged
  * [ ] evidence pointer that doesn’t resolve -> rulecheck fails

---

## Suggested “build order” (so you get real end-to-end value ASAP)

If you want the fastest “real system” proof (with no stubs), implement in this order:

1. Components 0–7 (infra → DB → storage → auth → RBAC → workspaces → artifacts)
2. Components 8–13 (logs/events → pdf_ingest → resolver → claims/drafts → citation_check)
3. Component 15 (Workflow A end-to-end)
4. Components 16–18 (repo_ingest → sandbox_run → Workflow B)
5. Components 19–21 (critiques → phase gates → finalization)
6. Components 22–24 (search → UI → evaluation harness)

This matches the “minimum workflows to prove the system” approach in the spec while still keeping each step independently testable.
