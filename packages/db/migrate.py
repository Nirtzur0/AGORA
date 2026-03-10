"""
Migration runner for AGORA database schema.

Provides a simple interface to apply and manage database migrations.
"""
import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://agora:agora_dev_password@localhost:{os.getenv('AGORA_DB_PORT', '55432')}/agora",
)


def get_alembic_config():
    """Create Alembic configuration."""
    # Get the directory containing this file
    migrations_dir = Path(__file__).parent
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(migrations_dir))
    alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    return alembic_cfg


def migrate_up():
    """Apply all pending migrations."""
    logger.info(f"Running migrations on {DATABASE_URL}")
    
    # First, ensure the alembic_version table exists
    engine = create_engine(DATABASE_URL)
    
    # Check if we need to initialize the migrations directory structure
    migrations_dir = Path(__file__).parent
    versions_dir = migrations_dir / "versions"
    versions_dir.mkdir(exist_ok=True)
    
    with engine.begin() as conn:
        # Check if tables exist
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'agents'
            );
        """))
        tables_exist = result.scalar()
        
        # Setup Alembic context
        from alembic.runtime.migration import MigrationContext
        from alembic.operations import Operations
        import alembic.op
        
        context = MigrationContext.configure(conn)
        op = Operations(context)
        
        # Bind the op object to alembic.op module
        import sys
        alembic.op._proxy = op
        
        import importlib.util

        if not tables_exist:
            logger.info("Applying initial schema migration (001)...")
            
            # Now load and execute the migration
            migration_file = migrations_dir / "migrations" / "001_initial_schema.py"
            spec = importlib.util.spec_from_file_location("migration_001", migration_file)
            migration_001 = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_001)
            
            # Call the upgrade function
            migration_001.upgrade()
            
            logger.info("✓ Initial schema migration applied successfully")
        else:
            logger.info("Schema (001) already exists, skipping")

        # 2. Seed roles (002) - Uses raw connection
        logger.info("Applying roles seed (002)...")
        migration_file_002 = migrations_dir / "migrations" / "002_seed_roles.py"
        spec_002 = importlib.util.spec_from_file_location("migration_002", migration_file_002)
        migration_002 = importlib.util.module_from_spec(spec_002)
        spec_002.loader.exec_module(migration_002)
        
        # Pass raw DBAPI connection
        migration_002.upgrade(conn.connection)
        logger.info("✓ Roles seeded successfully")

        # 3. Search index (003) - Uses Alembic
        result_003 = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'search_index'
            );
        """))
        search_index_exists = result_003.scalar()
        
        if not search_index_exists:
            logger.info("Applying search index migration (003)...")
            migration_file_003 = migrations_dir / "migrations" / "003_search_index.py"
            spec_003 = importlib.util.spec_from_file_location("migration_003", migration_file_003)
            migration_003 = importlib.util.module_from_spec(spec_003)
            spec_003.loader.exec_module(migration_003)
            
            migration_003.upgrade()
            logger.info("✓ Search index migration applied successfully")
        else:
            logger.info("Search index (003) already exists, skipping")
    
    logger.info("✓ Migrations complete")


def migrate_down():
    """Rollback the last migration."""
    logger.info("Rolling back last migration...")
    alembic_cfg = get_alembic_config()
    command.downgrade(alembic_cfg, "-1")
    logger.info("✓ Rollback complete")


def create_migration(message: str):
    """Create a new migration file."""
    logger.info(f"Creating migration: {message}")
    alembic_cfg = get_alembic_config()
    command.revision(alembic_cfg, message=message, autogenerate=False)
    logger.info("✓ Migration file created")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m db.migrate [up|down|create <message>]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "up":
        migrate_up()
    elif cmd == "down":
        migrate_down()
    elif cmd == "create":
        if len(sys.argv) < 3:
            print("Error: create requires a message")
            sys.exit(1)
        create_migration(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
