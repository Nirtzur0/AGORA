"""
Centralized pytest configuration for AGORA.

All tests run via pytest from the repository root.
"""

import os
import subprocess
import sys
import time
import types
from pathlib import Path

import pytest

# When we disable third-party plugin autoloading (for determinism), we still
# want first-party async tests to execute.
pytest_plugins = ("pytest_asyncio.plugin",)

# Test database URL (must be set before importing database module)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    f"postgresql://agora:agora_dev_password@localhost:{os.getenv('AGORA_DB_PORT', '55432')}/agora_test",
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

# Ensure local `tests.*` imports win even when another installed project also
# exposes a top-level `tests` namespace.
tests_pkg = types.ModuleType("tests")
tests_pkg.__path__ = [str(repo_root / "tests")]
sys.modules["tests"] = tests_pkg

# Lock "database" module to packages/db/database.py to avoid sys.path shadowing.
import importlib
sys.modules["database"] = importlib.import_module("database")

# Automatically tag tests by location so selection is consistent even if a file
# forgets to add `@pytest.mark.<...>` decorators.
def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    for item in items:
        p = Path(str(getattr(item, "fspath", "")))
        try:
            rel = p.relative_to(repo_root)
        except Exception:
            rel = p

        parts = rel.parts
        if not parts or parts[0] != "tests":
            continue
        if "unit" in parts:
            item.add_marker(pytest.mark.unit)
        elif "integration" in parts:
            item.add_marker(pytest.mark.integration)
        elif "e2e" in parts:
            item.add_marker(pytest.mark.e2e)

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
CORE_API_URL = os.getenv("CORE_API_URL")  # optional override; defaults to in-process TestClient
_TEMPORAL_WORKER_PROCESS = None


@pytest.fixture(scope="session")
def migrated_db():
    """
    Ensure the TEST_DATABASE_URL exists and is migrated before any tests run.

    This is intentionally NOT autouse: unit tests must be runnable without
    requiring a running Postgres container.
    """
    # Create database if missing (connect to postgres maintenance DB).
    import re
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    m = re.match(r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.*)", TEST_DATABASE_URL)
    if not m:
        raise RuntimeError(f"Invalid TEST_DATABASE_URL: {TEST_DATABASE_URL}")
    user, password, host, port, dbname = m.groups()

    conn = psycopg2.connect(host=host, port=int(port), database="postgres", user=user, password=password)
    try:
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        exists = cur.fetchone() is not None
        if not exists:
            cur.execute(f"CREATE DATABASE {dbname}")
    finally:
        conn.close()

    # Run migrations against the test database.
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    try:
        # The migration runner binds DATABASE_URL at import time; force it to the
        # test DB even if another test/module imported it earlier.
        import importlib
        migrate = importlib.import_module("migrate")
        migrate.DATABASE_URL = TEST_DATABASE_URL
        migrate.migrate_up()
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original


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
    """Core API URL for integration tests (session-scoped)."""
    # If caller provided an explicit CORE_API_URL, respect it. Otherwise, tests
    # should use the in-process `test_client` fixture (preferred).
    return CORE_API_URL or "http://testserver"


@pytest.fixture(scope="session", autouse=True)
def _shutdown_core_api_server():
    """
    Back-compat fixture: older versions spawned uvicorn and needed cleanup.
    Core API is now exercised via in-process TestClient for determinism.
    """
    yield


