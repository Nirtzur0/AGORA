#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
DEBUG_TOKEN="${DEBUG_TOKEN:-debug-token-clawdbot}"
REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON="${PYTHON:-python3}"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_cmd curl
require_cmd "$PYTHON"

uuid() {
  "$PYTHON" - <<'PY'
import uuid
print(uuid.uuid4())
PY
}

json_get() {
  local key="$1"
  "$PYTHON" - <<PY
import json,sys
data=json.loads(sys.stdin.read())
print(data.get("$key",""))
PY
}

echo "== Health check"
curl -sS "$BASE_URL/health" >/dev/null

echo "== Auth (primary agent)"
AUTH_JSON=$(curl -sS -X POST "$BASE_URL/auth/moltbook" -H "X-Moltbook-Identity: $DEBUG_TOKEN")
AGENT_JWT=$(printf '%s' "$AUTH_JSON" | json_get agent_session_jwt)
AGENT_ID=$(printf '%s' "$AUTH_JSON" | json_get agent_id)

echo "== Create workspace (idempotent)"
IDEMPOTENCY_KEY=$(uuid)
WORKSPACE_JSON=$(curl -sS -X POST "$BASE_URL/workspaces" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"System Flows Smoke","description":"ingest_pdf + ingest_repo + run_sandbox + finalize_draft"}')
WORKSPACE_ID=$(printf '%s' "$WORKSPACE_JSON" | json_get id)

echo "== Create additional agents (DB-backed for smoke test)"
SECOND_AGENT_JSON=$("$PYTHON" - <<'PY'
import os, uuid, psycopg2
db_url = os.getenv("DATABASE_URL", "postgresql://agora:agora_dev_password@localhost:5432/agora")
agent_id = str(uuid.uuid4())
moltbook_id = f"mb_smoke_{agent_id[:8]}"
name = "Smoke Skeptic"
reputation = 50
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute(
    "INSERT INTO agents (id, moltbook_id, name, reputation) VALUES (%s,%s,%s,%s)",
    (agent_id, moltbook_id, name, reputation),
)
conn.commit()
cur.close(); conn.close()
print(f"{agent_id}|{moltbook_id}|{reputation}")
PY
)
SECOND_AGENT_ID=$(printf '%s' "$SECOND_AGENT_JSON" | cut -d'|' -f1)
SECOND_MOLTBOOK_ID=$(printf '%s' "$SECOND_AGENT_JSON" | cut -d'|' -f2)
SECOND_REP=$(printf '%s' "$SECOND_AGENT_JSON" | cut -d'|' -f3)

THIRD_AGENT_JSON=$("$PYTHON" - <<'PY'
import os, uuid, psycopg2
db_url = os.getenv("DATABASE_URL", "postgresql://agora:agora_dev_password@localhost:5432/agora")
agent_id = str(uuid.uuid4())
moltbook_id = f"mb_smoke_{agent_id[:8]}"
name = "Smoke Method Reviewer"
reputation = 50
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute(
    "INSERT INTO agents (id, moltbook_id, name, reputation) VALUES (%s,%s,%s,%s)",
    (agent_id, moltbook_id, name, reputation),
)
conn.commit()
cur.close(); conn.close()
print(f"{agent_id}|{moltbook_id}|{reputation}")
PY
)
THIRD_AGENT_ID=$(printf '%s' "$THIRD_AGENT_JSON" | cut -d'|' -f1)
THIRD_MOLTBOOK_ID=$(printf '%s' "$THIRD_AGENT_JSON" | cut -d'|' -f2)
THIRD_REP=$(printf '%s' "$THIRD_AGENT_JSON" | cut -d'|' -f3)

echo "== Mint JWTs for additional agents"
SECOND_AGENT_JWT=$("$PYTHON" - <<PY
import sys
sys.path.insert(0, "$REPO_ROOT/apps/core-api")
from jwt_utils import create_agent_token_v2
print(create_agent_token_v2("$SECOND_AGENT_ID", "$SECOND_MOLTBOOK_ID", int("$SECOND_REP")))
PY
)

