"""
Integration tests for database migrations and schema.

Tests verify:
- Migrations apply cleanly from empty DB
- All tables exist with correct structure
- Constraints work as expected
- Indexes are created
"""
import pytest
import os
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import IntegrityError
import uuid
from sqlalchemy import text

# Use test database
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://agora:agora_dev_password@localhost:5432/agora_test"
)


@pytest.fixture(scope="module")
def engine():
    """Create test database engine."""
    engine = create_engine(TEST_DATABASE_URL)
    
    # Drop all tables before test
    with engine.begin() as conn:
        # Get all table names
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if tables:
            # Drop all tables
            for table in tables:
                conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
            conn.execute(text('DROP TABLE IF EXISTS alembic_version'))
    
    yield engine
    
    # Cleanup after tests
    with engine.begin() as conn:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        for table in tables:
            conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))


@pytest.fixture(scope="module")
def migrated_db(engine):
    """Apply migrations to test database."""
    # Set DATABASE_URL for migration runner
    original_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    
    try:
        from db.migrate import migrate_up
        migrate_up()
    finally:
        # Restore original DATABASE_URL
        if original_url:
            os.environ["DATABASE_URL"] = original_url
        else:
            os.environ.pop("DATABASE_URL", None)
    
    return engine


class TestMigrations:
    """Test migration application."""
    
    def test_migrations_create_all_tables(self, migrated_db):
        """Verify all required tables are created."""
        inspector = inspect(migrated_db)
        tables = set(inspector.get_table_names())
        
        expected_tables = {
            'agents',
            'roles',
            'workspaces',
            'workspace_agents',
            'join_requests',
            'artifacts',
            'artifact_versions',
            'logs',
            'events',
            'claims',
            'claim_evidence',
            'citations',
            'workflow_runs',
            'activity_runs',
            'agent_tasks',
            'critiques',
            'rule_checks',
            'idempotency_keys',
        }
        
        assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"
    
    def test_agents_table_structure(self, migrated_db):
        """Verify agents table has correct columns."""
        inspector = inspect(migrated_db)
        columns = {col['name']: col for col in inspector.get_columns('agents')}
        
        assert 'id' in columns
        assert 'moltbook_id' in columns
        assert 'name' in columns
        assert 'reputation' in columns
        assert 'created_at' in columns
        
        # Check moltbook_id is unique
        indexes = inspector.get_indexes('agents')
        unique_cols = [idx['column_names'] for idx in inspector.get_unique_constraints('agents')]
        assert ['moltbook_id'] in unique_cols or any('moltbook_id' in idx['column_names'] for idx in indexes if idx.get('unique'))
    
    def test_workspaces_table_structure(self, migrated_db):
        """Verify workspaces table has correct columns."""
        inspector = inspect(migrated_db)
        columns = {col['name']: col for col in inspector.get_columns('workspaces')}
        
        assert 'id' in columns
        assert 'name' in columns
        assert 'description' in columns
        assert 'tags' in columns
        assert 'phase' in columns
        assert 'created_by' in columns
        assert 'created_at' in columns
    
    def test_artifacts_table_structure(self, migrated_db):
        """Verify artifacts table has correct columns and constraints."""
        inspector = inspect(migrated_db)
        columns = {col['name']: col for col in inspector.get_columns('artifacts')}
        
        assert 'id' in columns
        assert 'workspace_id' in columns
        assert 'short_id' in columns
        assert 'type' in columns
        assert 'metadata' in columns
        assert 'storage_uri' in columns
        assert 'created_by' in columns
        assert 'created_at' in columns
        
        # Check unique constraint on (workspace_id, short_id)
        unique_constraints = inspector.get_unique_constraints('artifacts')
        constraint_cols = [set(uc['column_names']) for uc in unique_constraints]
        assert {'workspace_id', 'short_id'} in constraint_cols
    
    def test_artifact_versions_table_structure(self, migrated_db):
        """Verify artifact_versions table has correct columns and constraints."""
        inspector = inspect(migrated_db)
        columns = {col['name']: col for col in inspector.get_columns('artifact_versions')}
        
        assert 'id' in columns
        assert 'artifact_id' in columns
        assert 'version' in columns
        assert 'storage_uri' in columns
        assert 'content_hash' in columns
        assert 'created_by' in columns
        assert 'created_at' in columns
        
        # Check unique constraint on (artifact_id, version)
        unique_constraints = inspector.get_unique_constraints('artifact_versions')
        constraint_cols = [set(uc['column_names']) for uc in unique_constraints]
        assert {'artifact_id', 'version'} in constraint_cols


