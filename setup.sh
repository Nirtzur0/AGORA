#!/bin/bash
# Setup script for AGORA development environment

set -e

echo "🚀 Setting up AGORA development environment..."

# Check prerequisites
echo "Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed."; exit 1; }
command -v docker-compose >/dev/null 2>&1 || command -v docker compose >/dev/null 2>&1 || { echo "❌ Docker Compose is required but not installed."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 is required but not installed."; exit 1; }
command -v pip3 >/dev/null 2>&1 || { echo "❌ pip3 is required but not installed."; exit 1; }

echo "✓ Prerequisites check passed"

# Start infrastructure
echo ""
echo "📦 Starting infrastructure (Postgres, Temporal, MinIO)..."
cd infra
docker compose up -d
cd ..

echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check service health
echo "Checking Postgres..."
docker exec agora-postgres pg_isready -U agora || { echo "❌ Postgres not ready"; exit 1; }
echo "✓ Postgres is healthy"

echo "Checking MinIO..."
curl -sf http://localhost:9000/minio/health/live >/dev/null || { echo "❌ MinIO not ready"; exit 1; }
echo "✓ MinIO is healthy"

# Install Python dependencies
echo ""
echo "📚 Installing Python dependencies..."

echo "Installing db package dependencies..."
cd packages/db
pip3 install -r requirements.txt -r requirements-test.txt
cd ../..

echo "Installing shared-types package dependencies..."
cd packages/shared-types
pip3 install -r requirements.txt -r requirements-test.txt
cd ../..

echo "Installing test dependencies..."
pip3 install -r tests/requirements.txt

echo "Installing core-api dependencies..."
cd apps/core-api
pip3 install -r requirements.txt -r requirements-dev.txt
cd ../..

# Run migrations
echo ""
echo "🗄️  Running database migrations..."
cd packages/db
python3 -m db.migrate up
cd ../..

# Run tests
echo ""
echo "🧪 Running tests..."
pytest tests/ -v

echo "Running storage tests..."
pytest tests/test_storage.py -v

# Install and test Moltbook adapter
echo ""
echo "📦 Installing Moltbook adapter dependencies..."
cd apps/moltbook-adapter
npm install

echo ""
echo "🔨 Building Moltbook adapter..."
npm run build
cd ../..

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start the Core API: make dev-core-api"
echo "  2. Or run tests: make test"
echo "  3. Or view logs: make logs"
echo ""
echo "Service URLs:"
echo "  - Core API: http://localhost:8000"
echo "  - Core API docs: http://localhost:8000/docs"
echo "  - Moltbook Adapter: http://localhost:3001"
echo "  - Temporal UI: http://localhost:8080"
echo "  - MinIO console: http://localhost:9001 (user: agora, password: agora_dev_password)"
