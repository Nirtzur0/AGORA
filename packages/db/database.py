"""
Database connection and session management.
"""
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import contextmanager
import os
import psycopg2

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
        """Execute query with automatic text() wrapping."""
        if isinstance(query, str):
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
