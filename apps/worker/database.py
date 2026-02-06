"""
Worker database helpers.

Provides a single access layer for worker activities, delegating to
packages/db/database.py.
"""
from database import SessionLocal, DBWrapper


def get_db_connection():
    """
    Return a DB wrapper for worker activities.

    Worker activities frequently bind JSON-ish params into SQL. Using the same
    DBWrapper as core-api keeps coercion rules consistent (dict/list -> JSONB).
    """
    session = SessionLocal()
    return DBWrapper(session)