THIRD_AGENT_JWT=$("$PYTHON" - <<PY
import sys
sys.path.insert(0, "$REPO_ROOT/apps/core-api")
from jwt_utils import create_agent_token_v2
print(create_agent_token_v2("$THIRD_AGENT_ID", "$THIRD_MOLTBOOK_ID", int("$THIRD_REP")))
PY
)

echo "== Start orchestrator worker"
WORKER_LOG="/tmp/agora_orchestrator_worker.log"
"$PYTHON" - <<PY >"$WORKER_LOG" 2>&1 &
import asyncio, sys
repo_root = "$REPO_ROOT"
sys.path.insert(0, repo_root)
sys.path.insert(0, repo_root + "/apps/worker")
sys.path.insert(0, repo_root + "/apps/core-api")
sys.path.insert(0, repo_root + "/packages/shared-types")
sys.path.insert(0, repo_root + "/packages/db")
from temporalio.client import Client
from temporalio.worker import Worker
from phase_advancement_workflow import PhaseAdvancementWorkflow
from draft_finalization_workflow import DraftFinalizationWorkflow
from phase_activities import (
    get_workspace_phase,
    validate_phase_transition,
    advance_workspace_phase,
    create_required_action_tasks,
    gather_lit_review_exit_snapshot,
    gather_experimentation_exit_snapshot,
    gather_internal_review_exit_snapshot,
    gather_finalization_gate_snapshot,
)
from finalization_activities import finalize_draft_artifact

async def main():
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue="agora-orchestrator",
        workflows=[PhaseAdvancementWorkflow, DraftFinalizationWorkflow],
        activities=[
            get_workspace_phase,
            validate_phase_transition,
            advance_workspace_phase,
            create_required_action_tasks,
            gather_lit_review_exit_snapshot,
            gather_experimentation_exit_snapshot,
            gather_internal_review_exit_snapshot,
            gather_finalization_gate_snapshot,
            finalize_draft_artifact,
        ],
    )
    await worker.run()

asyncio.run(main())
PY
WORKER_PID=$!
trap 'kill $WORKER_PID >/dev/null 2>&1 || true' EXIT

echo "== Create roles (Skeptic + Method Reviewer)"
ROLE_IDS=$("$PYTHON" - <<'PY'
import os, psycopg2, json
db_url = os.getenv("DATABASE_URL", "postgresql://agora:agora_dev_password@localhost:5432/agora")
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute("SELECT name, id FROM roles WHERE name IN ('Skeptic','Method Reviewer')")
rows = cur.fetchall()
cur.close(); conn.close()
print(json.dumps({name: str(id_) for name, id_ in rows}))
PY
)
SKEPTIC_ROLE_ID=$(printf '%s' "$ROLE_IDS" | "$PYTHON" - <<'PY'
import json,sys
print(json.loads(sys.stdin.read()).get("Skeptic",""))
PY
)
METHOD_ROLE_ID=$(printf '%s' "$ROLE_IDS" | "$PYTHON" - <<'PY'
import json,sys
print(json.loads(sys.stdin.read()).get("Method Reviewer",""))
PY
)
if [[ -z "$SKEPTIC_ROLE_ID" || -z "$METHOD_ROLE_ID" ]]; then
  echo "Missing required roles. Seed roles before running smoke tests." >&2
  exit 1
fi

echo "== Join requests for roles (approve)"
JR_JSON=$(curl -sS -X POST "$BASE_URL/workspaces/$WORKSPACE_ID/join-requests" \
  -H "Authorization: Bearer $SECOND_AGENT_JWT" \
  -H "Idempotency-Key: $(uuid)" \
  -H "Content-Type: application/json" \
  -d "{\"role_id\":\"$SKEPTIC_ROLE_ID\"}")
JR_ID=$(printf '%s' "$JR_JSON" | json_get id)
curl -sS -X POST "$BASE_URL/workspaces/$WORKSPACE_ID/join-requests/$JR_ID/review" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{"approve": true}' >/dev/null

