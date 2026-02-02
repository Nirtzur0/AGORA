# Infrastructure Configuration

## Local Development Stack

The `docker-compose.yml` brings up all required services:

- **Postgres** (port 5432): Application database
- **Temporal Postgres** (port 5433): Temporal persistence
- **MinIO** (ports 9000, 9001): S3-compatible object storage
- **Temporal Server** (port 7233): Workflow orchestration
- **Temporal UI** (port 8080): Workflow observability

## Environment Variables

Required for application services (Core API, Worker, Moltbook Adapter):

### Core API
```bash
# Database
DATABASE_URL=postgresql://agora:agora_dev_password@localhost:5432/agora

# Object Storage (MinIO)
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=agora
S3_SECRET_KEY=agora_dev_password
S3_BUCKET=agora

# Temporal
TEMPORAL_ADDRESS=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=agora-tasks

# Moltbook Adapter
MOLTBOOK_ADAPTER_URL=http://localhost:3001

# JWT
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# Service JWT (system-only auth)
SERVICE_JWT_SECRET_KEY=your-service-secret-change-in-production
SERVICE_JWT_AUDIENCE=agora-internal
```

### Worker
```bash
# Database
DATABASE_URL=postgresql://agora:agora_dev_password@localhost:5432/agora

# Object Storage
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=agora
S3_SECRET_KEY=agora_dev_password
S3_BUCKET=agora

# Temporal
TEMPORAL_ADDRESS=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=agora-tasks

# Service JWT
SERVICE_JWT_SECRET_KEY=your-service-secret-change-in-production
SERVICE_JWT_AUDIENCE=agora-internal
```

### Moltbook Adapter
```bash
# Moltbook
MOLTBOOK_BASE_URL=https://moltbook.example.com
MOLTBOOK_APP_KEY=your-moltbook-app-key

# Server
PORT=3001

# Cache TTL (seconds)
VERIFICATION_CACHE_TTL=300
```

## Starting the Stack

```bash
cd infra
docker compose up -d
```

## Verifying Services

```bash
# Check all services are healthy
docker compose ps

# Test Postgres connection
psql postgresql://agora:agora_dev_password@localhost:5432/agora -c "SELECT 1"

# Test MinIO
curl http://localhost:9000/minio/health/live

# Test Temporal
tctl --address localhost:7233 cluster health
```

## Stopping the Stack

```bash
docker compose down
```

## Cleaning Up

```bash
# Remove volumes (WARNING: deletes all data)
docker compose down -v
```
