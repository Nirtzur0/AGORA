#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys


DEFAULT_TEST_PATH = "tests/e2e"


def _parse_warning_count(output: str) -> int:
    matches = re.findall(r"(\d+)\s+warnings?\s+in\s+[0-9.]+s", output)
    if matches:
        return int(matches[-1])
    if "warnings summary" in output:
        return 1
    return 0


def _run_pytest(python_bin: str, test_path: str) -> tuple[int, str, str]:
    env = os.environ.copy()
    env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    command = [
        python_bin,
        "-m",
        "pytest",
        "-p",
        "pytest_asyncio.plugin",
        "-q",
        test_path,
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=env,
    )
    return completed.returncode, completed.stdout, completed.stderr


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run full e2e pytest selector and enforce a warning budget."
        )
    )
    parser.add_argument(
        "--python",
        default=os.environ.get("PYTHON", "python3"),
        help="Python binary used to run pytest.",
    )
    parser.add_argument(
        "--test-path",
        default=DEFAULT_TEST_PATH,
        help="Pytest path or node id for full e2e checks.",
    )
    parser.add_argument(
        "--max-warnings",
        type=int,
        default=int(os.environ.get("E2E_FULL_WARNING_BUDGET", "200")),
        help="Maximum allowed warning count before failing.",
    )
    args = parser.parse_args()

    returncode, stdout, stderr = _run_pytest(args.python, args.test_path)
    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)

    if returncode != 0:
        print(
            "warning_budget_summary gate=cmd-13 status=fail reason=pytest_failed",
            file=sys.stderr,
        )
        return returncode

    warning_count = _parse_warning_count(f"{stdout}\n{stderr}")
    if warning_count > args.max_warnings:
        print(
            "warning_budget_summary "
            f"gate=cmd-13 status=fail warnings={warning_count} "
            f"max_warnings={args.max_warnings}",
            file=sys.stderr,
        )
        return 1

    print(
        "warning_budget_summary "
        f"gate=cmd-13 status=pass warnings={warning_count} "
        f"max_warnings={args.max_warnings}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
