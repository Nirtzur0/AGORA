# Docker Setup Guide for AGORA

## Current Status

❌ **Docker is not installed on your system**

AGORA requires Docker Desktop to run the following infrastructure services:
- PostgreSQL (application database)
- PostgreSQL (Temporal workflow engine)
- MinIO (S3-compatible object storage)
- Temporal Server (workflow orchestration)
- Temporal UI (workflow monitoring)

## Installation Steps for macOS

### Option 1: Install Docker Desktop (Recommended)

1. **Download Docker Desktop**
   ```bash
   open https://www.docker.com/products/docker-desktop
   ```
   Or download directly: https://desktop.docker.com/mac/main/arm64/Docker.dmg (Apple Silicon) or https://desktop.docker.com/mac/main/amd64/Docker.dmg (Intel)

2. **Install Docker Desktop**
   - Open the downloaded `.dmg` file
   - Drag Docker to Applications folder
   - Launch Docker from Applications
   - Follow the setup wizard

3. **Verify Installation**
   ```bash
   docker --version
   docker compose version
   ```

4. **Start Docker Desktop**
   - Ensure Docker Desktop is running (whale icon in menu bar)
   - Wait for "Docker Desktop is running" status

### Option 2: Install via Homebrew

```bash
brew install --cask docker
open -a Docker  # Start Docker Desktop
```

## After Docker Installation

Once Docker is installed and running, continue with AGORA setup:

```bash
cd /Users/nirtzur/Documents/projects/AGORA

# Start all infrastructure services
make up

# Verify services are running
docker ps

# Check service health
docker compose -f infra/docker-compose.yml ps
```

## Expected Services After `make up`

You should see these containers running:

```
CONTAINER ID   IMAGE                              STATUS                    PORTS
xxxxx          postgres:15-alpine                 Up (healthy)             0.0.0.0:5432->5432/tcp
xxxxx          postgres:15-alpine                 Up (healthy)             0.0.0.0:5433->5432/tcp
xxxxx          minio/minio:latest                 Up (healthy)             0.0.0.0:9000-9001->9000-9001/tcp
xxxxx          temporalio/auto-setup:1.22.4       Up (healthy)             0.0.0.0:7233->7233/tcp
xxxxx          temporalio/ui:2.21.3               Up                       0.0.0.0:8080->8080/tcp
```

## Next Steps After Docker Setup

1. **Run Database Migrations**
   ```bash
   make migrate-up
   ```

2. **Run Tests**
   ```bash
   make test
   ```

3. **Start Core API**
   ```bash
   make dev-core-api
   ```

4. **Start Temporal Workers**
   ```bash
   # In a new terminal
   cd apps/worker
   python -m temporalio.worker
   ```

5. **Start Web UI**
   ```bash
   # In another terminal
   cd apps/web
   npm install
   npm run dev
   ```

6. **Run Evaluation Harness**
   ```bash
   python scripts/run_evaluation.py --verbose
   ```

## Service URLs Once Running

- **Core API**: http://localhost:8000
  - Health: http://localhost:8000/health
  - Docs: http://localhost:8000/docs
- **Temporal UI**: http://localhost:8080
- **MinIO Console**: http://localhost:9001
  - Username: `agora`
  - Password: `agora_dev_password`
- **Web UI**: http://localhost:3000 (after starting dev server)

## Troubleshooting

### Docker Command Not Found After Installation

If Docker is installed but command not found:

```bash
# Add Docker to PATH
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"

# Add to ~/.zshrc for persistence
echo 'export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### Services Not Starting

```bash
# Check Docker Desktop is running
ps aux | grep Docker

# View service logs
cd infra
docker compose logs -f

# Restart services
docker compose down
docker compose up -d
```

### Port Conflicts

If ports 5432, 9000, etc. are already in use:

```bash
# Check what's using the port
lsof -i :5432
lsof -i :9000

# Kill the process or modify docker-compose.yml ports
```

## Alternative: Run Without Docker (Not Recommended)

Running without Docker requires manual installation of:
- PostgreSQL 15+
- Temporal Server
- MinIO
- Manual configuration of all connection strings

This is **not supported** and significantly more complex. Docker is the recommended approach.

---

## Current Action Required

**Please install Docker Desktop and start it, then run:**

```bash
cd /Users/nirtzur/Documents/projects/AGORA
make up
```

This will start all required infrastructure services for AGORA.
