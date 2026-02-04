"""
Worker database helpers.

Provides a single access layer for worker activities, delegating to
packages/db/database.py.
"""
from packages.db.database import SessionLocal


def get_db_connection():
    """Return a SQLAlchemy session for worker activities."""
    return SessionLocal()
