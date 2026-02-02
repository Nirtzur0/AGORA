"""
Centralized pytest configuration for AGORA.

All tests run via pytest from the repository root.
"""

import os
import sys
import pytest
from pathlib import Path

# Add packages to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "packages" / "db"))
sys.path.insert(0, str(repo_root / "packages" / "shared-types"))
sys.path.insert(0, str(repo_root / "apps" / "core-api"))

# Test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://agora:agora_dev_password@localhost:5432/agora_test"
)

# MinIO configuration for storage tests
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "agora")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "agora_dev_password")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "agora")

# Moltbook adapter configuration
MOLTBOOK_ADAPTER_URL = os.getenv("MOLTBOOK_ADAPTER_URL", "http://localhost:3001")

# Core API configuration
CORE_API_URL = os.getenv("CORE_API_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def db_url():
    """Test database URL."""
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def minio_config():
    """MinIO configuration for storage tests."""
    return {
        "endpoint": MINIO_ENDPOINT,
        "access_key": MINIO_ACCESS_KEY,
        "secret_key": MINIO_SECRET_KEY,
        "bucket": MINIO_BUCKET,
    }


@pytest.fixture(scope="session")
def moltbook_adapter_url():
    """Moltbook adapter URL for integration tests."""
    return MOLTBOOK_ADAPTER_URL


@pytest.fixture(scope="session")
def core_api_url():
    """Core API URL for integration tests."""
    return CORE_API_URL
