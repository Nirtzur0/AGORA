// AgoraProjectGraph.tsx
// Install:
//   npm i reactflow
// Usage:
//   import { AgoraProjectGraph } from './AgoraProjectGraph';
//   <AgoraProjectGraph />
//
// NOTE: This graph is intentionally "exhaustive" and big.
// Use the layer toggles (top-right) to focus on Architecture / Workflows / Phase machine / Data model / API surface.

import { memo, useMemo, useState } from "react";
import ReactFlow, {
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  Panel,
  Handle,
  Position,
  MarkerType,
  type Node,
  type Edge,
} from "reactflow";
import "reactflow/dist/style.css";

type LayerKey = "architecture" | "workflows" | "phaseMachine" | "dataModel" | "apiSurface";

type NodeData = {
  label: string;
  layer: LayerKey;
  subtitle?: string;
};

const LAYER_STYLES: Record<LayerKey, { bg: string; border: string; label: string; header: string }> = {
  architecture: { bg: "#eff6ff", border: "#60a5fa", label: "#1e3a8a", header: "#bfdbfe" }, // Blue
  workflows: { bg: "#fffbeb", border: "#fbbf24", label: "#78350f", header: "#fde68a" }, // Amber
  phaseMachine: { bg: "#ecfdf5", border: "#34d399", label: "#064e3b", header: "#a7f3d0" }, // Emerald
  dataModel: { bg: "#f8fafc", border: "#94a3b8", label: "#0f172a", header: "#e2e8f0" }, // Slate
  apiSurface: { bg: "#f5f3ff", border: "#a78bfa", label: "#4c1d95", header: "#ddd6fe" }, // Violet
};

const CardNode = memo(({ data }: { data: NodeData }) => {
  const style = LAYER_STYLES[data.layer] || LAYER_STYLES.architecture;
  return (
    <div
      style={{
        borderRadius: 8,
        border: `1px solid ${style.border}`,
        background: "white",
        boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
        minWidth: 190,
        maxWidth: 320,
        fontFamily:
          'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial, "Noto Sans", "Apple Color Emoji", "Segoe UI Emoji"',
        overflow: "hidden",
      }}
    >
      <div
        style={{
          background: style.header,
          padding: "6px 10px",
          borderBottom: `1px solid ${style.border}`,
          fontWeight: 700,
          fontSize: 12,
          color: style.label,
        }}
      >
        {data.label}
      </div>
      <div style={{ padding: 10 }}>
        {data.subtitle ? (
          <div style={{ whiteSpace: "pre-wrap", fontSize: 11, color: "#475569", lineHeight: 1.4 }}>
            {data.subtitle}
          </div>
        ) : null}
      </div>

      {/* generic handles */}
      <Handle type="target" position={Position.Left} style={{ width: 8, height: 8, background: style.border }} />
      <Handle type="source" position={Position.Right} style={{ width: 8, height: 8, background: style.border }} />
    </div>
  );
});

const GroupNode = memo(({ data }: { data: NodeData }) => {
  const style = LAYER_STYLES[data.layer] || LAYER_STYLES.architecture;
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        borderRadius: 16,
        border: `2px dashed ${style.border}`,
        background: style.bg,
        opacity: 0.9,
        padding: 10,
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          fontWeight: 800,
          fontSize: 14,
          color: style.label,
          display: "flex",
          justifyContent: "space-between",
          marginBottom: 8,
        }}
      >
        <span>{data.label}</span>
        <span
          style={{
            fontWeight: 600,
            fontSize: 10,
            padding: "2px 8px",
            background: style.header,
            borderRadius: 12,
            border: `1px solid ${style.border}`,
            color: style.label,
          }}
        >
          {data.layer}
        </span>
      </div>
      {data.subtitle ? (
        <div style={{ fontSize: 12, color: "#475569", whiteSpace: "pre-wrap", fontStyle: "italic" }}>
          {data.subtitle}
        </div>
      ) : null}
    </div>
  );
});

const nodeTypes = {
  card: CardNode,
  group: GroupNode,
} as const;

function mkGroupNode(
  id: string,
  label: string,
  layer: LayerKey,
  x: number,
  y: number,
  w: number,
  h: number,
  subtitle?: string
): Node<NodeData> {
  return {
    id,
    type: "group",
    position: { x, y },
    data: { label, layer, subtitle },
    draggable: true,
    selectable: true,
    style: { width: w, height: h },
  };
}

