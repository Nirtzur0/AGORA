"""
Database connection and session management.
"""
from sqlalchemy import create_engine, text as sql_text, Column, String, Boolean, TIMESTAMP, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from contextlib import contextmanager
import os
import psycopg2
import uuid
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://agora:agora_dev_password@localhost:5432/agora")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class DBWrapper:
    """
    Wrapper around SQLAlchemy session that auto-wraps SQL in text().
    """
    def __init__(self, session):
        self._session = session
    
    def execute(self, query, params=None):
        """Execute query with automatic text() wrapping. handles %s style via raw cursor."""
        if isinstance(query, str):
            # Check for %s placeholder - implies raw psycopg2 style
            if "%s" in query:
                # Use raw cursor for compatibility with %s style queries
                # access the underlying DBAPI connection
                conn = self._session.connection().connection
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor
            
            # Otherwise use SQLAlchemy text()
            query = sql_text(query)
            
        if params:
            return self._session.execute(query, params)
        return self._session.execute(query)
    
    def commit(self):
        return self._session.commit()
    
    def rollback(self):
        return self._session.rollback()
    
    def close(self):
        return self._session.close()


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
    phase = Column(String, nullable=False, default='setup')
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)


class Agent(Base):
    """Agent model."""
    __tablename__ = 'agents'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    moltbook_identity = Column(String, nullable=False, unique=True)
    display_name = Column(String, nullable=True)
    reputation_score = Column(Integer, nullable=False, default=0)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)


class Artifact(Base):
    """Artifact model."""
    __tablename__ = 'artifacts'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.id'), nullable=False)
    short_id = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey('agents.id'), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)


class ArtifactVersion(Base):
    """Artifact version model."""
    __tablename__ = 'artifact_versions'
    
    id = Column(String, primary_key=True)  # Format: {artifact_id}_v{version}
    artifact_id = Column(UUID(as_uuid=True), ForeignKey('artifacts.id'), nullable=False)
    version = Column(Integer, nullable=False)
    content_hash = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    location = Column(String, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey('agents.id'), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)


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
    artifact_id = Column(UUID(as_uuid=True), ForeignKey('artifacts.id'), nullable=True)
    message = Column(String, nullable=False)
    level = Column(String, nullable=False, default='info')
    actor_type = Column(String, nullable=False)  # 'agent' or 'system'
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)


class Event(Base):
    """Event model."""
    __tablename__ = 'events'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey('workspaces.id'), nullable=False)
    event_type = Column(String, nullable=False)
    actor_type = Column(String, nullable=False)  # Always 'system'
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(String, nullable=True)  # JSONB in actual DB
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