class TestSchemaConstraints:
    """Test database constraints work correctly."""
    
    def test_basic_insert_and_select(self, migrated_db):
        """Test basic insert and select for each table."""
        with migrated_db.begin() as conn:
            # Insert agent
            agent_id = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO agents (id, moltbook_id, name, reputation)
                VALUES (:id, :moltbook_id, :name, :reputation)
            """), {
                "id": agent_id,
                "moltbook_id": "test_moltbook_123",
                "name": "Test Agent",
                "reputation": 100.0
            })
            
            # Select agent
            result = conn.execute(text("SELECT * FROM agents WHERE id = :id"), {"id": agent_id})
            agent = result.fetchone()
            assert agent is not None
            assert agent.name == "Test Agent"
            assert float(agent.reputation) == 100.0
    
    def test_unique_moltbook_id_constraint(self, migrated_db):
        """Test that duplicate moltbook_id is rejected."""
        with migrated_db.begin() as conn:
            moltbook_id = f"unique_test_{uuid.uuid4()}"
            
            # First insert should succeed
            conn.execute(text("""
                INSERT INTO agents (moltbook_id, name)
                VALUES (:moltbook_id, :name)
            """), {"moltbook_id": moltbook_id, "name": "Agent 1"})
            
        # Second insert with same moltbook_id should fail
        with pytest.raises(IntegrityError):
            with migrated_db.begin() as conn:
                conn.execute(text("""
                    INSERT INTO agents (moltbook_id, name)
                    VALUES (:moltbook_id, :name)
                """), {"moltbook_id": moltbook_id, "name": "Agent 2"})
    
    def test_workspace_short_id_unique_per_workspace(self, migrated_db):
        """Test that (workspace_id, short_id) uniqueness is enforced."""
        with migrated_db.begin() as conn:
            # Create agent and workspace
            agent_id = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO agents (id, moltbook_id) VALUES (:id, :moltbook_id)
            """), {"id": agent_id, "moltbook_id": f"agent_{uuid.uuid4()}"})
            
            workspace_id = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO workspaces (id, name, phase, created_by)
                VALUES (:id, :name, :phase, :created_by)
            """), {"id": workspace_id, "name": "Test WS", "phase": "INIT", "created_by": agent_id})
            
            # First artifact with short_id A1
            conn.execute(text("""
                INSERT INTO artifacts (workspace_id, short_id, type, storage_uri)
                VALUES (:workspace_id, :short_id, :type, :storage_uri)
            """), {
                "workspace_id": workspace_id,
                "short_id": "A1",
                "type": "pdf",
                "storage_uri": "s3://bucket/path1"
            })
            
        # Second artifact with same short_id in same workspace should fail
        with pytest.raises(IntegrityError):
            with migrated_db.begin() as conn:
                conn.execute(text("""
                    INSERT INTO artifacts (workspace_id, short_id, type, storage_uri)
                    VALUES (:workspace_id, :short_id, :type, :storage_uri)
                """), {
                    "workspace_id": workspace_id,
                    "short_id": "A1",
                    "type": "code",
                    "storage_uri": "s3://bucket/path2"
                })
    
    def test_artifact_version_uniqueness(self, migrated_db):
        """Test that (artifact_id, version) uniqueness is enforced."""
        with migrated_db.begin() as conn:
            # Create prerequisite records
            agent_id = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO agents (id, moltbook_id) VALUES (:id, :moltbook_id)
            """), {"id": agent_id, "moltbook_id": f"agent_{uuid.uuid4()}"})
            
            workspace_id = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO workspaces (id, name, phase, created_by)
                VALUES (:id, :name, :phase, :created_by)
            """), {"id": workspace_id, "name": "Test", "phase": "INIT", "created_by": agent_id})
            
            artifact_id = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO artifacts (id, workspace_id, short_id, type, storage_uri)
                VALUES (:id, :workspace_id, :short_id, :type, :storage_uri)
            """), {
                "id": artifact_id,
                "workspace_id": workspace_id,
                "short_id": "A1",
                "type": "pdf",
                "storage_uri": "s3://bucket/base"
            })
            
            # First version
            conn.execute(text("""
                INSERT INTO artifact_versions (artifact_id, version, storage_uri)
                VALUES (:artifact_id, :version, :storage_uri)
            """), {"artifact_id": artifact_id, "version": 1, "storage_uri": "s3://bucket/v1"})
        
        # Duplicate version should fail
        with pytest.raises(IntegrityError):
            with migrated_db.begin() as conn:
                conn.execute(text("""
                    INSERT INTO artifact_versions (artifact_id, version, storage_uri)
                    VALUES (:artifact_id, :version, :storage_uri)
                """), {"artifact_id": artifact_id, "version": 1, "storage_uri": "s3://bucket/v1_dup"})
    
    def test_foreign_key_constraints(self, migrated_db):
        """Test that foreign key constraints are enforced."""
        # Try to insert workspace with non-existent created_by agent
        with pytest.raises(IntegrityError):
            with migrated_db.begin() as conn:
                fake_agent_id = str(uuid.uuid4())
                conn.execute(text("""
                    INSERT INTO workspaces (name, phase, created_by)
                    VALUES (:name, :phase, :created_by)
                """), {"name": "Test", "phase": "INIT", "created_by": fake_agent_id})
    
    def test_idempotency_keys_unique_constraint(self, migrated_db):
        """Test idempotency_keys unique constraint on (workspace_id, agent_id, request_name, idempotency_key)."""
        with migrated_db.begin() as conn:
            # Create prerequisites
            agent_id = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO agents (id, moltbook_id) VALUES (:id, :moltbook_id)
            """), {"id": agent_id, "moltbook_id": f"agent_{uuid.uuid4()}"})
            
            workspace_id = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO workspaces (id, name, phase, created_by)
                VALUES (:id, :name, :phase, :created_by)
            """), {"id": workspace_id, "name": "Test", "phase": "INIT", "created_by": agent_id})
            
            result_id = str(uuid.uuid4())
            
            # First insert
            conn.execute(text("""
                INSERT INTO idempotency_keys 
                (workspace_id, agent_id, request_name, idempotency_key, result_type, result_id, expires_at)
                VALUES (:workspace_id, :agent_id, :request_name, :idempotency_key, :result_type, :result_id, NOW() + INTERVAL '1 day')
            """), {
                "workspace_id": workspace_id,
                "agent_id": agent_id,
                "request_name": "claim.create",
                "idempotency_key": "key123",
                "result_type": "claim",
                "result_id": result_id
            })
        
        # Duplicate should fail
        with pytest.raises(IntegrityError):
            with migrated_db.begin() as conn:
                conn.execute(text("""
                    INSERT INTO idempotency_keys 
                    (workspace_id, agent_id, request_name, idempotency_key, result_type, result_id, expires_at)
                    VALUES (:workspace_id, :agent_id, :request_name, :idempotency_key, :result_type, :result_id, NOW() + INTERVAL '1 day')
                """), {
                    "workspace_id": workspace_id,
                    "agent_id": agent_id,
                    "request_name": "claim.create",
                    "idempotency_key": "key123",
                    "result_type": "claim",
                    "result_id": str(uuid.uuid4())
                })


class TestIndexes:
    """Test that recommended indexes are created."""
    
    def test_key_indexes_exist(self, migrated_db):
        """Verify critical indexes are created."""
        inspector = inspect(migrated_db)
        
        # Check agents indexes
        agent_indexes = {idx['name']: idx for idx in inspector.get_indexes('agents')}
        assert any('moltbook_id' in idx['column_names'] for idx in agent_indexes.values())
        
        # Check workspaces indexes
        ws_indexes = {idx['name']: idx for idx in inspector.get_indexes('workspaces')}
        assert any('phase' in idx['column_names'] for idx in ws_indexes.values())
        
        # Check artifacts indexes
        artifact_indexes = {idx['name']: idx for idx in inspector.get_indexes('artifacts')}
        index_cols = [tuple(idx['column_names']) for idx in artifact_indexes.values()]
        assert any('workspace_id' in cols and 'short_id' in cols for cols in index_cols)
