# Quick Start Guide

## Prerequisites

- Docker & Docker Compose
- Python 3.10+
- Make (optional, for convenience commands)

## Option 1: Automated Setup (Recommended)

```bash
# Run the setup script (will install everything and run tests)
chmod +x setup.sh
./setup.sh
```

The setup script will:
1. Start infrastructure (Postgres, Temporal, MinIO)
2. Install Python dependencies
3. Run database migrations
4. Create test database and run tests

## Option 2: Manual Setup

### 1. Start Infrastructure

```bash
make up
# Or manually:
cd infra && docker compose up -d
```

### 2. Install Dependencies

```bash
# Database package
make install-db

# Core API
make install-core-api
```

### 3. Run Migrations

```bash
make migrate-up
# Or manually:
cd packages/db && python -m db.migrate up
```

### 4. Run Tests

```bash
make test
```

### 5. Start Core API

```bash
make dev-core-api
# Or manually:
cd apps/core-api && python main.py
```

## Verify Installation

### Check Health Endpoint

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "core-api",
  "version": "1.0.0"
}
```

### Check Database Tables

```bash
docker exec agora-postgres psql -U agora -d agora -c "\dt"
```

You should see all 18 MVP tables listed.

### Check Services

```bash
# View all running services
cd infra && docker compose ps

# View logs
make logs
```

## Service URLs

- **Core API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Temporal UI**: http://localhost:8080
- **MinIO Console**: http://localhost:9001
  - Username: `agora`
  - Password: `agora_dev_password`

## Common Commands

```bash
# Show all available commands
make help

# Start services
make up

# Stop services
make down

# View logs
make logs

# Run all tests
make test

# Run database tests only
make test-db

# Check for stubs/TODOs
make check-stubs

# Clean everything (including data)
make clean
```

## Troubleshooting

### Port Already in Use

If you get port conflict errors:

```bash
# Check what's using the port
lsof -i :5432  # Postgres
lsof -i :8000  # Core API
lsof -i :9000  # MinIO
lsof -i :7233  # Temporal

# Stop conflicting services or change ports in docker-compose.yml
```

### Database Connection Errors

```bash
# Check if Postgres is running and healthy
docker exec agora-postgres pg_isready -U agora

# Check logs
docker logs agora-postgres

# Restart Postgres
cd infra && docker compose restart postgres
```

### Migration Errors

```bash
# Check current database state
docker exec agora-postgres psql -U agora -d agora -c "\dt"

# Drop and recreate database (WARNING: deletes all data)
docker exec agora-postgres psql -U agora -c "DROP DATABASE IF EXISTS agora;"
docker exec agora-postgres psql -U agora -c "CREATE DATABASE agora;"

# Rerun migrations
make migrate-up
```

## Development Workflow

1. **Start infrastructure once**: `make up`
2. **Run migrations when schema changes**: `make migrate-up`
3. **Run tests frequently**: `make test`
4. **Develop and run Core API**: `make dev-core-api`
5. **Check for stubs before committing**: `make check-stubs`

## Next Steps

- See [Component 0 Exit Tests](#component-0-exit-tests) to verify setup
- Continue to Component 2 (MinIO/S3 storage layer)
- Read `Docs/06-implementation-checklist.md` for implementation order

## Component 0 Exit Tests

✅ All exit tests should pass:

```bash
# 1. CI smoke test - check health endpoint
curl -s http://localhost:8000/health | grep "healthy"

# 2. Check infrastructure is running
docker compose -f infra/docker-compose.yml ps | grep "Up"

# 3. Check no stubs in production code
make check-stubs
```

## Component 1 Exit Tests

✅ All exit tests should pass:

```bash
# 1. Migrations apply cleanly
make migrate-up

# 2. All tables exist
docker exec agora-postgres psql -U agora -d agora -c "\dt" | grep agents

# 3. Integration tests pass
make test-db
```
