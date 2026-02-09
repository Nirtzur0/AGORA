#!/usr/bin/env python3
"""Check artifact metadata freshness and provenance coverage.

Fails when artifact entries are missing required provenance fields or when
`retrieved_at` age exceeds the configured threshold.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_iso8601_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _load_index(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError(f"invalid index format (missing artifacts list): {path}")
    return artifacts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate artifact provenance coverage and retrieval freshness."
    )
    parser.add_argument(
        "--index",
        default="Docs/artifacts/index.json",
        help="Path to artifact index.json",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=90,
        help="Fail when retrieved_at is older than this threshold.",
    )
    parser.add_argument(
        "--warn-age-days",
        type=int,
        default=75,
        help="Warn when retrieved_at age exceeds this threshold.",
    )
    args = parser.parse_args()

    index_path = Path(args.index)
    if not index_path.exists():
        raise SystemExit(f"index file not found: {index_path}")

    artifacts = _load_index(index_path)
    now = datetime.now(timezone.utc)
    required_fields = ("id", "url", "retrieved_at")

    missing: list[tuple[str, list[str]]] = []
    invalid_ts: list[tuple[str, str]] = []
    stale: list[tuple[str, int]] = []
    warn: list[tuple[str, int]] = []

    for artifact in artifacts:
        aid = str(artifact.get("id") or "<missing-id>")
        missing_fields = [field for field in required_fields if not artifact.get(field)]
        if missing_fields:
            missing.append((aid, missing_fields))
            continue

        retrieved_at = str(artifact["retrieved_at"])
        try:
            age_days = int((now - _parse_iso8601_utc(retrieved_at)).total_seconds() // 86400)
        except Exception:
            invalid_ts.append((aid, retrieved_at))
            continue

        if age_days > args.max_age_days:
            stale.append((aid, age_days))
        elif age_days > args.warn_age_days:
            warn.append((aid, age_days))

    coverage = (
        0.0 if not artifacts else ((len(artifacts) - len(missing) - len(invalid_ts)) / len(artifacts)) * 100.0
    )
    print(
        "artifact_freshness_summary "
        f"artifacts={len(artifacts)} "
        f"coverage_percent={coverage:.1f} "
        f"warnings={len(warn)} "
        f"stale={len(stale)} "
        f"missing={len(missing)} "
        f"invalid_timestamps={len(invalid_ts)} "
        f"max_age_days={args.max_age_days}"
    )

    for aid, fields in missing:
        print(f"MISSING_PROVENANCE id={aid} fields={','.join(fields)}")
    for aid, value in invalid_ts:
        print(f"INVALID_RETRIEVED_AT id={aid} value={value}")
    for aid, age in warn:
        print(f"FRESHNESS_WARN id={aid} age_days={age} threshold={args.warn_age_days}")
    for aid, age in stale:
        print(f"FRESHNESS_STALE id={aid} age_days={age} threshold={args.max_age_days}")

    if missing or invalid_ts or stale:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
