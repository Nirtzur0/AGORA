.PHONY: help up down logs test check-stubs clean test-unit test-integration test-e2e test-all

PYTHON ?= python3
PYTEST_ENV ?= PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
# We disable global plugin autoloading because dev machines sometimes have
# third-party pytest plugins installed that can break collection (ex: langsmith).
PYTEST ?= $(PYTEST_ENV) $(PYTHON) -m pytest -p pytest_asyncio

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

up: ## Start all services (Postgres, Temporal, MinIO)
	@echo "Starting AGORA infrastructure..."
	cd infra && docker compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@echo "Services started. Run 'make logs' to see logs."

down: ## Stop all services
	@echo "Stopping AGORA infrastructure..."
	cd infra && docker compose down

logs: ## Show logs from all services
	cd infra && docker compose logs -f

test: check-stubs test-unit ## Run fast tests (unit only)
	@echo "Unit tests passed ✓"

test-all: check-stubs test-unit test-integration ## Run unit + integration (requires local infra)
	@echo "Unit + integration tests passed ✓"

test-unit: ## Run unit tests only (no external services)
	@echo "Running unit tests..."
	@$(PYTEST) -q tests/unit

test-integration: ## Run integration tests (requires local infra: Postgres/MinIO/Temporal)
	@echo "Running integration tests..."
	@$(PYTEST) -q tests/integration

test-e2e: ## Run end-to-end tests (slow; may require Docker/Temporal)
	@echo "Running e2e tests..."
	@$(PYTEST) -q tests/e2e

test-db: ## Run database migration tests
	@echo "Running database migration tests..."
	@echo "Creating test database if needed..."
	@docker exec agora-postgres psql -U agora -c "DROP DATABASE IF EXISTS agora_test;" 2>/dev/null || true
	@docker exec agora-postgres psql -U agora -c "CREATE DATABASE agora_test;" 2>/dev/null || true
	cd packages/db && TEST_DATABASE_URL=postgresql://agora:agora_dev_password@localhost:5432/agora_test $(PYTEST) test_migrations.py -v
	@echo "Database tests passed ✓"

test-storage: ## Run storage layer tests
	@echo "Running storage layer tests..."
	cd packages/shared-types && $(PYTEST) test_storage.py -v
	@echo "Storage tests passed ✓"

check-stubs: ## Check for TODO/stub code in production dirs
	@echo "Checking for stubs/TODOs in production code..."
	@if grep -rn "TODO" apps/core-api/*.py apps/worker/*.py 2>/dev/null | grep -v "test_" | grep -v "#.*TODO"; then \
		echo "ERROR: Found TODO markers in production code"; \
		exit 1; \
	fi
	@if grep -rn "pass$$" apps/core-api/*.py apps/worker/*.py 2>/dev/null | grep -v "test_" | grep -v "except.*pass" | grep -v "#.*pass"; then \
		echo "ERROR: Found bare 'pass' statements in production code"; \
		exit 1; \
	fi
	@echo "No stubs found in production code ✓"

clean: down ## Clean up all volumes and data
	@echo "Cleaning up volumes (this will delete all data)..."
	cd infra && docker compose down -v
	@echo "Cleanup complete."

dev-core-api: ## Run core API locally (for development)
	cd apps/core-api && python main.py

install-core-api: ## Install core-api dependencies
	cd apps/core-api && pip install -r requirements.txt -r requirements-dev.txt

install-db: ## Install db package dependencies
	cd packages/db && pip install -r requirements.txt -r requirements-test.txt

install-storage: ## Install shared-types package dependencies
	cd packages/shared-types && pip install -r requirements.txt -r requirements-test.txt

install-moltbook: ## Install Moltbook adapter dependencies
	@echo "Installing Moltbook adapter dependencies..."
	cd apps/moltbook-adapter && npm install

build-moltbook: ## Build Moltbook adapter
	@echo "Building Moltbook adapter..."
	cd apps/moltbook-adapter && npm run build

migrate-up: ## Run database migrations
	@echo "Running migrations..."
	cd packages/db && python -m db.migrate up
	@echo "Seeding roles..."
	cd packages/db && python -m db.migrate seed_roles

seed-roles: ## Seed roles with canonical permissions
	@echo "Seeding roles..."
	cd packages/db && python migrations/002_seed_roles.py

migrate-create: ## Create a new migration (usage: make migrate-create NAME=description)
	@echo "Creating migration: $(NAME)"
	cd packages/db && python -m db.migrate create "$(NAME)"

.PHONY: help init up down db-migrate db-rollback logs install-core install-worker install-storage install-moltbook install-test-deps test test-all test-db test-storage test-moltbook test-auth test-rbac build-moltbook check-stubs clean seed-roles
