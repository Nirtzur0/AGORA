"""
Shared runtime configuration helpers.

These helpers centralize the environment-variable contract used across
core-api, worker, scripts, and tests while preserving explicit backwards
compatibility for older variable names during the cleanup window.
"""

from __future__ import annotations

import os


def _getenv(primary: str, *aliases: str, default: str) -> str:
    for key in (primary, *aliases):
        value = os.getenv(key)
        if value not in (None, ""):
            return value
    return default


def get_core_api_port() -> int:
    return int(_getenv("AGORA_CORE_API_PORT", default="18000"))


def get_temporal_address() -> str:
    return _getenv("TEMPORAL_ADDRESS", "TEMPORAL_HOST", default="localhost:7233")


def get_temporal_task_queue() -> str:
    return _getenv("TEMPORAL_TASK_QUEUE", default="agora-tasks")


def get_agent_jwt_secret() -> str:
    return _getenv(
        "AGENT_JWT_SECRET",
        "JWT_SECRET_KEY",
        default="agent-secret-change-in-production",
    )


def get_system_jwt_secret() -> str:
    return _getenv(
        "SYSTEM_JWT_SECRET",
        "SERVICE_JWT_SECRET_KEY",
        default="system-secret-change-in-production",
    )


def get_system_jwt_audience() -> str:
    return _getenv(
        "SYSTEM_JWT_AUDIENCE",
        "SERVICE_JWT_AUDIENCE",
        default="agora:system-api",
    )

