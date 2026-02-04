"""
Compatibility shim for db.migrate imports.
"""
from migrate import migrate_up, migrate_down  # noqa: F401
