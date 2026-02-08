#!/usr/bin/env python3
"""
Delete all workspaces except an allowlist (dev utility).

This is intentionally a DB-level tool because the product contract does not
include a "delete workspace" API.

Usage:
  DATABASE_URL=... python3 scripts/edit_tools/prune_workspaces.py --yes
  python3 scripts/edit_tools/prune_workspaces.py --keep-name "Foo" --keep-name "Bar" --yes
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable


DEFAULT_KEEP_NAMES = [
    "Invariant Neural Operators for Turbulent Flow Closure",
    "Cross‑Device Tokamak Disruption Prediction with Transfer and Robustness",
    "Neural‑Operator Full Waveform Inversion that Generalizes to Real Sources",
    "Physics‑Informed Battery Degradation Modeling with Few‑Cycle Data",
    "Scalable Inverse Design of Metamaterials with Data‑Efficient Deep Learning",
]


def _qmarks(n: int) -> str:
    return ", ".join(["%s"] * n)


def _fmt_names(names: Iterable[str]) -> str:
    return "\n".join([f"- {n}" for n in names])


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune workspaces in Postgres (dev utility).")
    parser.add_argument(
        "--keep-name",
        action="append",
        default=[],
        help="Workspace name to keep (repeatable). Defaults to the 5 seeded research problems.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually delete. Without this flag, runs in dry-run mode.",
    )
    args = parser.parse_args()

    keep_names = args.keep_name or list(DEFAULT_KEEP_NAMES)
    db_url = os.getenv("DATABASE_URL", "postgresql://agora:agora_dev_password@localhost:5432/agora")

    try:
        import psycopg2  # type: ignore
    except Exception as exc:
        print(f"ERROR: psycopg2 is required: {exc}", file=sys.stderr)
        return 2

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    try:
        cur = conn.cursor()

        cur.execute("SELECT id, name FROM workspaces ORDER BY created_at ASC;")
        rows = cur.fetchall()
        all_ws = [{"id": str(r[0]), "name": r[1]} for r in rows]

        keep_ids = [w["id"] for w in all_ws if w["name"] in set(keep_names)]
        delete_ws = [w for w in all_ws if w["id"] not in set(keep_ids)]

        missing_keep = [n for n in keep_names if n not in {w["name"] for w in all_ws}]
        if missing_keep:
            print("ERROR: some keep-names were not found in DB (refusing to guess):", file=sys.stderr)
            print(_fmt_names(missing_keep), file=sys.stderr)
            return 2

        print(f"Found {len(all_ws)} workspaces.")
        print(f"Keeping {len(keep_ids)} workspaces:")
        print(_fmt_names([w['name'] for w in all_ws if w['id'] in set(keep_ids)]) or "(none)")
        print(f"Deleting {len(delete_ws)} workspaces:")
        print(_fmt_names([w['name'] for w in delete_ws]) or "(none)")

        if not delete_ws:
            print("Nothing to delete.")
            return 0

        if not args.yes:
            print("\nDry-run only. Re-run with --yes to apply.")
            conn.rollback()
            return 0

        delete_ids = [w["id"] for w in delete_ws]
        in_ids = f"({_qmarks(len(delete_ids))})"

        # Delete in dependency order (mirrors TRUNCATE order in seed scripts).
        # We scope every delete to the workspaces we're removing.

        cur.execute(f"DELETE FROM idempotency_keys WHERE workspace_id IN {in_ids};", delete_ids)
        cur.execute(f"DELETE FROM rule_checks WHERE workspace_id IN {in_ids};", delete_ids)
        cur.execute(f"DELETE FROM critiques WHERE workspace_id IN {in_ids};", delete_ids)
        cur.execute(f"DELETE FROM agent_tasks WHERE workspace_id IN {in_ids};", delete_ids)

        cur.execute(
            f"""
            DELETE FROM activity_runs ar
            USING workflow_runs wr
            WHERE ar.workflow_run_id = wr.id
              AND wr.workspace_id IN {in_ids};
            """,
            delete_ids,
        )
        cur.execute(f"DELETE FROM workflow_runs WHERE workspace_id IN {in_ids};", delete_ids)

        # Search index has ON DELETE CASCADE, but deleting explicitly avoids extra work for FK cascades.
        cur.execute(f"DELETE FROM search_index WHERE workspace_id IN {in_ids};", delete_ids)

        cur.execute(f"DELETE FROM citations WHERE workspace_id IN {in_ids};", delete_ids)

        cur.execute(
            f"""
            DELETE FROM claim_evidence ce
            USING claims c
            WHERE ce.claim_id = c.id
              AND c.workspace_id IN {in_ids};
            """,
            delete_ids,
        )
        cur.execute(f"DELETE FROM claims WHERE workspace_id IN {in_ids};", delete_ids)

        cur.execute(f"DELETE FROM events WHERE workspace_id IN {in_ids};", delete_ids)
        cur.execute(f"DELETE FROM logs WHERE workspace_id IN {in_ids};", delete_ids)

        cur.execute(
            f"""
            DELETE FROM artifact_versions av
            USING artifacts a
            WHERE av.artifact_id = a.id
              AND a.workspace_id IN {in_ids};
            """,
            delete_ids,
        )
        cur.execute(f"DELETE FROM artifacts WHERE workspace_id IN {in_ids};", delete_ids)

        cur.execute(f"DELETE FROM join_requests WHERE workspace_id IN {in_ids};", delete_ids)
        cur.execute(f"DELETE FROM workspace_agents WHERE workspace_id IN {in_ids};", delete_ids)
        cur.execute(f"DELETE FROM workspaces WHERE id IN {in_ids};", delete_ids)

        conn.commit()
        print("\nDone.")
        return 0
    except Exception as exc:
        conn.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

