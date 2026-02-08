#!/usr/bin/env python3
"""
Seed each workspace with a small starter pack of PDFs + (optionally) code repos.

This is a dev tool meant to make the Web UI feel "alive" before any real agents
are collaborating. It uses Core API endpoints so audit/logging/versioning stays
in the platform boundary (no direct DB writes).
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from urllib import parse, request
import xml.etree.ElementTree as ET


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
MOLTBOOK_IDENTITY = os.getenv("MOLTBOOK_IDENTITY", "debug-token-clawdbot")

MAX_PDFS_PER_WORKSPACE = int(os.getenv("MAX_PDFS_PER_WORKSPACE", "2"))
RUN_PDF_INGEST = os.getenv("RUN_PDF_INGEST", "true").lower() in ("1", "true", "yes")

SEED_REPOS = os.getenv("SEED_REPOS", "true").lower() in ("1", "true", "yes")
MAX_REPOS_PER_WORKSPACE = int(os.getenv("MAX_REPOS_PER_WORKSPACE", "1"))

DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("1", "true", "yes")

ARXIV_API = "http://export.arxiv.org/api/query"


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


def get_workspace(jwt, workspace_id):
    return http_json(
        "GET",
        f"{BASE_URL}/workspaces/{workspace_id}",
        headers={"Authorization": f"Bearer {jwt}"},
    )


def get_workspace_artifacts(jwt, workspace_id):
    return http_json(
        "GET",
        f"{BASE_URL}/workspaces/{workspace_id}/artifacts",
        headers={"Authorization": f"Bearer {jwt}"},
    ).get("artifacts", [])


def create_artifact(jwt, workspace_id, artifact_type, metadata):
    if DRY_RUN:
        return {"id": f"dryrun-{uuid.uuid4()}", "workspace_id": workspace_id, "type": artifact_type, "metadata": metadata}
    return http_json(
        "POST",
        f"{BASE_URL}/workspaces/{workspace_id}/artifacts",
        headers={
            "Authorization": f"Bearer {jwt}",
            "Idempotency-Key": str(uuid.uuid4()),
            "Content-Type": "application/json",
        },
        body={"type": artifact_type, "metadata": metadata},
    )


def upload_version(jwt, artifact_id, file_path):
    if DRY_RUN:
        return {"id": f"dryrun-{uuid.uuid4()}", "artifact_id": artifact_id, "version": 1}
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


def request_ingest_pdf(jwt, workspace_id, artifact_id):
    if DRY_RUN:
        return {"workflow_run_id": f"dryrun-{uuid.uuid4()}"}
    return http_json(
        "POST",
        f"{BASE_URL}/workspaces/{workspace_id}/requests/ingest_pdf",
        headers={
            "Authorization": f"Bearer {jwt}",
            "Idempotency-Key": f"seed:ingest_pdf:{artifact_id}",
            "Content-Type": "application/json",
        },
        body={"artifact_id": artifact_id},
    )


def request_ingest_repo(jwt, workspace_id, repo_url):
    if DRY_RUN:
        return {"artifact_id": f"dryrun-{uuid.uuid4()}", "activity_run_id": f"dryrun-{uuid.uuid4()}"}
    return http_json(
        "POST",
        f"{BASE_URL}/workspaces/{workspace_id}/requests/ingest_repo",
        headers={
            "Authorization": f"Bearer {jwt}",
            "Idempotency-Key": f"seed:ingest_repo:{repo_url}",
            "Content-Type": "application/json",
        },
        body={"repo_url": repo_url},
    )


def _safe_ascii(s: str) -> str:
    s = s or ""
    # Replace common Unicode dashes with spaces before ASCII-stripping so we
    # don't accidentally join words (e.g. "Physics‑Informed" -> "PhysicsInformed").
    for ch in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"):
        s = s.replace(ch, " ")
    return s.encode("ascii", "ignore").decode("ascii")


def _normalize_query(text: str) -> str:
    text = _safe_ascii(text)
    text = re.sub(r"[^A-Za-z0-9\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def arxiv_search(query: str, max_results: int = 8):
    qs = {
        "search_query": query,
        "start": "0",
        "max_results": str(max_results),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API}?{parse.urlencode(qs)}"
    # Use curl rather than urllib to avoid local Python SSL/cert-store issues
    # that can show up in some dev environments.
    resp = subprocess.run(
        [
            "curl",
            "-sS",
            "-L",
            "--max-time",
            "20",
            "--retry",
            "2",
            "--retry-delay",
            "1",
            url,
        ],
        capture_output=True,
        check=True,
    )
    feed = resp.stdout

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(feed)
    entries = []
    for entry in root.findall("atom:entry", ns):
        entry_id = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        published = (entry.findtext("atom:published", default="", namespaces=ns) or "").strip()

        m = re.search(r"/abs/([^\s/]+)$", entry_id)
        if not m:
            continue
        raw = m.group(1)
        arxiv_id = re.sub(r"v\d+$", "", raw)

        pdf_url = None
        for link in entry.findall("atom:link", ns):
            if link.attrib.get("title") == "pdf" and link.attrib.get("href"):
                pdf_url = link.attrib["href"]
                break
        if not pdf_url:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        year = None
        if len(published) >= 4 and published[:4].isdigit():
            year = int(published[:4])

        entries.append(
            {
                "arxiv_id": arxiv_id,
                "title": re.sub(r"\s+", " ", title),
                "source_url": f"https://arxiv.org/abs/{arxiv_id}",
                "pdf_url": pdf_url,
                "year": year,
            }
        )

    return entries


def download_to_temp(url: str, suffix: str):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    cmd = ["curl", "-sS", "-L", "-o", path, url]
    subprocess.run(cmd, check=True)
    return path


def _metadata_dict(meta):
    if isinstance(meta, dict):
        return meta
    if isinstance(meta, str):
        try:
            return json.loads(meta)
        except Exception:
            return {}
    return {}


def _repo_pack_for_workspace(name: str):
    # Curated, intentionally small set of repos that are likely to clone on dev machines.
    packs = [
        ("Turbulent Flow Closure", ["https://github.com/neuraloperator/neuraloperator.git"]),
        ("Tokamak Disruption", ["https://github.com/google-deepmind/torax.git"]),
        ("Full Waveform Inversion", ["https://github.com/ar4/deepwave.git"]),
        ("Battery Degradation", ["https://github.com/pybamm-team/PyBaMM.git"]),
        ("Metamaterials", ["https://github.com/NanoComp/meep.git"]),
    ]
    for needle, urls in packs:
        if needle.lower() in (name or "").lower():
            return urls
    return []


def main():
    jwt = auth_agent_jwt()
    workspaces = get_workspaces(jwt)

    results = []
    for ws in workspaces:
        ws_id = ws["id"]
        ws_detail = get_workspace(jwt, ws_id)
        ws_name = ws_detail.get("workspace", {}).get("name") or ws.get("name") or ws_id
        ws_desc = ws_detail.get("workspace", {}).get("description") or ""

        existing = get_workspace_artifacts(jwt, ws_id)
        existing_pdf_arxiv = {
            _metadata_dict(a.get("metadata")).get("arxiv_id")
            for a in existing
            if a.get("type") == "pdf"
        }
        existing_pdf_arxiv.discard(None)

        existing_code_repos = {
            _metadata_dict(a.get("metadata")).get("repo_url")
            for a in existing
            if a.get("type") == "code"
        }
        existing_code_repos.discard(None)

        ws_result = {"workspace_id": ws_id, "workspace_name": ws_name, "pdfs": [], "repos": [], "skips": []}

        # PDFs (arXiv)
        # Use workspace name only (keep query stable + short). Description can
        # be long and introduce low-signal tokens.
        query_phrase = _normalize_query(ws_name)[:140]
        arxiv_query = f'all:"{query_phrase}"' if query_phrase else 'all:"machine learning"'

        candidates = []
        try:
            candidates = arxiv_search(arxiv_query, max_results=25)

            # Also run a broader keyword query so we can still seed additional
            # papers even when the exact phrase only matches an already-seeded
            # item.
            stop = {"with", "from", "that", "this", "into", "across", "data", "deep", "learning"}
            words = [w for w in (query_phrase or "").lower().split(" ") if len(w) >= 4 and w not in stop][:8]
            if words:
                broad = " AND ".join([f"all:{w}" for w in words[:6]])
                candidates.extend(arxiv_search(broad, max_results=25))

            # De-dupe by arXiv id while preserving order.
            seen = set()
            uniq = []
            for p in candidates:
                aid = p.get("arxiv_id")
                if not aid or aid in seen:
                    continue
                seen.add(aid)
                uniq.append(p)
            candidates = uniq

            # Heuristic fallbacks for very specific workspace names that often
            # return 0-1 results.
            if len(candidates) < 5:
                low_name = (ws_name or "").lower()
                extra_queries = []
                if "turbulent" in low_name or "turbulence" in low_name:
                    extra_queries.extend(
                        [
                            'all:"neural operator" AND all:turbulence',
                            'all:turbulence AND all:closure',
                        ]
                    )
                if "tokamak" in low_name or "disruption" in low_name:
                    extra_queries.extend(
                        [
                            "all:tokamak AND all:disruption",
                            'all:"disruption prediction"',
                        ]
                    )
                for eq in extra_queries:
                    candidates.extend(arxiv_search(eq, max_results=25))

                # Re-dedupe after adding extra candidates.
                seen = set()
                uniq = []
                for p in candidates:
                    aid = p.get("arxiv_id")
                    if not aid or aid in seen:
                        continue
                    seen.add(aid)
                    uniq.append(p)
                candidates = uniq
        except Exception as e:
            ws_result["skips"].append({"kind": "arxiv_search_failed", "error": str(e)})

        added = 0
        for paper in candidates:
            if added >= MAX_PDFS_PER_WORKSPACE:
                break
            if paper["arxiv_id"] in existing_pdf_arxiv:
                continue

            meta = {
                "title": paper["title"],
                "source": "arXiv",
                "source_url": paper["source_url"],
                "arxiv_id": paper["arxiv_id"],
                "year": paper.get("year"),
            }
            ws_result["pdfs"].append({"action": "create", "arxiv_id": paper["arxiv_id"], "title": paper["title"]})

            if DRY_RUN:
                added += 1
                continue

            pdf_path = download_to_temp(paper["pdf_url"], suffix=".pdf")
            try:
                with open(pdf_path, "rb") as f:
                    head = f.read(4)
                if head != b"%PDF":
                    ws_result["skips"].append({"kind": "download_not_pdf", "arxiv_id": paper["arxiv_id"], "pdf_url": paper["pdf_url"]})
                    continue

                artifact = create_artifact(jwt, ws_id, "pdf", meta)
                upload_version(jwt, artifact["id"], pdf_path)
                if RUN_PDF_INGEST:
                    request_ingest_pdf(jwt, ws_id, artifact["id"])
                added += 1
            finally:
                try:
                    os.remove(pdf_path)
                except OSError:
                    pass

        # Code repos
        if SEED_REPOS and MAX_REPOS_PER_WORKSPACE > 0:
            urls = _repo_pack_for_workspace(ws_name)[:MAX_REPOS_PER_WORKSPACE]
            for repo_url in urls:
                if repo_url in existing_code_repos:
                    continue
                ws_result["repos"].append({"action": "ingest", "repo_url": repo_url})
                if not DRY_RUN:
                    try:
                        request_ingest_repo(jwt, ws_id, repo_url)
                    except Exception as e:
                        ws_result["skips"].append({"kind": "repo_ingest_failed", "repo_url": repo_url, "error": str(e)})

        results.append(ws_result)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
