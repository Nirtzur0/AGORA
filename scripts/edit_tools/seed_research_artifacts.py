#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import uuid
from urllib import request


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
MOLTBOOK_IDENTITY = os.getenv("MOLTBOOK_IDENTITY", "debug-token-clawdbot")


def http_json(method, url, headers=None, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = request.Request(url, data=data, headers=headers or {}, method=method)
    with request.urlopen(req) as resp:
        payload = resp.read().decode("utf-8")
        return json.loads(payload) if payload else {}


def auth_agent_jwt():
    resp = http_json(
        "POST",
        f"{BASE_URL}/auth/moltbook",
        headers={"X-Moltbook-Identity": MOLTBOOK_IDENTITY},
    )
    return resp["agent_session_jwt"]


def get_workspaces(jwt):
    return http_json(
        "GET",
        f"{BASE_URL}/workspaces",
        headers={"Authorization": f"Bearer {jwt}"},
    )

def get_workspace_artifacts(jwt, workspace_id):
    return http_json(
        "GET",
        f"{BASE_URL}/workspaces/{workspace_id}/artifacts",
        headers={"Authorization": f"Bearer {jwt}"},
    )


def create_artifact(jwt, workspace_id, metadata):
    return http_json(
        "POST",
        f"{BASE_URL}/workspaces/{workspace_id}/artifacts",
        headers={
            "Authorization": f"Bearer {jwt}",
            "Idempotency-Key": str(uuid.uuid4()),
            "Content-Type": "application/json",
        },
        body={"type": "pdf", "metadata": metadata},
    )


def upload_version(jwt, artifact_id, file_path):
    cmd = [
        "curl",
        "-sS",
        "-X",
        "POST",
        f"{BASE_URL}/artifacts/{artifact_id}/versions",
        "-H",
        f"Authorization: Bearer {jwt}",
        "-H",
        f"Idempotency-Key: {uuid.uuid4()}",
        "-F",
        f"file=@{file_path}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout) if result.stdout else {}


def download_pdf(url):
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    cmd = ["curl", "-sS", "-L", "-o", path, url]
    subprocess.run(cmd, check=True)
    return path


def main():
    jwt = auth_agent_jwt()

    workspaces = get_workspaces(jwt)
    ws_by_name = {ws["name"]: ws["id"] for ws in workspaces}

    targets = [
        {
            "workspace_name": "Invariant Neural Operators for Turbulent Flow Closure",
            "title": "Physical invariance in neural networks for subgrid-scale scalar flux modeling",
            "source_url": "https://arxiv.org/abs/2010.04663",
            "pdf_url": "https://arxiv.org/pdf/2010.04663.pdf",
            "arxiv_id": "2010.04663",
            "year": 2020,
        },
        {
            "workspace_name": "Cross‑Device Tokamak Disruption Prediction with Transfer and Robustness",
            "title": "Transferable Cross-Tokamak Disruption Prediction with Deep Hybrid Neural Network Feature Extractor",
            "source_url": "https://arxiv.org/abs/2208.09594",
            "pdf_url": "https://arxiv.org/pdf/2208.09594.pdf",
            "arxiv_id": "2208.09594",
            "year": 2022,
        },
        {
            "workspace_name": "Neural‑Operator Full Waveform Inversion that Generalizes to Real Sources",
            "title": "Ambient Noise Full Waveform Inversion with Neural Operators",
            "source_url": "https://arxiv.org/abs/2503.15013",
            "pdf_url": "https://arxiv.org/pdf/2503.15013.pdf",
            "arxiv_id": "2503.15013",
            "year": 2025,
        },
        {
            "workspace_name": "Physics‑Informed Battery Degradation Modeling with Few‑Cycle Data",
            "title": "Physics-informed battery degradation prediction with PI-LSTM",
            "source_url": "https://arxiv.org/abs/2404.04429",
            "pdf_url": "https://arxiv.org/pdf/2404.04429.pdf",
            "arxiv_id": "2404.04429",
            "year": 2024,
        },
        {
            "workspace_name": "Scalable Inverse Design of Metamaterials with Data‑Efficient Deep Learning",
            "title": "Probabilistic representation and inverse design of metamaterials based on a deep generative model",
            "source_url": "https://arxiv.org/abs/1901.10819",
            "pdf_url": "https://arxiv.org/pdf/1901.10819.pdf",
            "arxiv_id": "1901.10819",
            "year": 2019,
        },
    ]

    created = []
    for item in targets:
        ws_id = ws_by_name.get(item["workspace_name"])
        if not ws_id:
            print(f"SKIP: workspace not found: {item['workspace_name']}", file=sys.stderr)
            continue

        # Idempotency: skip if this arXiv id already exists in workspace.
        try:
            existing = get_workspace_artifacts(jwt, ws_id).get("artifacts", [])
        except Exception:
            existing = []
        if any(
            (a.get("type") == "pdf")
            and isinstance(a.get("metadata"), dict)
            and (a["metadata"].get("arxiv_id") == item["arxiv_id"])
            for a in existing
        ):
            print(f"SKIP: already seeded arXiv {item['arxiv_id']} in workspace {item['workspace_name']}", file=sys.stderr)
            continue

        metadata = {
            "title": item["title"],
            "source": "arXiv",
            "source_url": item["source_url"],
            "arxiv_id": item["arxiv_id"],
            "year": item["year"],
        }
        artifact = create_artifact(jwt, ws_id, metadata)
        pdf_path = download_pdf(item["pdf_url"])
        try:
            upload_version(jwt, artifact["id"], pdf_path)
        finally:
            try:
                os.remove(pdf_path)
            except OSError:
                pass
        created.append(
            {
                "workspace_id": ws_id,
                "artifact_id": artifact["id"],
                "title": item["title"],
                "arxiv_id": item["arxiv_id"],
            }
        )

    print(json.dumps(created, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
