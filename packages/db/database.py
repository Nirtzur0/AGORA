"""
Database connection and session management.
"""
from sqlalchemy import create_engine, text as sql_text, Column, String, Boolean, TIMESTAMP, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, synonym
from contextlib import contextmanager
import os
import psycopg2
from psycopg2.extras import Json as PgJson
import uuid
from datetime import datetime
import json

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://agora:agora_dev_password@localhost:{os.getenv('AGORA_DB_PORT', '55432')}/agora",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class DBWrapper:
    """
    Wrapper around SQLAlchemy session that auto-wraps SQL in text().
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
        """Execute query with automatic text() wrapping. handles %s style via raw cursor."""
        if isinstance(query, str):
            # Check for %s placeholder - implies raw psycopg2 style
            if "%s" in query:
                # Use raw cursor for compatibility with %s style queries
                # access the underlying DBAPI connection
                conn = self._session.connection().connection
                cursor = conn.cursor()
                cursor.execute(query, self._coerce_params(params))
                return cursor
            
            # Otherwise use SQLAlchemy text()
            query = sql_text(query)
            
        if params:
            return self._session.execute(query, self._coerce_params(params))
        return self._session.execute(query)
    
    def commit(self):
        return self._session.commit()
    
    def rollback(self):
        return self._session.rollback()
    
    def close(self):
        return self._session.close()

    def __getattr__(self, name):
        return getattr(self._session, name)


@contextmanager
def get_db():
    """Context manager for database sessions (SQLAlchemy ORM with auto text() wrapper)."""
    session = SessionLocal()
    db = DBWrapper(session)
    try:
        yield db
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_session():
    """
    Generator for FastAPI Depends().
    
    Delegates to get_db() context manager but yields the session
    so FastAPI can handle the dependency injection correctly.
    """
    with get_db() as db:
        yield db


@contextmanager
def get_raw_db():
    """
    Context manager for raw psycopg2 connection.
    
    Use this for direct SQL execution without SQLAlchemy text() wrapper.
    """
    # Parse DATABASE_URL
    import re
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', DATABASE_URL)
    if not match:
        raise ValueError(f"Invalid DATABASE_URL format: {DATABASE_URL}")
    
    user, password, host, port, database = match.groups()
    
    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password
    )
    
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# SQLAlchemy ORM Models

class Workspace(Base):
    """Workspace model."""
    __tablename__ = 'workspaces'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    tags = Column(ARRAY(String), nullable=False, default=list)
    phase = Column(String, nullable=False, default='INIT')
    created_by = Column(UUID(as_uuid=True), ForeignKey('agents.id'), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)


class Agent(Base):
    """Agent model."""
    __tablename__ = 'agents'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    moltbook_id = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=True)
    reputation = Column(Numeric, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Backwards-compatible aliases for legacy test code
    moltbook_identity = synonym("moltbook_id")
    display_name = synonym("name")
    reputation_score = synonym("reputation")


class Artifact(Base):
    """Artifact model."""
    __tablename__ = 'artifacts'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.id'), nullable=False)
    short_id = Column(String, nullable=False)
    type = Column(String, nullable=False)
    metadata_json = Column("metadata", JSONB, key="metadata_json", nullable=True)
    storage_uri = Column(String, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey('agents.id'), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Backwards-compatible alias
    content_type = synonym("type")

    def __init__(self, **kwargs):
        if "metadata" in kwargs and "metadata_json" not in kwargs:
            kwargs["metadata_json"] = kwargs.pop("metadata")
        if "storage_uri" not in kwargs and "workspace_id" in kwargs and "id" in kwargs:
            kwargs["storage_uri"] = f"s3://agora/{kwargs['workspace_id']}/artifacts/{kwargs['id']}/"
        super().__init__(**kwargs)


class ArtifactVersion(Base):
    """Artifact version model."""
    __tablename__ = 'artifact_versions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id = Column(UUID(as_uuid=True), ForeignKey('artifacts.id'), nullable=False)
    version = Column(Integer, nullable=False)
    storage_uri = Column(String, nullable=False)
    content_hash = Column(String, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey('agents.id'), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Backwards-compatible aliases
    version_number = synonym("version")
    location = synonym("storage_uri")

    _size_bytes = None

    def __init__(self, **kwargs):
        size_bytes = kwargs.pop("size_bytes", None)
        super().__init__(**kwargs)
        if size_bytes is not None:
            self._size_bytes = size_bytes

    @property
    def size_bytes(self):
        return self._size_bytes


class Claim(Base):
    """Claim model."""
    __tablename__ = 'claims'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.id'), nullable=False)
    kind = Column(String, nullable=False)
    text = Column(String, nullable=False)
    confidence = Column(String, nullable=True)
    is_key = Column(Boolean, nullable=False, default=False)
    status = Column(String, nullable=False, default='active')
    created_by = Column(UUID(as_uuid=True), ForeignKey('agents.id'), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Relationships
    evidence = relationship('ClaimEvidence', back_populates='claim')

    # Backwards-compatible aliases
    agent_id = synonym("created_by")
    statement = synonym("text")
    content = synonym("text")


class ClaimEvidence(Base):
    """Claim evidence model."""
    __tablename__ = 'claim_evidence'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(UUID(as_uuid=True), ForeignKey('claims.id'), nullable=False)
    artifact_version_id = Column(String, ForeignKey('artifact_versions.id'), nullable=False)
    location = Column(String, nullable=False)
    
    # Relationships
    claim = relationship('Claim', back_populates='evidence')
    artifact_version = relationship('ArtifactVersion')


class Log(Base):
    """Log model."""
    __tablename__ = 'logs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.id'), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey('agents.id'), nullable=True)
    action = Column(String, nullable=False)
    payload = Column(JSONB, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Backwards-compatible alias
    message = synonym("action")


class Event(Base):
    """Event model."""
    __tablename__ = 'events'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.id'), nullable=False)
    event_type = Column(String, nullable=False)
    actor_type = Column(String, nullable=False)
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    payload = Column(JSONB, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Backwards-compatible alias
    details = synonym("payload")
