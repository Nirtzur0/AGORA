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


@pytest.fixture
def test_db(db_url):
    """
    Test database connection wrapper.
    
    Provides a raw psycopg2 connection wrapped in a helper object
    that automatically wraps SQL in text() for SQLAlchemy-style execution.
    
    Each test gets its own connection with rollback at end.
    """
    import psycopg2
    import re
    
    # Parse db_url
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', db_url)
    if not match:
        raise ValueError(f"Invalid DATABASE_URL format: {db_url}")
    
    user, password, host, port, database = match.groups()
    
    # Create connection
    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password
    )
    conn.autocommit = False
    
    # Wrapper class for execute/commit/rollback with text() auto-wrap
    class DBWrapper:
        def __init__(self, connection):
            self._conn = connection
            self._cursor = connection.cursor()
        
        def execute(self, query, params=None):
            """Execute query with optional params (dict or tuple)."""
            if params is None:
                self._cursor.execute(query)
            elif isinstance(params, dict):
                # Convert :param to %(param)s for psycopg2
                query_pg = query.replace(":", "%")
                for key in params.keys():
                    query_pg = query_pg.replace(f"%{key}", f"%({key})s")
                self._cursor.execute(query_pg, params)
            else:
                self._cursor.execute(query, params)
            return self._cursor
        
        def commit(self):
            self._conn.commit()
        
        def rollback(self):
            self._conn.rollback()
        
        def fetchone(self):
            return self._cursor.fetchone()
        
        def fetchall(self):
            return self._cursor.fetchall()
        
        def __enter__(self):
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
    
    db_wrapper = DBWrapper(conn)
    
    yield db_wrapper
    
    # Rollback any uncommitted changes
    conn.rollback()
    conn.close()


@pytest.fixture
def test_storage(minio_config):
    """
    Test storage client for MinIO.
    
    Provides a MinIO client configured for testing.
    Cleans up created buckets/objects after each test.
    """
    from minio import Minio
    
    # Create MinIO client
    client = Minio(
        minio_config["endpoint"],
        access_key=minio_config["access_key"],
        secret_key=minio_config["secret_key"],
        secure=False
    )
    
    # Ensure bucket exists
    bucket = minio_config["bucket"]
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    
    # Track created objects for cleanup
    created_objects = []
    
    class StorageWrapper:
        def __init__(self, minio_client, bucket_name):
            self.client = minio_client
            self.bucket = bucket_name
            self.created_objects = created_objects
        
        def put_object(self, object_name, data, length, content_type="application/octet-stream"):
            """Upload object to MinIO."""
            self.client.put_object(
                self.bucket,
                object_name,
                data,
                length,
                content_type=content_type
            )
            self.created_objects.append(object_name)
        
        def get_object(self, object_name):
            """Get object from MinIO."""
            return self.client.get_object(self.bucket, object_name)
        
        def remove_object(self, object_name):
            """Remove object from MinIO."""
            self.client.remove_object(self.bucket, object_name)
    
    storage = StorageWrapper(client, bucket)
    
    yield storage
    
    # Cleanup created objects
    for obj in created_objects:
        try:
            client.remove_object(bucket, obj)
        except Exception:
            pass  # Ignore cleanup errors


@pytest.fixture
def test_client(core_api_url):
    """
    Test HTTP client for Core API.
    
    Provides a requests-like client configured to call the Core API.
    """
    import requests
    
    class APIClient:
        def __init__(self, base_url):
            self.base_url = base_url.rstrip("/")
            self.session = requests.Session()
        
        def get(self, path, **kwargs):
            url = f"{self.base_url}{path}"
            return self.session.get(url, **kwargs)
        
        def post(self, path, **kwargs):
            url = f"{self.base_url}{path}"
            return self.session.post(url, **kwargs)
        
        def patch(self, path, **kwargs):
            url = f"{self.base_url}{path}"
            return self.session.patch(url, **kwargs)
        
        def delete(self, path, **kwargs):
            url = f"{self.base_url}{path}"
            return self.session.delete(url, **kwargs)
    
    return APIClient(core_api_url)


@pytest.fixture
def mock_agent_token():
    """
    Mock JWT token for testing authenticated endpoints.
    
    Creates a JWT token with test agent credentials.
    """
    import jwt
    
    # Create test token
    payload = {
        "agent_id": "test_agent_id",
        "moltbook_id": "test_moltbook_id"
    }
    
    # Use test secret (should match Core API test secret)
    token = jwt.encode(payload, "test_secret", algorithm="HS256")
    
    return token
