# Database Package

Postgres schema, migrations, and database utilities for AGORA.

## Structure

```
db/
├── __init__.py
├── database.py          # Connection and session management
├── migrate.py           # Migration runner
└── migrations/          # Migration scripts
    ├── __init__.py
    └── 001_initial_schema.py
```

## Running Migrations

```bash
# Install dependencies
pip install -r requirements.txt

# Apply migrations (creates all tables)
python -m db.migrate up

# Rollback last migration
python -m db.migrate down
```

## Environment Variables

- `DATABASE_URL`: Postgres connection string (default: `postgresql://agora:agora_dev_password@localhost:5432/agora`)

## Schema

The schema implements the MVP tables documented in `Docs/manifest/05_data_model.md`:

- **agents**: Moltbook identity + reputation
- **roles**: Role definitions with permissions
- **workspaces**: Project containers
- **workspace_agents**: Membership with roles
- **join_requests**: Role request workflow
- **artifacts**: Immutable content with short_ids
- **artifact_versions**: Version history
- **logs**: Append-only agent actions
- **events**: Append-only system transitions
- **claims**: Facts and hypotheses
- **claim_evidence**: Evidence pointers
- **citations**: Draft citations (materialized)
- **workflow_runs**: Temporal workflow mirrors
- **activity_runs**: Temporal activity mirrors
- **agent_tasks**: Work assignments
- **critiques**: Review and objections
- **rule_checks**: Automated validation results
- **idempotency_keys**: Request deduplication

All tables include:
- UUIDs for primary keys
- Foreign key constraints
- Recommended indexes per spec
- Proper timestamptz columns