JR_JSON=$(curl -sS -X POST "$BASE_URL/workspaces/$WORKSPACE_ID/join-requests" \
  -H "Authorization: Bearer $THIRD_AGENT_JWT" \
  -H "Idempotency-Key: $(uuid)" \
  -H "Content-Type: application/json" \
  -d "{\"role_id\":\"$METHOD_ROLE_ID\"}")
JR_ID=$(printf '%s' "$JR_JSON" | json_get id)
curl -sS -X POST "$BASE_URL/workspaces/$WORKSPACE_ID/join-requests/$JR_ID/review" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{"approve": true}' >/dev/null

echo "== Create PDF artifact + version"
PDF_ARTIFACT_JSON=$(curl -sS -X POST "$BASE_URL/workspaces/$WORKSPACE_ID/artifacts" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Idempotency-Key: $(uuid)" \
  -H "Content-Type: application/json" \
  -d '{"type":"pdf","metadata":{"source":"smoke"}}')
PDF_ARTIFACT_ID=$(printf '%s' "$PDF_ARTIFACT_JSON" | json_get id)

"$PYTHON" - <<'PY'
from pathlib import Path

text = "Smoke PDF test. Evidence line for ingestion."
escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

objects = []
objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET"
objects.append(
    b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
    b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
)
objects.append(
    f"4 0 obj<< /Length {len(stream)} >>stream\n{stream}\nendstream\nendobj\n".encode()
)
objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

pdf = b"%PDF-1.4\n"
offsets = [0]
for obj in objects:
    offsets.append(len(pdf))
    pdf += obj

xref_start = len(pdf)
pdf += f"xref\n0 {len(offsets)}\n".encode()
pdf += b"0000000000 65535 f \n"
for off in offsets[1:]:
    pdf += f"{off:010d} 00000 n \n".encode()
pdf += f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\n".encode()
pdf += f"startxref\n{xref_start}\n%%EOF\n".encode()

Path("/tmp/agora_smoke.pdf").write_bytes(pdf)
PY

curl -sS -X POST "$BASE_URL/artifacts/$PDF_ARTIFACT_ID/versions" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Idempotency-Key: $(uuid)" \
  -F "file=@/tmp/agora_smoke.pdf" >/dev/null

echo "== ingest_pdf"
curl -sS -X POST "$BASE_URL/workspaces/$WORKSPACE_ID/requests/ingest_pdf" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Idempotency-Key: $(uuid)" \
  -H "Content-Type: application/json" \
  -d "{\"artifact_id\":\"$PDF_ARTIFACT_ID\"}" >/dev/null

echo "== Create claim + evidence"
CLAIM_JSON=$(curl -sS -X POST "$BASE_URL/workspaces/$WORKSPACE_ID/claims" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Idempotency-Key: $(uuid)" \
  -H "Content-Type: application/json" \
  -d '{"kind":"fact","text":"Smoke claim for gate.","confidence":"low"}')
CLAIM_ID=$(printf '%s' "$CLAIM_JSON" | json_get id)

PDF_VERSION_ID=$(PDF_ARTIFACT_ID="$PDF_ARTIFACT_ID" "$PYTHON" - <<'PY'
import os, psycopg2
db_url = os.getenv("DATABASE_URL", "postgresql://agora:agora_dev_password@localhost:5432/agora")
artifact_id = os.environ["PDF_ARTIFACT_ID"]
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute(
    "SELECT id FROM artifact_versions WHERE artifact_id = %s ORDER BY version DESC LIMIT 1",
    (artifact_id,)
)
row = cur.fetchone()
cur.close(); conn.close()
print(row[0])
PY
)

curl -sS -X POST "$BASE_URL/claims/$CLAIM_ID/evidence" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Idempotency-Key: $(uuid)" \
  -H "Content-Type: application/json" \
  -d "{\"artifact_version_id\":\"$PDF_VERSION_ID\",\"location\":\"pdf:p=1#char=0-20\"}" >/dev/null

echo "== Critique claim (Skeptic agent)"
curl -sS -X POST "$BASE_URL/workspaces/$WORKSPACE_ID/critiques" \
  -H "Authorization: Bearer $SECOND_AGENT_JWT" \
  -H "Idempotency-Key: $(uuid)" \
  -H "Content-Type: application/json" \
  -d "{\"target_type\":\"claim\",\"target_id\":\"$CLAIM_ID\",\"severity\":\"minor\",\"message\":\"Smoke critique\"}" >/dev/null

echo "== ingest_repo"
curl -sS -X POST "$BASE_URL/workspaces/$WORKSPACE_ID/requests/ingest_repo" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Idempotency-Key: $(uuid)" \
  -H "Content-Type: application/json" \
  -d "{\"repo_url\":\"$REPO_ROOT\"}" >/dev/null

echo "== run_sandbox"
SCRIPT_ARTIFACT_JSON=$(curl -sS -X POST "$BASE_URL/workspaces/$WORKSPACE_ID/artifacts" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Idempotency-Key: $(uuid)" \
  -H "Content-Type: application/json" \
  -d '{"type":"code","metadata":{"source":"smoke","lang":"python"}}')
SCRIPT_ARTIFACT_ID=$(printf '%s' "$SCRIPT_ARTIFACT_JSON" | json_get id)

cat > /tmp/agora_smoke_script.py <<'EOF'
print("sandbox ok")
for i in range(3):
    print("step", i)
EOF

curl -sS -X POST "$BASE_URL/artifacts/$SCRIPT_ARTIFACT_ID/versions" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Idempotency-Key: $(uuid)" \
  -F "file=@/tmp/agora_smoke_script.py" >/dev/null

curl -sS -X POST "$BASE_URL/workspaces/$WORKSPACE_ID/requests/run_sandbox" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Idempotency-Key: $(uuid)" \
  -H "Content-Type: application/json" \
  -d "{\"script_artifact_id\":\"$SCRIPT_ARTIFACT_ID\"}" >/dev/null

SANDBOX_WORKFLOW_ID=$(WORKSPACE_ID="$WORKSPACE_ID" "$PYTHON" - <<'PY'
import os, psycopg2
db_url = os.getenv("DATABASE_URL", "postgresql://agora:agora_dev_password@localhost:5432/agora")
workspace_id = os.environ["WORKSPACE_ID"]
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute(
    "SELECT id FROM workflow_runs WHERE workspace_id = %s AND workflow_type = 'sandbox_run' ORDER BY started_at DESC LIMIT 1",
    (workspace_id,)
)
row = cur.fetchone()
cur.close(); conn.close()
print(row[0])
PY
)

echo "== Critique sandbox workflow (Method Reviewer)"
curl -sS -X POST "$BASE_URL/workspaces/$WORKSPACE_ID/critiques" \
  -H "Authorization: Bearer $THIRD_AGENT_JWT" \
  -H "Idempotency-Key: $(uuid)" \
  -H "Content-Type: application/json" \
  -d "{\"target_type\":\"workflow_run\",\"target_id\":\"$SANDBOX_WORKFLOW_ID\",\"severity\":\"minor\",\"message\":\"Smoke method review\"}" >/dev/null

echo "== Create draft + version"
DRAFT_JSON=$(curl -sS -X POST "$BASE_URL/workspaces/$WORKSPACE_ID/drafts" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Idempotency-Key: $(uuid)" \
  -H "Content-Type: application/json" \
  -d '{"title":"Smoke Draft"}')
DRAFT_ID=$(printf '%s' "$DRAFT_JSON" | json_get id)

DRAFT_CONTENT=$("$PYTHON" - <<'PY'
import json
print(json.dumps({"content": "Smoke draft content."}))
PY
)

DRAFT_VERSION_JSON=$(curl -sS -X POST "$BASE_URL/drafts/$DRAFT_ID/versions" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Idempotency-Key: $(uuid)" \
  -H "Content-Type: application/json" \
  -d "$DRAFT_CONTENT")
DRAFT_VERSION_ID=$(printf '%s' "$DRAFT_VERSION_JSON" | json_get id)

echo "== Create rule checks (system)"
SYSTEM_JWT=$("$PYTHON" - <<PY
import sys
sys.path.insert(0, "$REPO_ROOT/apps/core-api")
from jwt_utils import create_system_token
print(create_system_token("orchestrator-smoke"))
PY
)

curl -sS -X POST "$BASE_URL/rule-checks" \
  -H "Authorization: Bearer $SYSTEM_JWT" \
  -H "Content-Type: application/json" \
  -d "{\"rule_name\":\"citation_check\",\"target_type\":\"workspace\",\"target_id\":\"$WORKSPACE_ID\",\"status\":\"pass\",\"details\":{\"all_citations_resolve\":true}}" >/dev/null

curl -sS -X POST "$BASE_URL/rule-checks" \
  -H "Authorization: Bearer $SYSTEM_JWT" \
  -H "Content-Type: application/json" \
  -d "{\"rule_name\":\"critique_sufficiency\",\"target_type\":\"workspace\",\"target_id\":\"$WORKSPACE_ID\",\"status\":\"pass\",\"details\":{\"reason\":\"smoke\"}}" >/dev/null

curl -sS -X POST "$BASE_URL/rule-checks" \
  -H "Authorization: Bearer $SYSTEM_JWT" \
  -H "Content-Type: application/json" \
  -d "{\"rule_name\":\"citation_check\",\"target_type\":\"draft_version\",\"target_id\":\"$DRAFT_VERSION_ID\",\"status\":\"pass\",\"details\":{\"all_citations_resolve\":true}}" >/dev/null

curl -sS -X POST "$BASE_URL/rule-checks" \
  -H "Authorization: Bearer $SYSTEM_JWT" \
  -H "Content-Type: application/json" \
  -d "{\"rule_name\":\"critique_sufficiency\",\"target_type\":\"draft_version\",\"target_id\":\"$DRAFT_VERSION_ID\",\"status\":\"pass\",\"details\":{\"reason\":\"smoke\"}}" >/dev/null

wait_for_phase() {
  local target="$1"
  for _ in $(seq 1 20); do
    current=$(curl -sS "$BASE_URL/workspaces/$WORKSPACE_ID/phase" | "$PYTHON" - <<'PY'
import json,sys
print(json.loads(sys.stdin.read())["current_phase"])
PY
)
    if [[ "$current" == "$target" ]]; then
      return 0
    fi
    sleep 1
  done
  echo "Timed out waiting for phase $target" >&2
  exit 1
}

advance_phase() {
  local target="$1"
  curl -sS -X POST "$BASE_URL/workspaces/$WORKSPACE_ID/advance-phase" \
    -H "Authorization: Bearer $SYSTEM_JWT" \
    -H "Content-Type: application/json" \
    -d "{\"target_phase\":\"$target\"}" >/dev/null
  wait_for_phase "$target"
}

echo "== Advance phases to FINALIZED"
advance_phase "LIT_REVIEW"
advance_phase "CLAIM_VALIDATION"
advance_phase "HYPOTHESIS_PLANNING"
advance_phase "EXPERIMENTATION"
advance_phase "SYNTHESIS"
advance_phase "INTERNAL_REVIEW"
advance_phase "FINALIZED"

echo "== Finalize draft (system)"
curl -sS -X POST "$BASE_URL/workspaces/$WORKSPACE_ID/requests/finalize_draft" \
  -H "Authorization: Bearer $SYSTEM_JWT" \
  -H "Content-Type: application/json" \
  -d "{\"draft_artifact_id\":\"$DRAFT_ID\",\"draft_artifact_version_id\":\"$DRAFT_VERSION_ID\"}" >/dev/null

echo "== Summary"
echo "WORKSPACE_ID=$WORKSPACE_ID"
echo "PDF_ARTIFACT_ID=$PDF_ARTIFACT_ID"
echo "CLAIM_ID=$CLAIM_ID"
echo "SANDBOX_WORKFLOW_ID=$SANDBOX_WORKFLOW_ID"
echo "DRAFT_ID=$DRAFT_ID"
echo "DRAFT_VERSION_ID=$DRAFT_VERSION_ID"
echo "OK"
