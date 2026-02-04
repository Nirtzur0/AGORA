"""
Centralized pytest configuration for AGORA.

All tests run via pytest from the repository root.
"""

import os
import sys
import pytest
from pathlib import Path
from sqlalchemy import text as sql_text
from psycopg2.extras import Json as PgJson

# Test database URL (must be set before importing database module)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://agora:agora_dev_password@localhost:5432/agora_test"
)
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)

# Add packages to path (ordered to avoid name shadowing)
repo_root = Path(__file__).parent.parent
path_order = [
    repo_root / "packages" / "db",
    repo_root / "packages" / "shared-types",
    repo_root / "apps" / "core-api",
    repo_root / "apps" / "worker",
    repo_root,
]
for path in reversed(path_order):
    sys.path.insert(0, str(path))

# Lock "database" module to packages/db/database.py to avoid sys.path shadowing.
import importlib
sys.modules["database"] = importlib.import_module("database")

# Shared test agent identity
TEST_AGENT_ID = os.getenv("TEST_AGENT_ID", "00000000-0000-0000-0000-000000000001")
TEST_MOLTBOOK_ID = os.getenv("TEST_MOLTBOOK_ID", "test_moltbook_id")

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


class SessionWrapper:
    """
    SQLAlchemy session wrapper with text() auto-wrap for raw SQL.

    Provides a consistent API for tests using either ORM or raw SQL.
    """
    def __init__(self, session):
        self._session = session

    def _coerce_params(self, params):
        if isinstance(params, dict):
            return {k: self._coerce_value(v) for k, v in params.items()}
        if isinstance(params, (list, tuple)):
            return [self._coerce_value(v) for v in params]
        return params

    def _coerce_value(self, value):
        if isinstance(value, (dict, list)):
            return PgJson(value)
        return value

    def execute(self, query, params=None):
        if isinstance(query, str):
            if "%s" in query:
                conn = self._session.connection().connection
                cursor = conn.cursor()
                # Escape literal % to avoid psycopg2 param parsing issues (e.g., LIKE 'D%').
                import re
                safe_query = re.sub(r'%(?!s)', '%%', query)
                cursor.execute(safe_query, self._coerce_params(params))
                return cursor
            query = sql_text(query)
        if params:
            return self._session.execute(query, self._coerce_params(params))
        return self._session.execute(query)

    def commit(self):
        return self._session.commit()

    def rollback(self):
        return self._session.rollback()

    def __getattr__(self, name):
        return getattr(self._session, name)


@pytest.fixture
def db_session(db_url):
    """
    SQLAlchemy session bound to the test database.

    Uses a nested transaction so tests can commit while the outer
    transaction is rolled back at teardown.
    """
    from sqlalchemy import create_engine, event, inspect
    from sqlalchemy.orm import sessionmaker

    def ensure_migrated(url: str) -> None:
        engine = create_engine(url, pool_pre_ping=True)
        try:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            if "workspaces" not in tables:
                original_url = os.environ.get("DATABASE_URL")
                os.environ["DATABASE_URL"] = url
                try:
                    from db.migrate import migrate_up
                    migrate_up()
                finally:
                    if original_url is not None:
                        os.environ["DATABASE_URL"] = original_url
                    else:
                        os.environ.pop("DATABASE_URL", None)
        finally:
            engine.dispose()

    ensure_migrated(db_url)

    engine = create_engine(db_url, pool_pre_ping=True)
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = Session()
    
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    wrapped = SessionWrapper(session)
    try:
        yield wrapped
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture
def test_db(db_session):
    """Alias for db_session to standardize test DB access."""
    return db_session


@pytest.fixture
def test_storage():
    """
    Test storage wrapper using the shared Storage class.
    
    Tracks created objects and deletes them after each test.
    """
    from storage import create_storage_from_env, InvalidStorageURIError
    
    storage = create_storage_from_env()
    created_uris = []
    
    class StorageWrapper:
        def __init__(self, storage_client):
            self._storage = storage_client
        
        def put_object(self, storage_uri, data):
            self._storage.put_object(storage_uri, data)
            created_uris.append(storage_uri)
        
        def get_object(self, storage_uri):
            return self._storage.get_object(storage_uri)
        
        def exists(self, storage_uri):
            return self._storage.exists(storage_uri)
        
        def _delete_object(self, storage_uri):
            key = self._storage._validate_storage_uri(storage_uri)
            self._storage.s3.delete_object(Bucket=self._storage.bucket, Key=key)
    
    wrapper = StorageWrapper(storage)
    yield wrapper
    
    # Cleanup created objects
    for uri in created_uris:
        try:
            wrapper._delete_object(uri)
        except InvalidStorageURIError:
            pass
        except Exception:
            pass


@pytest.fixture
def storage(test_storage):
    """Alias for test_storage to standardize storage usage."""
    return test_storage


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
def mock_agent_token(test_db):
    """
    Mock JWT token for testing authenticated endpoints.
    
    Creates a JWT token with test agent credentials.
    """
    from jwt_utils import create_agent_token

    # Ensure test agent exists for FK constraints
    test_db.execute(
        """
        INSERT INTO agents (id, moltbook_id, name)
        VALUES (:id, :moltbook_id, :name)
        ON CONFLICT (id) DO NOTHING
        """,
        {"id": TEST_AGENT_ID, "moltbook_id": TEST_MOLTBOOK_ID, "name": "Test Agent"}
    )
    test_db.commit()

    return create_agent_token(
        agent_id=TEST_AGENT_ID,
        moltbook_id=TEST_MOLTBOOK_ID,
        reputation=0
    )