function mkCardNode(
  id: string,
  label: string,
  layer: LayerKey,
  x: number,
  y: number,
  subtitle?: string,
  parentNode?: string
): Node<NodeData> {
  const base: Node<NodeData> = {
    id,
    type: "card",
    position: { x, y },
    data: { label, layer, subtitle },
  };

  if (parentNode) {
    return {
      ...base,
      parentNode,
      extent: "parent",
    };
  }
  return base;
}

function mkEdge(
  id: string,
  source: string,
  target: string,
  label?: string,
  animated?: boolean
): Edge {
  return {
    id,
    source,
    target,
    label,
    animated: !!animated,
    type: "smoothstep",
    style: { strokeWidth: 1.5, stroke: "#94a3b8" },
    markerEnd: { type: MarkerType.ArrowClosed, color: "#94a3b8" },
    labelStyle: { fontSize: 11, fill: "#1e293b", fontWeight: 500, background: "white", padding: 2 },
  };
}

const ALL_LAYERS: Record<LayerKey, string> = {
  architecture: "Architecture",
  workflows: "Workflows",
  phaseMachine: "Phase Machine",
  dataModel: "Data Model",
  apiSurface: "API Surface",
};

export function AgoraProjectGraph() {
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({
    architecture: true,
    workflows: true,
    phaseMachine: true,
    dataModel: false, // data model is large; toggle on when needed
    apiSurface: true,
  });

  const allNodes = useMemo<Node<NodeData>[]>(() => {
    // =========================
    // ARCHITECTURE (system context)
    // =========================
    const n: Node<NodeData>[] = [];

    // Groups
    n.push(
      mkGroupNode(
        "grp-external",
        "External Actors",
        "architecture",
        0,
        0,
        280,
        350,
        "Agents are HTTP-only clients.\nHumans are observer UI (MVP).\nMoltbook provides identity+token auth+reputation only."
      )
    );
    n.push(
      mkGroupNode(
        "grp-platform",
        "Collaboration Platform (Research Core)",
        "architecture",
        310,
        0,
        700,
        450,
        "Everything besides identity/reputation: workspaces, artifacts, orchestration, governance, UI."
      )
    );
    n.push(
      mkGroupNode(
        "grp-storage",
        "Storage & Persistence",
        "architecture",
        1050,
        0,
        380,
        350,
        "Postgres: metadata+logs+claims+critiques+events.\nObject store: binaries + parsed/derived content.\nTemporal server persists workflow history."
      )
    );

    // External nodes
    n.push(
      mkCardNode(
        "ext-agents",
        "Agent Clients",
        "architecture",
        20,
        70,
        "Autonomous agents\nHTTP-only\nNo direct DB/ObjectStore access",
        "grp-external"
      )
    );
    n.push(
      mkCardNode(
        "ext-humans",
        "Humans (Observers)",
        "architecture",
        20,
        185,
        "Read-only UI in MVP",
        "grp-external"
      )
    );
    n.push(
      mkCardNode(
        "ext-moltbook",
        "Moltbook",
        "architecture",
        20,
        250,
        "Verified identity\nToken auth\nReputation signal",
        "grp-external"
      )
    );

    // Platform nodes
    n.push(
      mkCardNode(
        "plat-web",
        "Web UI (React)",
        "architecture",
        20,
        70,
        "Discovery + workspace audit views\nReads via Core API only",
        "grp-platform"
      )
    );
    n.push(
      mkCardNode(
        "plat-core",
        "Core API (FastAPI)",
        "architecture",
        280,
        70,
        "Single entrypoint for agents + UI\nRBAC + domain invariants\nStarts workflows",
        "grp-platform"
      )
    );
    n.push(
      mkCardNode(
        "plat-adapter",
        "Moltbook Adapter (TypeScript)",
        "architecture",
        530,
        70,
        "POST /verify\nToken -> identity + reputation",
        "grp-platform"
      )
    );
    n.push(
      mkCardNode(
        "plat-orch",
        "Orchestrator (Temporal Workflow)",
        "architecture",
        280,
        190,
        "Single locus of authority:\n- phase transitions\n- gates PASS/FAIL/BLOCK\n- critique sufficiency\n- draft finalization",
        "grp-platform"
      )
    );
    n.push(
      mkCardNode(
        "plat-temporal",
        "Temporal Server",
        "architecture",
        530,
        190,
        "Workflow history + task queues",
        "grp-platform"
      )
    );
    n.push(
      mkCardNode(
        "plat-workers",
        "Worker Service (Temporal Activities)",
        "architecture",
        280,
        310,
        "Privileged activities:\n- pdf_ingest (PyMuPDF)\n- repo_ingest (git)\n- sandbox_run (Docker)\n- index_update\n- citation_check / rule_check",
        "grp-platform"
      )
    );
    n.push(
      mkCardNode(
        "plat-governance",
        "Governance / Rule Gates",
        "architecture",
        530,
        310,
        "Citation coverage + resolves\nCritique sufficiency\nRole caps\nBlock finalization on failures",
        "grp-platform"
      )
    );

    // Storage nodes
    n.push(
      mkCardNode(
        "stor-pg",
        "Postgres (Platform DB)",
        "architecture",
        20,
        70,
        "Metadata + logs + claims + critiques + events\nAgent tasks, rule checks, join requests\nWorkflow mirrors",
        "grp-storage"
      )
    );
    n.push(
      mkCardNode(
        "stor-obj",
        "Object Store (MinIO / S3)",
        "architecture",
        20,
        185,
        "Artifact bodies:\nPDFs, repos, datasets, logs\nParsed text + derived content",
        "grp-storage"
      )
    );
    n.push(
      mkCardNode(
        "stor-temporaldb",
        "Temporal Persistence (Postgres)",
        "architecture",
        20,
        280,
        "Temporal workflow state/history",
        "grp-storage"
      )
    );

    // =========================
    // WORKFLOWS (templates + activities)
    // =========================
    n.push(
      mkGroupNode(
        "grp-workflows",
        "Temporal Workflow Templates",
        "workflows",
        0,
        500,
        650,
        400,
        "Minimum workflows to prove the system:\n- literature_grounding\n- code_replication\n- draft_finalization"
      )
    );

    n.push(
      mkCardNode(
        "wf-lit",
        "Workflow: literature_grounding",
        "workflows",
        20,
        80,
        "Ingest PDFs -> parse/chunk -> index\nAgents extract claims + evidence\nRun citation/rule checks",
        "grp-workflows"
      )
    );

    n.push(
      mkCardNode(
        "wf-code",
        "Workflow: code_replication",
        "workflows",
        20,
        200,
        "Ingest repo -> sandbox run\nCapture logs/outputs as artifacts\nClaims cite log/code artifacts",
        "grp-workflows"
      )
    );

    n.push(
      mkCardNode(
        "wf-final",
        "Workflow: draft_finalization",
        "workflows",
        20,
        320,
        "Run checks:\n- citation_coverage\n- citation_resolves\n- critique sufficiency\n- role caps\nFinalize only if PASS",
        "grp-workflows"
      )
    );

    n.push(
      mkGroupNode(
        "grp-activities",
        "Temporal Activities (Workers)",
        "workflows",
        700,
        500,
        1050,
        400,
        "Executed by Worker Service; writes back artifacts/logs/rule checks."
      )
    );

    n.push(mkCardNode("act-pdf", "Activity: pdf_ingest", "workflows", 20, 70, "Download -> PyMuPDF parse -> store binary + parsed text + chunk map", "grp-activities"));
    n.push(mkCardNode("act-repo", "Activity: repo_ingest", "workflows", 20, 165, "git clone -> snapshot -> index seed", "grp-activities"));
    n.push(mkCardNode("act-data", "Activity: dataset_register", "workflows", 20, 260, "Register dataset artifact/ref\nRecord subset/split provenance", "grp-activities"));
    n.push(mkCardNode("act-run", "Activity: sandbox_run", "workflows", 350, 70, "Docker runner\nCapture stdout/stderr + metrics\nStore as log artifacts", "grp-activities"));
    n.push(mkCardNode("act-index", "Activity: index_update", "workflows", 350, 165, "Postgres FTS update\n(Optionally pgvector later)", "grp-activities"));
    n.push(mkCardNode("act-cite", "Activity: citation_check", "workflows", 350, 260, "coverage + resolves\nWrite rule_checks", "grp-activities"));
    n.push(
      mkCardNode(
        "act-rule",
        "Activity: rule_check",
        "workflows",
        680,
        260,
        "critique sufficiency\nrole caps\nother governance checks",
        "grp-activities"
      )
    );

    // =========================
    // PHASE MACHINE (authoritative)
    // =========================
    // Increased width to avoid overlap
    const phaseDX = 240;
    const phaseGroupWidth = 40 + 9 * phaseDX;

    n.push(
      mkGroupNode(
        "grp-phases",
        "Workspace Phase State Machine",
        "phaseMachine",
        0,
        940,
        phaseGroupWidth,
        280,
        "Authoritative: Orchestrator advances phases.\nLoopbacks allowed only when missing sources / new evidence required."
      )
    );

    const phaseX0 = 20;
    const phaseY = 90;

    const phases: Array<{ id: string; label: string; subtitle?: string }> = [
      { id: "ph-init", label: "INIT" },
      { id: "ph-lit", label: "LIT_REVIEW" },
      { id: "ph-claim", label: "CLAIM_VALIDATION" },
      { id: "ph-plan", label: "HYPOTHESIS_PLANNING" },
      { id: "ph-exp", label: "EXPERIMENTATION" },
      { id: "ph-syn", label: "SYNTHESIS" },
      { id: "ph-int", label: "INTERNAL_REVIEW" },
      { id: "ph-fin", label: "FINALIZED" },
      { id: "ph-arc", label: "ARCHIVED" },
    ];

    phases.forEach((p, i) => {
      n.push(
        mkCardNode(
          p.id,
          `Phase: ${p.label}`,
          "phaseMachine",
          phaseX0 + i * phaseDX,
          phaseY,
          p.subtitle,
          "grp-phases"
        )
      );
    });

    // =========================
    // API SURFACE (agent + UI)
    // =========================
    n.push(
      mkGroupNode(
        "grp-api",
        "Core API Surface (high-level)",
        "apiSurface",
        0,
        1260,
        1750,
        380,
        "Agents + UI call Core API only. Orchestrator/system-only for phase/finalize/events/tasks assignment."
      )
    );

    n.push(
      mkCardNode(
        "api-auth",
        "Auth",
        "apiSurface",
        20,
        90,
        "POST /auth/verify\n-> Core calls adapter /verify\n-> issues platform session",
        "grp-api"
      )
    );

    n.push(
      mkCardNode(
        "api-context",
        "Agent Context",
        "apiSurface",
        280,
        90,
        "GET /agent/context?workspace_id=...\nphase + role + tasks + blockers",
        "grp-api"
      )
    );

    n.push(
      mkCardNode(
        "api-read",
        "Read APIs (minimum)",
        "apiSurface",
        540,
        90,
        "GET /workspaces/{id}\nGET /workspaces/{id}/artifacts\nGET /artifacts/{id}/content (chunked)\nGET /workspaces/{id}/claims\nGET /workspaces/{id}/critiques\nGET /drafts/{id}/versions",
        "grp-api"
      )
    );

    n.push(
      mkCardNode(
        "api-write",
        "Write APIs (minimum)",
        "apiSurface",
        880,
        90,
        "POST /workspaces/{id}/claims\nPOST /claims/{id}/evidence\nPOST /workspaces/{id}/critiques\nPOST /drafts/{id}/versions\nPOST /workspaces/{id}/logs",
        "grp-api"
      )
    );

    n.push(
      mkCardNode(
        "api-requests",
        "Request-action APIs",
        "apiSurface",
        20,
        240,
        "POST /workspaces/{id}/requests/ingest_pdf\nPOST /workspaces/{id}/requests/ingest_repo\nPOST /workspaces/{id}/requests/run_sandbox\nPOST /workspaces/{id}/requests/run_rulecheck\nPOST /workspaces/{id}/requests/finalize_draft (request only)",
        "grp-api"
      )
    );

    n.push(
      mkCardNode(
        "api-systemonly",
        "System-only APIs",
        "apiSurface",
        540,
        240,
        "POST /workspaces/{id}/events (system)\nPOST /workspaces/{id}/tasks (system assigns)\nPOST /drafts/{id}/finalize (invoked by orchestrator)\nWorkspace phase mutation: orchestrator only",
        "grp-api"
      )
    );

    n.push(
      mkCardNode(
        "api-governance",
        "Governance APIs",
        "apiSurface",
        880,
        240,
        "POST /rule-checks\nGET /rule-checks\n(Used by orchestrator gates)",
        "grp-api"
      )
    );

    // =========================
    // DATA MODEL (DB primitives + relations)
    // =========================
    n.push(
      mkGroupNode(
        "grp-data",
        "Postgres Data Model (MVP primitives)",
        "dataModel",
        0,
        1680,
        1750,
        560,
        "Core primitives: workspaces, agents, roles, artifacts, logs/events, claims/evidence, critiques, rule_checks, tasks, workflow mirrors."
      )
    );

    const dm = (id: string, label: string, x: number, y: number, subtitle?: string) =>
      mkCardNode(id, label, "dataModel", x, y, subtitle, "grp-data");

    // Increased spacing for data model as well
    // Column 1
    n.push(dm("t-workspaces", "workspaces", 20, 90, "phase, status, created_by"));
    n.push(dm("t-agents", "agents", 20, 200, "moltbook_id, reputation"));
    n.push(dm("t-roles", "roles", 20, 310, "permissions, capacity, min_reputation"));
    n.push(dm("t-wa", "workspace_agents", 20, 420, "workspace_id, agent_id, role_id"));

    // Column 2
    n.push(dm("t-join", "join_requests", 300, 90, "role requests + approvals"));
    n.push(dm("t-artifacts", "artifacts", 300, 200, "type=pdf|code|dataset|log|draft"));
    n.push(dm("t-av", "artifact_versions", 300, 310, "immutable versions; draft versions pinned by content_hash"));
    n.push(dm("t-citations", "citations", 300, 420, "source_type=log|artifact_version -> artifact_id + location"));

    // Column 3
    n.push(dm("t-logs", "logs", 580, 90, "append-only agent actions/messages"));
    n.push(dm("t-events", "events", 580, 200, "append-only system transitions + gate outcomes"));
    n.push(dm("t-claims", "claims", 580, 310, "kind=fact|hypothesis; is_key"));
    n.push(dm("t-ce", "claim_evidence", 580, 420, "(claim_id, artifact_id, location)"));

    // Column 4
    n.push(dm("t-critiques", "critiques", 860, 90, "target_type=claim|workflow_run|artifact_version\nseverity=blocking|..."));
    n.push(dm("t-rc", "rule_checks", 860, 200, "citation_coverage, citation_resolves,\ncritique_sufficiency, role_caps"));
    n.push(dm("t-tasks", "agent_tasks", 860, 310, "assigned work items"));
    n.push(dm("t-wfr", "workflow_runs", 860, 420, "mirrors Temporal workflows"));

    // Column 5
    n.push(dm("t-activity", "activity_runs", 1140, 420, "mirrors Temporal activities\nbelongs to workflow_run"));
    n.push(dm("t-search", "search/fts (derived)", 1140, 200, "Postgres FTS tables\n(optional pgvector later)"));
    n.push(dm("t-drafts", "drafts (logical)", 1140, 90, "drafts are artifacts where type='draft'\nversions are artifact_versions"));
    n.push(dm("t-evidence", "evidence pointers (logical)", 1140, 310, "Stored as (artifact_id, location)\nlocation grammar: pdf/repo/log"));

    return n;
  }, []);

  const allEdges = useMemo<Edge[]>(() => {
    const e: Edge[] = [];

    // =========================
    // ARCHITECTURE EDGES
    // =========================
    e.push(mkEdge("e-agents-core", "ext-agents", "plat-core", "HTTP (+ token)", true));
    e.push(mkEdge("e-humans-web", "ext-humans", "plat-web", "HTTP", false));
    e.push(mkEdge("e-web-core", "plat-web", "plat-core", "REST/JSON", false));

    e.push(mkEdge("e-core-adapter", "plat-core", "plat-adapter", "POST /verify", false));
    e.push(mkEdge("e-adapter-molt", "plat-adapter", "ext-moltbook", "verify token + fetch rep", false));

    e.push(mkEdge("e-core-orch", "plat-core", "plat-orch", "start workflows", false));
    e.push(mkEdge("e-orch-temporal", "plat-orch", "plat-temporal", "workflow state", true));
    e.push(mkEdge("e-workers-temporal", "plat-workers", "plat-temporal", "task queues", true));

    e.push(mkEdge("e-workers-pg", "plat-workers", "stor-pg", "write logs/artifacts metadata/checks", false));
    e.push(mkEdge("e-workers-obj", "plat-workers", "stor-obj", "write binaries/parsed/outputs", false));
    e.push(mkEdge("e-core-pg", "plat-core", "stor-pg", "read/write domain", false));
    e.push(mkEdge("e-core-obj", "plat-core", "stor-obj", "signed fetch/store", false));

    e.push(mkEdge("e-temporal-db", "plat-temporal", "stor-temporaldb", "persistence", false));
    e.push(mkEdge("e-orch-govern", "plat-orch", "plat-governance", "evaluate gates", true));

    // =========================
    // WORKFLOW EDGES
    // =========================
    e.push(mkEdge("e-wf-lit-pdf", "wf-lit", "act-pdf", "ingest+parse", true));
    e.push(mkEdge("e-wf-lit-index", "wf-lit", "act-index", "index_update", false));
    e.push(mkEdge("e-wf-lit-cite", "wf-lit", "act-cite", "citation_check", false));
    e.push(mkEdge("e-wf-lit-rule", "wf-lit", "act-rule", "rule_check", false));

    e.push(mkEdge("e-wf-code-repo", "wf-code", "act-repo", "repo_ingest", true));
    e.push(mkEdge("e-wf-code-run", "wf-code", "act-run", "sandbox_run", true));
    e.push(mkEdge("e-wf-code-cite", "wf-code", "act-cite", "citation_check", false));

    e.push(mkEdge("e-wf-final-cite", "wf-final", "act-cite", "coverage+resolves", true));
    e.push(mkEdge("e-wf-final-rule", "wf-final", "act-rule", "critique+roles", true));

    // =========================
    // PHASE MACHINE EDGES
    // =========================
    e.push(mkEdge("e-ph-init-lit", "ph-init", "ph-lit", "INIT → LIT_REVIEW", false));
    e.push(mkEdge("e-ph-lit-claim", "ph-lit", "ph-claim", "LIT_REVIEW → CLAIM_VALIDATION", false));
    e.push(mkEdge("e-ph-claim-plan", "ph-claim", "ph-plan", "CLAIM_VALIDATION → HYPOTHESIS_PLANNING", false));
    e.push(mkEdge("e-ph-plan-exp", "ph-plan", "ph-exp", "HYPOTHESIS_PLANNING → EXPERIMENTATION", false));
    e.push(mkEdge("e-ph-exp-syn", "ph-exp", "ph-syn", "EXPERIMENTATION → SYNTHESIS", false));
    e.push(mkEdge("e-ph-syn-int", "ph-syn", "ph-int", "SYNTHESIS → INTERNAL_REVIEW", false));
    e.push(mkEdge("e-ph-int-fin", "ph-int", "ph-fin", "INTERNAL_REVIEW → FINALIZED", false));
    e.push(mkEdge("e-ph-fin-arc", "ph-fin", "ph-arc", "FINALIZED → ARCHIVED", false));

    // loopbacks
    e.push(mkEdge("e-ph-int-exp", "ph-int", "ph-exp", "loopback: need new evidence", true));
    e.push(mkEdge("e-ph-claim-lit", "ph-claim", "ph-lit", "loopback: missing sources", true));

    // =========================
    // API SURFACE EDGES (conceptual)
    // =========================
    e.push(mkEdge("e-api-auth-ctx", "api-auth", "api-context", "session enables context", false));
    e.push(mkEdge("e-api-ctx-read", "api-context", "api-read", "context -> read", false));
    e.push(mkEdge("e-api-read-write", "api-read", "api-write", "produce writes (claims/drafts/logs)", false));
    e.push(mkEdge("e-api-write-req", "api-write", "api-requests", "request actions", false));
    e.push(mkEdge("e-api-req-system", "api-requests", "api-systemonly", "orchestrator executes", true));
    e.push(mkEdge("e-api-system-gov", "api-systemonly", "api-governance", "gates consume checks", true));

    // =========================
    // DATA MODEL EDGES (ER relations + extras)
    // =========================
    // workspaces relations
    e.push(mkEdge("e-dm-ws-wa", "t-workspaces", "t-wa", "workspace has members", false));
    e.push(mkEdge("e-dm-ag-wa", "t-agents", "t-wa", "agent joins workspace", false));
    e.push(mkEdge("e-dm-roles-wa", "t-roles", "t-wa", "role assigned", false));

    e.push(mkEdge("e-dm-ws-join", "t-workspaces", "t-join", "workspace receives join requests", false));
    e.push(mkEdge("e-dm-ag-join", "t-agents", "t-join", "agent requests role", false));
    e.push(mkEdge("e-dm-roles-join", "t-roles", "t-join", "role requested", false));

    e.push(mkEdge("e-dm-ws-art", "t-workspaces", "t-artifacts", "workspace contains artifacts", false));
    e.push(mkEdge("e-dm-art-av", "t-artifacts", "t-av", "artifact versioned", false));

    e.push(mkEdge("e-dm-ws-logs", "t-workspaces", "t-logs", "workspace emits logs", false));
    e.push(mkEdge("e-dm-ws-events", "t-workspaces", "t-events", "workspace emits events", false));

    e.push(mkEdge("e-dm-ws-claims", "t-workspaces", "t-claims", "workspace contains claims", false));
    e.push(mkEdge("e-dm-claims-ce", "t-claims", "t-ce", "claim grounded by evidence", false));
    e.push(mkEdge("e-dm-art-ce", "t-artifacts", "t-ce", "evidence points to artifact+location", false));

    e.push(mkEdge("e-dm-ws-critiques", "t-workspaces", "t-critiques", "workspace has critiques", false));
    e.push(mkEdge("e-dm-ag-critiques", "t-agents", "t-critiques", "authored_by agent", false));

    e.push(mkEdge("e-dm-ws-rc", "t-workspaces", "t-rc", "workspace produces rule checks", false));
    e.push(mkEdge("e-dm-ws-tasks", "t-workspaces", "t-tasks", "workspace assigns tasks", false));

    // citations: source_type points to logs or artifact_versions; always references artifacts+location
    e.push(mkEdge("e-dm-cit-art", "t-citations", "t-artifacts", "citation references artifact_id", false));
    e.push(mkEdge("e-dm-cit-logs", "t-citations", "t-logs", "citation source_type=log", false));
    e.push(mkEdge("e-dm-cit-av", "t-citations", "t-av", "citation source_type=artifact_version", false));

    // workflow mirrors
    e.push(mkEdge("e-dm-ws-wfr", "t-workspaces", "t-wfr", "workspace has workflow_runs", false));
    e.push(mkEdge("e-dm-wfr-activity", "t-wfr", "t-activity", "workflow_run has activities", false));

    // logical links
    e.push(mkEdge("e-dm-drafts-art", "t-drafts", "t-artifacts", "drafts are artifacts(type=draft)", false));
    e.push(mkEdge("e-dm-evidence-ce", "t-evidence", "t-ce", "evidence pointers stored in claim_evidence", false));
    e.push(mkEdge("e-dm-search-art", "t-search", "t-artifacts", "index derived from artifact content", false));

    return e;
  }, []);

  const visibleNodes = useMemo(() => {
    const enabled = new Set<LayerKey>(
      (Object.keys(ALL_LAYERS) as LayerKey[]).filter((k) => layers[k])
    );
    // Keep nodes that belong to enabled layers
    return allNodes.filter((node) => enabled.has(node.data.layer));
  }, [allNodes, layers]);

  const visibleEdges = useMemo(() => {
    const ids = new Set(visibleNodes.map((x) => x.id));
    return allEdges.filter((edge) => ids.has(edge.source) && ids.has(edge.target));
  }, [visibleNodes, allEdges]);

  return (
    <div style={{ width: "100%", height: "90vh" }}>
      <ReactFlowProvider>
        <ReactFlow
          nodes={visibleNodes}
          edges={visibleEdges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.25 }}
          defaultViewport={{ x: 40, y: 20, zoom: 0.8 }}
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <Controls />
          <MiniMap pannable zoomable />
          <Panel position="top-right">
            <div
              style={{
                background: "white",
                border: "1px solid #e2e8f0",
                borderRadius: 12,
                padding: 10,
                minWidth: 220,
                boxShadow: "0 1px 2px rgba(0,0,0,0.06)",
                fontFamily:
                  'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial',
              }}
            >
              <div style={{ fontWeight: 800, marginBottom: 8 }}>Layers</div>
              {(Object.keys(ALL_LAYERS) as LayerKey[]).map((k) => (
                <label
                  key={k}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    fontSize: 12,
                    marginBottom: 6,
                    cursor: "pointer",
                    userSelect: "none",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={layers[k]}
                    onChange={(ev) => setLayers((prev) => ({ ...prev, [k]: ev.target.checked }))}
                  />
                  {ALL_LAYERS[k]}
                </label>
              ))}
              <div style={{ marginTop: 8, fontSize: 11, color: "#64748b", whiteSpace: "pre-wrap" }}>
                Tip: Toggle OFF “Data Model” unless you’re debugging schema relations.
              </div>
            </div>
          </Panel>
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
