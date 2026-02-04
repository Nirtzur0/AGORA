#!/usr/bin/env python3
"""
Run the roles seed migration.
"""

import os
import sys
from pathlib import Path

# Add packages to path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "packages" / "db"))

from database import get_db

# Import migration module
migrations_dir = repo_root / "packages" / "db" / "migrations"
sys.path.insert(0, str(migrations_dir))

import importlib.util
spec = importlib.util.spec_from_file_location("seed_roles", migrations_dir / "002_seed_roles.py")
seed_roles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed_roles)


def main():
    print("Seeding roles with canonical permissions...")
    
    import psycopg
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://agora:agora_dev_password@localhost:5432/agora")
    
    with psycopg.connect(DATABASE_URL) as conn:
        # Run upgrade
        seed_roles.upgrade(conn)
        conn.commit()
    
    print("✓ Roles seeded successfully")


if __name__ == "__main__":
    main()
