#!/usr/bin/env python3
"""Minimal artifact-store manager.

This script is intentionally scheme-focused:
- no web search
- no URL fetching/downloading
- not for web-app runtime/E2E evidence capture

Use it after artifacts are already fetched/saved by the agent workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


INDEX_VERSION = 1


def _now_rfc3339_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_index(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": INDEX_VERSION, "artifacts": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != INDEX_VERSION:
        raise ValueError(f"Unsupported index format/version: {path}")
    if not isinstance(data.get("artifacts"), list):
        raise ValueError(f"Index missing 'artifacts' list: {path}")
    return data


def _write_index(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve_paths(repo_root_arg: str, store_root_arg: Optional[str]) -> tuple[Path, Path, Path, Path, Path]:
    repo_root = Path(repo_root_arg).resolve()
    if store_root_arg:
        store_root = Path(store_root_arg)
        if not store_root.is_absolute():
            store_root = (repo_root / store_root).resolve()
    else:
        store_root = (repo_root / "docs" / "artifacts") if (repo_root / "docs").exists() else (repo_root / "artifacts")
    index_path = store_root / "index.json"
    blobs_dir = store_root / "blobs"
    excerpts_dir = store_root / "excerpts"
    return repo_root, store_root, index_path, blobs_dir, excerpts_dir


def _compact_relpath(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)


def _append(index_path: Path, artifact: dict[str, Any]) -> None:
    index = _load_index(index_path)
    artifacts: list[dict[str, Any]] = index["artifacts"]

    aid = artifact.get("id")
    if not isinstance(aid, str) or not aid:
        raise ValueError("artifact id missing/invalid")
    if any(a.get("id") == aid for a in artifacts):
        raise ValueError(f"artifact id already exists: {aid}")

    artifacts.append({k: v for k, v in artifact.items() if v not in (None, "", [], {})})
    _write_index(index_path, index)


def cmd_init(args: argparse.Namespace) -> int:
    repo_root, store_root, index_path, blobs_dir, excerpts_dir = _resolve_paths(args.repo_root, args.store_root)
    blobs_dir.mkdir(parents=True, exist_ok=True)
    excerpts_dir.mkdir(parents=True, exist_ok=True)
    if not index_path.exists():
        _write_index(index_path, {"version": INDEX_VERSION, "artifacts": []})

    readme = store_root / "README.md"
    if not readme.exists():
        readme.write_text(
            "\n".join(
                [
                    "# Artifacts",
                    "",
                    "External artifacts captured for grounding and traceability.",
                    "",
                    "- `index.json`: machine-readable index",
                    "- `blobs/`: content-addressed snapshots (SHA256 filename)",
                    "- `excerpts/`: short notes/snippets keyed by artifact id",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    print(f"Repo root: {repo_root}")
    print(f"Store root: {store_root}")
    print(f"Index: {index_path}")
    return 0


def cmd_add_file(args: argparse.Namespace) -> int:
    repo_root, store_root, index_path, blobs_dir, _ = _resolve_paths(args.repo_root, args.store_root)
    store_root.mkdir(parents=True, exist_ok=True)
    blobs_dir.mkdir(parents=True, exist_ok=True)
    if not index_path.exists():
        _write_index(index_path, {"version": INDEX_VERSION, "artifacts": []})

    src = Path(args.file).expanduser().resolve()
    if not src.exists() or not src.is_file():
        raise ValueError(f"--file must be an existing file: {src}")

    retrieved_at = _now_rfc3339_utc()
    sha256 = _sha256_file(src)
    ext = src.suffix.lower() if src.suffix else ".bin"
    blob_path = blobs_dir / f"{sha256}{ext}"
    if not blob_path.exists():
        shutil.copyfile(src, blob_path)

    url = args.url.strip() if args.url else f"file:{src.name}"
    url_hash = _sha256_text(url)[:10]
    content_hash = sha256[:10]
    date = retrieved_at[:10].replace("-", "")
    artifact_id = args.id or f"{date}-{url_hash}-{content_hash}"

    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
    source = {"doi": args.doi.strip()} if args.doi else None

    artifact = {
        "id": artifact_id,
        "kind": args.kind or "other",
        "title": args.title,
        "url": url,
        "retrieved_at": retrieved_at,
        "sha256": sha256,
        "local_path": _compact_relpath(blob_path, repo_root),
        "tags": tags or None,
        "notes": args.notes,
        "source": source,
    }

    index = _load_index(index_path)
    for a in index["artifacts"]:
        if a.get("url") == url and a.get("sha256") == sha256:
            print(f"Already captured: id={a.get('id')}")
            return 0

    _append(index_path, artifact)
    print(f"Added: id={artifact_id}")
    print(f"URL: {url}")
    print(f"Blob: {artifact['local_path']}")
    return 0


def cmd_add_meta(args: argparse.Namespace) -> int:
    _, store_root, index_path, _, _ = _resolve_paths(args.repo_root, args.store_root)
    store_root.mkdir(parents=True, exist_ok=True)
    if not index_path.exists():
        _write_index(index_path, {"version": INDEX_VERSION, "artifacts": []})

    url = (args.url or "").strip()
    if not url:
        raise ValueError("--url is required")

    retrieved_at = _now_rfc3339_utc()
    url_hash = _sha256_text(url)[:10]
    date = retrieved_at[:10].replace("-", "")
    artifact_id = args.id or f"{date}-{url_hash}-meta"

    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
    source = {"doi": args.doi.strip()} if args.doi else None

    artifact = {
        "id": artifact_id,
        "kind": args.kind or "other",
        "title": args.title,
        "url": url,
        "retrieved_at": retrieved_at,
        "tags": tags or None,
        "notes": args.notes,
        "source": source,
    }

    index = _load_index(index_path)
    for a in index["artifacts"]:
        if a.get("url") == url and not a.get("local_path"):
            print(f"Already present (metadata-only): id={a.get('id')}")
            return 0

    _append(index_path, artifact)
    print(f"Added (metadata-only): id={artifact_id}")
    print(f"URL: {url}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    repo_root, _, index_path, _, _ = _resolve_paths(args.repo_root, args.store_root)
    index = _load_index(index_path)

    ok = True
    seen: set[str] = set()
    for a in index["artifacts"]:
        aid = a.get("id")
        if not isinstance(aid, str) or not aid:
            print("Invalid artifact with missing id")
            ok = False
            continue
        if aid in seen:
            print(f"Duplicate id: {aid}")
            ok = False
        seen.add(aid)

        lp = a.get("local_path")
        if lp and not (repo_root / str(lp)).exists():
            print(f"Missing local_path for id={aid}: {lp}")
            ok = False

        h = a.get("sha256")
        if h and not re.fullmatch(r"[0-9a-f]{64}", str(h)):
            print(f"Invalid sha256 for id={aid}: {h}")
            ok = False
        if lp and not h:
            print(f"Missing sha256 for id={aid} with local_path present")
            ok = False

    if ok:
        print(f"OK: {len(index['artifacts'])} artifacts")
        return 0
    return 2


def cmd_list(args: argparse.Namespace) -> int:
    _, _, index_path, _, _ = _resolve_paths(args.repo_root, args.store_root)
    index = _load_index(index_path)
    for a in index["artifacts"]:
        print("-" * 80)
        print(f"id: {a.get('id')}")
        print(f"kind: {a.get('kind')}")
        if a.get("title"):
            print(f"title: {a.get('title')}")
        print(f"url: {a.get('url')}")
        print(f"retrieved_at: {a.get('retrieved_at')}")
        if a.get("local_path"):
            print(f"local_path: {a.get('local_path')}")
        if a.get("source"):
            print(f"source: {a.get('source')}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="web_artifacts.py",
        description=(
            "Manage local external-source artifacts (index + blobs). "
            "This tool does not perform internet fetching or web-app runtime capture."
        ),
    )
    p.add_argument("--repo-root", default=".", help="Target repo root (default: cwd)")
    p.add_argument("--store-root", default=None, help="Override store root (relative or absolute).")

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="Initialize store layout + index.json.")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("add-file", help="Ingest a local file into blobs/ and index it.")
    sp.add_argument("--file", required=True, help="Path to a downloaded/supplied artifact file.")
    sp.add_argument("--url", default=None, help="Optional source URL; defaults to file:<name> if omitted.")
    sp.add_argument("--id", default=None)
    sp.add_argument("--kind", default=None)
    sp.add_argument("--title", default=None)
    sp.add_argument("--doi", default=None)
    sp.add_argument("--tags", default=None, help="Comma-separated tags.")
    sp.add_argument("--notes", default=None)
    sp.set_defaults(func=cmd_add_file)

    sp = sub.add_parser("add-meta", help="Add metadata-only artifact (no blob).")
    sp.add_argument("--url", required=True)
    sp.add_argument("--id", default=None)
    sp.add_argument("--kind", default=None)
    sp.add_argument("--title", default=None)
    sp.add_argument("--doi", default=None)
    sp.add_argument("--tags", default=None, help="Comma-separated tags.")
    sp.add_argument("--notes", default=None)
    sp.set_defaults(func=cmd_add_meta)

    sp = sub.add_parser("validate", help="Validate index.json consistency and local paths.")
    sp.set_defaults(func=cmd_validate)

    sp = sub.add_parser("list", help="List artifacts in index.json.")
    sp.set_defaults(func=cmd_list)

    return p


def main(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
