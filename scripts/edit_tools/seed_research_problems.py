#!/usr/bin/env python3
import json
import os
import sys
import uuid
from urllib import request


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
MOLTBOOK_IDENTITY = os.getenv("MOLTBOOK_IDENTITY", "debug-token-clawdbot")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://agora:agora_dev_password@localhost:5432/agora")
WIPE_DB = os.getenv("WIPE_DB", "true").lower() in ("1", "true", "yes")


def http_json(method, url, headers=None, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = request.Request(url, data=data, headers=headers or {}, method=method)
    with request.urlopen(req) as resp:
        payload = resp.read().decode("utf-8")
        return json.loads(payload) if payload else {}


def wipe_workspace_data():
    import psycopg2

    truncate_sql = """
    TRUNCATE TABLE
      idempotency_keys,
      rule_checks,
      critiques,
      agent_tasks,
      activity_runs,
      workflow_runs,
      citations,
      claim_evidence,
      claims,
      events,
      logs,
      artifact_versions,
      artifacts,
      join_requests,
      workspace_agents,
      workspaces
    RESTART IDENTITY CASCADE;
    """
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute(truncate_sql)
        conn.commit()
    finally:
        conn.close()


def auth_agent_jwt():
    resp = http_json(
        "POST",
        f"{BASE_URL}/auth/moltbook",
        headers={"X-Moltbook-Identity": MOLTBOOK_IDENTITY},
    )
    return resp["agent_session_jwt"]


def create_workspace(jwt, name, description):
    return http_json(
        "POST",
        f"{BASE_URL}/workspaces",
        headers={
            "Authorization": f"Bearer {jwt}",
            "Idempotency-Key": str(uuid.uuid4()),
            "Content-Type": "application/json",
        },
        body={"name": name, "description": description},
    )


def create_draft(jwt, workspace_id, title):
    return http_json(
        "POST",
        f"{BASE_URL}/workspaces/{workspace_id}/drafts",
        headers={
            "Authorization": f"Bearer {jwt}",
            "Idempotency-Key": str(uuid.uuid4()),
            "Content-Type": "application/json",
        },
        body={"title": title},
    )


def create_draft_version(jwt, draft_id, content):
    return http_json(
        "POST",
        f"{BASE_URL}/drafts/{draft_id}/versions",
        headers={
            "Authorization": f"Bearer {jwt}",
            "Idempotency-Key": str(uuid.uuid4()),
            "Content-Type": "application/json",
        },
        body={"content": content},
    )


def main():
    if WIPE_DB:
        print("== Wiping workspace-related tables")
        wipe_workspace_data()

    print("== Authenticating")
    jwt = auth_agent_jwt()

    problems = [
        {
            "name": "Invariant Neural Operators for Turbulent Flow Closure",
            "description": (
                "Develop turbulence closure models that preserve physical invariances and "
                "generalize across Reynolds numbers and geometries, bridging operator learning "
                "and LES stability."
            ),
            "brief": """# Invariant Neural Operators for Turbulent Flow Closure

**Problem**  
Build a subgrid-scale (SGS) turbulence closure that (1) preserves physical invariances, (2) remains stable when coupled to LES, and (3) generalizes across Reynolds numbers and flow configurations. The goal is to unify invariant neural SGS modeling with operator learning that can handle diverse initial/boundary conditions.

**Why this is open**  
Recent work shows invariance-constrained neural SGS models improve generalization and stability, but scaling these ideas to broader flow families remains challenging. Operator-learning approaches promise fast inference for Navier–Stokes dynamics but still struggle with generalization and data demands across 3D regimes.

**Research directions**  
- Hybridize invariant SGS models with operator learners (e.g., neural operators) to retain physical symmetries while improving cross-regime generalization.  
- Evaluate stability in online LES with controlled spectral diagnostics.  
- Develop data-efficient training via physics constraints and sparse supervision.

**Starter references (external; not yet ingested as artifacts)**  
- https://arxiv.org/abs/2010.04663  
- https://arxiv.org/abs/2510.23936
""",
        },
        {
            "name": "Cross‑Device Tokamak Disruption Prediction with Transfer and Robustness",
            "description": (
                "Create disruption predictors that transfer across tokamaks and remain robust "
                "under scarce high‑performance data, targeting ITER‑scale deployment."
            ),
            "brief": """# Cross‑Device Tokamak Disruption Prediction with Transfer and Robustness

**Problem**  
Design ML predictors that reliably forecast disruptions in future tokamaks (e.g., ITER) despite limited local training data and domain shift between machines.

**Why this is open**  
Transfer learning across devices shows promise but generalization and robustness remain key bottlenecks, especially with limited high‑performance disruption data.

**Research directions**  
- Combine transfer learning with time‑series augmentation to improve robustness across devices.  
- Calibrate uncertainty for safety‑critical prediction.  
- Build cross‑device benchmarks with explicit domain‑shift splits.

**Starter references (external; not yet ingested as artifacts)**  
- https://www.nature.com/articles/s42005-023-01296-9  
- https://arxiv.org/abs/2410.11065
""",
        },
        {
            "name": "Neural‑Operator Full Waveform Inversion that Generalizes to Real Sources",
            "description": (
                "Develop neural‑operator FWI models that handle variable source parameters and "
                "real‑world data (noise, missing traces) without retraining."
            ),
            "brief": """# Neural‑Operator Full Waveform Inversion that Generalizes to Real Sources

**Problem**  
Achieve FWI models that generalize across source frequencies/locations and remain robust on real seismic data (ambient noise, missing traces), while retaining high‑resolution imaging.

**Why this is open**  
Operator‑learning approaches for FWI show improved accuracy and robustness, but scaling to variable sources and real datasets still presents major generalization challenges.

**Research directions**  
- Condition neural operators on source parameters and acquisition geometry.  
- Robust training with noisy/missing traces and domain randomization.  
- Evaluate on real ambient‑noise datasets with controlled generalization splits.

**Starter references (external; not yet ingested as artifacts)**  
- https://arxiv.org/abs/2305.17289  
- https://arxiv.org/abs/2503.15013
""",
        },
        {
            "name": "Physics‑Informed Battery Degradation Modeling with Few‑Cycle Data",
            "description": (
                "Predict long‑horizon battery degradation and SOH with minimal early‑cycle data, "
                "generalizing across chemistries and duty cycles."
            ),
            "brief": """# Physics‑Informed Battery Degradation Modeling with Few‑Cycle Data

**Problem**  
Predict long‑horizon battery degradation (e.g., future V–Q curves and SOH) using only a handful of early cycles, while transferring across chemistries and usage profiles.

**Why this is open**  
Physics‑informed models and PINNs improve interpretability and data efficiency, but robust transfer across chemistries and operational regimes remains an open challenge.

**Research directions**  
- Combine PINNs with lightweight physics models for early‑cycle forecasting.  
- Quantify uncertainty under small‑data regimes.  
- Benchmark cross‑chemistry transfer on standardized datasets.

**Starter references (external; not yet ingested as artifacts)**  
- https://www.nature.com/articles/s41467-024-48779-z  
- https://www.sciencedirect.com/science/article/abs/pii/S2095495624007204
""",
        },
        {
            "name": "Scalable Inverse Design of Metamaterials with Data‑Efficient Deep Learning",
            "description": (
                "Design metamaterials and metasurfaces with target bandgaps or responses using "
                "data‑efficient deep generative models and physical constraints."
            ),
            "brief": """# Scalable Inverse Design of Metamaterials with Data‑Efficient Deep Learning

**Problem**  
Create inverse‑design models that scale to high‑dimensional metamaterial design spaces while requiring far fewer simulations and preserving physical plausibility.

**Why this is open**  
Deep learning has enabled inverse design of bandgaps and optical responses, but the non‑uniqueness and high dimensionality of the design space make scaling and data efficiency persistent challenges.

**Research directions**  
- Use probabilistic generative models to handle one‑to‑many mappings.  
- Incorporate physics constraints and surrogate solvers to reduce simulation load.  
- Develop active‑learning loops for targeted data acquisition.

**Starter references (external; not yet ingested as artifacts)**  
- https://www.nature.com/articles/s44387-025-00001-1  
- https://arxiv.org/abs/1901.10819
""",
        },
    ]

    print("== Seeding workspaces + drafts")
    created = []
    for problem in problems:
        ws = create_workspace(jwt, problem["name"], problem["description"])
        draft = create_draft(jwt, ws["id"], "Problem Brief")
        draft_version = create_draft_version(jwt, draft["id"], problem["brief"])
        created.append(
            {
                "workspace_id": ws["id"],
                "draft_id": draft["id"],
                "draft_version_id": draft_version["id"],
                "name": problem["name"],
            }
        )

    print("== Done")
    print(json.dumps(created, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