def _start_test_worker() -> None:
    global _TEMPORAL_WORKER_PROCESS
    if _TEMPORAL_WORKER_PROCESS and _TEMPORAL_WORKER_PROCESS.poll() is None:
        return

    env = os.environ.copy()
    env.setdefault("TEMPORAL_TASK_QUEUE", "agora-tasks")
    env.setdefault("TEMPORAL_ADDRESS", "localhost:7233")
    pythonpath_entries = [
        str(repo_root / "packages" / "db"),
        str(repo_root / "packages" / "shared-types"),
        str(repo_root / "apps" / "core-api"),
        str(repo_root / "apps" / "worker"),
        str(repo_root),
    ]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_entries.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)

    _TEMPORAL_WORKER_PROCESS = subprocess.Popen(
        [sys.executable, str(repo_root / "apps" / "worker" / "main.py")],
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    deadline = time.time() + 10
    while time.time() < deadline:
        if _TEMPORAL_WORKER_PROCESS.poll() is not None:
            output = ""
            if _TEMPORAL_WORKER_PROCESS.stdout is not None:
                output = _TEMPORAL_WORKER_PROCESS.stdout.read()
            raise RuntimeError(f"Test worker exited unexpectedly:\n{output}")
        time.sleep(0.5)


@pytest.fixture(autouse=True)
def ensure_temporal_worker_for_runtime_tests(request):
    if "integration" not in request.keywords and "e2e" not in request.keywords:
        yield
        return

    _start_test_worker()
    yield


@pytest.fixture(scope="session", autouse=True)
def _shutdown_temporal_worker():
    yield
    global _TEMPORAL_WORKER_PROCESS
    if _TEMPORAL_WORKER_PROCESS and _TEMPORAL_WORKER_PROCESS.poll() is None:
        _TEMPORAL_WORKER_PROCESS.terminate()
        try:
            _TEMPORAL_WORKER_PROCESS.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _TEMPORAL_WORKER_PROCESS.kill()
            _TEMPORAL_WORKER_PROCESS.wait(timeout=10)
    _TEMPORAL_WORKER_PROCESS = None


@pytest.fixture(scope="session")
def core_api_app():
    """
    In-process FastAPI app instance.

    This avoids subprocess + readiness polling, while still exercising:
    routing, auth middleware, request parsing, and persistence.
    """
    # If users explicitly want to target a running server (CORE_API_URL), they
    # can bypass this fixture and use requests directly.
    from main import app

    return app


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
            from psycopg2.extras import Json as PgJson
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
            from sqlalchemy import text as sql_text
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
def db_session(db_url, migrated_db):
    """
    SQLAlchemy session bound to the test database.

    Tests that exercise the worker/orchestrator path need committed rows to be
    visible across real DB connections, so teardown uses explicit table cleanup
    instead of an outer rollback transaction.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    session = Session()
    wrapped = SessionWrapper(session)
    try:
        yield wrapped
    finally:
        session.rollback()
        session.close()

        cleanup_connection = engine.connect()
        cleanup_transaction = cleanup_connection.begin()
        cleanup_connection.execute(
            text(
                """
                DO $$
                DECLARE
                    table_name text;
                BEGIN
                    FOR table_name IN
                        SELECT tablename
                        FROM pg_tables
                        WHERE schemaname = 'public'
                          AND tablename NOT IN ('roles')
                    LOOP
                        EXECUTE 'TRUNCATE TABLE ' || quote_ident(table_name) || ' RESTART IDENTITY CASCADE';
                    END LOOP;
                END $$;
                """
            )
        )
        cleanup_transaction.commit()
        cleanup_connection.close()
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
def test_client(core_api_url, core_api_app, migrated_db):
    """
    Test HTTP client for Core API.
    
    Preferred: an in-process client (deterministic, no port conflicts).
    If CORE_API_URL is set, falls back to making real HTTP calls to that server.
    """
    import requests
    from fastapi.testclient import TestClient

    if CORE_API_URL:
        class RequestsAPIClient:
            def __init__(self, base_url: str):
                self.base_url = base_url.rstrip("/")
                self.session = requests.Session()

            def get(self, path, **kwargs):
                return self.session.get(f"{self.base_url}{path}", **kwargs)

            def post(self, path, **kwargs):
                return self.session.post(f"{self.base_url}{path}", **kwargs)

            def patch(self, path, **kwargs):
                return self.session.patch(f"{self.base_url}{path}", **kwargs)

            def delete(self, path, **kwargs):
                return self.session.delete(f"{self.base_url}{path}", **kwargs)

        return RequestsAPIClient(CORE_API_URL)

    client = TestClient(core_api_app)

    class InProcessAPIClient:
        def get(self, path, **kwargs):
            return client.get(path, **kwargs)

        def post(self, path, **kwargs):
            return client.post(path, **kwargs)

        def patch(self, path, **kwargs):
            return client.patch(path, **kwargs)

        def delete(self, path, **kwargs):
            return client.delete(path, **kwargs)

    return InProcessAPIClient()


@pytest.fixture
def mock_agent_token(migrated_db):
    """
    Mock JWT token for testing authenticated endpoints.
    
    Creates a JWT token with test agent credentials.
    """
    from jwt_utils import create_agent_token
    from database import get_db

    # Ensure test agent exists for FK constraints
    with get_db() as db:
        db.execute(
            """
            INSERT INTO agents (id, moltbook_id, name)
            VALUES (:id, :moltbook_id, :name)
            ON CONFLICT (id) DO NOTHING
            """,
            {"id": TEST_AGENT_ID, "moltbook_id": TEST_MOLTBOOK_ID, "name": "Test Agent"},
        )
        db.commit()

    return create_agent_token(
        agent_id=TEST_AGENT_ID,
        moltbook_id=TEST_MOLTBOOK_ID,
        reputation=0
    )
