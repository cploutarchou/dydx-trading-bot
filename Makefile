.PHONY: help dev prod setup install test lint format clean run start stop status restart logs docker-build docker-run docker-stop docker-logs docker-shell docker-dev docker-clean docker-up docker-down docker-up-logging docker-down-logging test-loki test-loki-dev test-loki-prod backtest backtest-quick backtest-3month backtest-analysis backtest-clean api-run backend-run worker-run config edit-config dev-config prod-config config-keygen config-key-rotate install-config-key show-config-token encrypt-dev-config decrypt-dev-config encrypt-prod-config decrypt-prod-config install-security-tools env-setup env db-upgrade db-downgrade db-revision db-current db-history db-merge db-branches db-init create-migration migration-up migration-down migration-verify db-init-schema db-verify-schema db-reset db-migrate-legacy db-up db-status db-down infra-up infra-down infra-logs infra-ps dev-infra dev-infra-down stack-env stack-env-check stack-up-dev stack-up-prod stack-up-integration stack-down stack-logs stack-ps docs-governance images-build images-build-latest images-push images-push-latest images-print
MODE ?= development
STACK_COMPOSE_FILE ?= docker-compose.stack.yml
INFRA_COMPOSE_FILE ?= docker-compose.infra.yml
IMAGE_REGISTRY ?= ghcr.io/cploutarchou/dydx-trading-bot
IMAGE_TAG ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo latest)

DEV_INFRA_NETWORK ?= dydx-dev-infra
DEV_MARIADB_CONTAINER ?= dydx-dev-mariadb
DEV_BOT_MARIADB_CONTAINER ?= dydx-dev-bot-mariadb
DEV_REDIS_CONTAINER ?= dydx-dev-redis
DEV_MARIADB_VOLUME ?= dydx-dev-mariadb-data
DEV_BOT_MARIADB_VOLUME ?= dydx-dev-bot-mariadb-data
DEV_MARIADB_USER ?= dydx_bot
DEV_MARIADB_PASSWORD ?= change-me-db-password
DEV_MARIADB_DB ?= dydx_bot
DEV_MARIADB_PORT ?= 3306
DEV_BOT_MARIADB_USER ?= dydx_bot
DEV_BOT_MARIADB_PASSWORD ?= change-me-db-password
DEV_BOT_MARIADB_DB ?= dydx_bot
DEV_BOT_MARIADB_PORT ?= 3307
DEV_REDIS_PORT ?= 6379

# Default target - show help when running just 'make'
help: ## Show this help message
	@echo "dYdX Trading Bot - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Daily service-first quick start:"
	@echo "  1. make config-keygen   # Create .configkey.bin and print the shareable token"
	@echo "  2. make dev-config      # Edit the encrypted development profile"
	@echo "  3. make dev             # Decrypt development profile into run.json"
	@echo "  4. make infra-up        # Start shared mariadb + redis only"
	@echo "  5. Start your service from its own workspace/devcontainer"
	@echo ""
	@echo "Integration quick start:"
	@echo "  1. make stack-up-dev    # Start frontend + api + worker + db + redis"
	@echo "  2. make stack-ps        # Check service status"
	@echo "  3. make stack-logs      # Follow logs"
	@echo ""

# ============================================================================
# ENVIRONMENT & SETUP
# ============================================================================

setup: ## Create Python virtual environment
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip setuptools wheel
	@echo "✅ Virtual environment created at .venv/"
	@echo "📌 Activate with: source .venv/bin/activate"

install: ## Install all dependencies including backend package
	@echo "Installing dependencies per service (backend/frontend/bot)..."
	cd backend && go mod download
	cd frontend && npm install
	cd bot && .venv/bin/pip install --upgrade pip setuptools wheel && .venv/bin/pip install -r requirements.txt
	@echo "✅ Service dependencies installed"

config: ## Deprecated legacy config target (bot uses runtime config under bot/)
	@echo "⚠️  'make config' is deprecated for this monorepo layout."
	@echo "Use stack/dev workflows and bot runtime config under bot/ instead."

edit-config: ## Open MODE JSON config files in your editor and normalize them on close
	@python3 scripts/edit_config.py --environment $(MODE)

dev-config: ## Open the encrypted development config profile
	@$(MAKE) edit-config MODE=development

prod-config: ## Open the encrypted production config profile
	@$(MAKE) edit-config MODE=production

config-keygen: ## Create repo-root .configkey.bin and print the shareable config token
	@python3 scripts/secure_config.py keygen

install-config-key: ## Rebuild .configkey.bin from TOKEN=<printed-token>
	@if [ -z "$(TOKEN)" ]; then \
		echo "Usage: make install-config-key TOKEN=<printed-config-token>"; \
		exit 1; \
	fi
	@python3 scripts/secure_config.py install-key --token "$(TOKEN)"

show-config-token: ## Print the current shareable token for .configkey.bin
	@python3 scripts/secure_config.py show-token

config-key-rotate: ## Rotate .configkey.bin, re-encrypt profiles, and print the new shareable token
	@python3 scripts/secure_config.py rotate-key

decrypt-dev-config: ## Decrypt development profile to config/profiles/development.config.json
	@python3 scripts/secure_config.py decrypt --environment development --output config/profiles/development.config.json

encrypt-dev-config: ## Encrypt config/profiles/development.config.json back into the secure profile
	@python3 scripts/secure_config.py encrypt --environment development --input config/profiles/development.config.json

decrypt-prod-config: ## Decrypt production profile to config/profiles/production.config.json
	@python3 scripts/secure_config.py decrypt --environment production --output config/profiles/production.config.json

encrypt-prod-config: ## Encrypt config/profiles/production.config.json back into the secure profile
	@python3 scripts/secure_config.py encrypt --environment production --input config/profiles/production.config.json

install-security-tools: ## Bootstrap the repo-owned config key workflow
	@bash scripts/install_security_tools.sh

env-setup: ## Deprecated: use `make dev` or `make prod` to generate run.json
	@echo "⚠️  env-setup is deprecated."
	@echo "Use make dev-config / make prod-config, then make dev / make prod."

env: ## Show deprecation warning for .env
	@echo "⚠️  WARNING: repo-root .env is deprecated."
	@echo "Use config/profiles/<env>.config.enc.json and generate run.json with make dev."

# ============================================================================
# DEVELOPMENT
# ============================================================================

test: ## Run pytest suite (tests/ directory only)
	@echo "Running service-level verification..."
	cd backend && make test
	cd frontend && npm run lint && npm run build
	cd bot && .venv/bin/python -m pytest tests/ -v --tb=short

docs-governance: ## Validate canonical docs links and archival policy
	python3 scripts/validate_docs_governance.py

validate-k8s-secrets: ## Fail when tracked k8s YAML contains plaintext secret values
	python3 scripts/check_no_plaintext_k8s_secrets.py

lint: ## Check code with flake8 and pylint
	.venv/bin/flake8 bot/src tests scripts --max-line-length=120 --exclude=__pycache__
	.venv/bin/pylint bot/src --disable=C0111,W0212 || true

format: ## Auto-format code with black
	.venv/bin/black bot/src tests scripts --line-length=120

clean: ## Remove build artifacts and cache files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".coverage" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Build artifacts cleaned"

# ============================================================================
# BOT COMMANDS
# ============================================================================

run: ## Run bot in foreground
	.venv/bin/python bot/main.py

backend-run: api-run ## Start bot API server (alias for api-run)

api-run: ## Start bot API server on port 8889
	.venv/bin/python -m uvicorn bot.src.api.server:app --reload --host 0.0.0.0 --port 8889

worker-run: ## Deprecated alias (kept for compatibility)
	@echo "⚠️  'make worker-run' is deprecated; use 'make api-run' instead."
	@$(MAKE) api-run

celery-worker: ## Start Celery worker for durable backtests
	cd bot && .venv/bin/celery -A src.infrastructure.workers.celery_app:celery_app worker --loglevel=$${CELERY_LOG_LEVEL:-INFO} --queues=$${CELERY_QUEUES:-backtests,default,high_priority,scheduled} --concurrency=$${CELERY_CONCURRENCY:-1}

celery-flower: ## Start internal/admin-only Flower UI on port 5555
	scripts/celery-flower.sh

celery-inspect: ## Inspect active, reserved, scheduled, and registered Celery tasks
	cd bot && .venv/bin/celery -A src.infrastructure.workers.celery_app:celery_app inspect active
	cd bot && .venv/bin/celery -A src.infrastructure.workers.celery_app:celery_app inspect reserved
	cd bot && .venv/bin/celery -A src.infrastructure.workers.celery_app:celery_app inspect scheduled
	cd bot && .venv/bin/celery -A src.infrastructure.workers.celery_app:celery_app inspect registered

celery-health: ## Check Celery worker availability
	cd bot && .venv/bin/celery -A src.infrastructure.workers.celery_app:celery_app inspect ping

celery-purge: ## Purge Celery queues after explicit confirmation
	cd bot && .venv/bin/celery -A src.infrastructure.workers.celery_app:celery_app purge

celery-revoke: ## Revoke a Celery task: make celery-revoke TASK_ID=<task-id> TERMINATE=false
	@if [ -z "$(TASK_ID)" ]; then echo "Usage: make celery-revoke TASK_ID=<task-id> TERMINATE=false"; exit 1; fi
	@if [ "$(TERMINATE)" = "true" ]; then \
		cd bot && .venv/bin/celery -A src.infrastructure.workers.celery_app:celery_app control revoke $(TASK_ID) --terminate; \
	else \
		cd bot && .venv/bin/celery -A src.infrastructure.workers.celery_app:celery_app control revoke $(TASK_ID); \
	fi

start: ## Start bot in background
	@if [ ! -f scripts/manage_bot.sh ]; then \
		echo "❌ scripts/manage_bot.sh not found"; \
		exit 1; \
	fi
	bash scripts/manage_bot.sh start
	@echo "✅ Bot started in background"

stop: ## Stop background bot
	@if [ ! -f scripts/manage_bot.sh ]; then \
		echo "❌ scripts/manage_bot.sh not found"; \
		exit 1; \
	fi
	bash scripts/manage_bot.sh stop
	@echo "✅ Bot stopped"

restart: ## Restart background bot
	@if [ ! -f scripts/manage_bot.sh ]; then \
		echo "❌ scripts/manage_bot.sh not found"; \
		exit 1; \
	fi
	bash scripts/manage_bot.sh restart
	@echo "✅ Bot restarted"

status: ## Check if bot is running
	@if [ ! -f scripts/manage_bot.sh ]; then \
		echo "❌ scripts/manage_bot.sh not found"; \
		exit 1; \
	fi
	bash scripts/manage_bot.sh status

logs: ## View recent bot logs
	@if [ -f bot_logs.txt ]; then \
		tail -100 bot_logs.txt; \
	else \
		echo "❌ bot_logs.txt not found"; \
		exit 1; \
	fi

# ============================================================================
# DOCKER
# ============================================================================

images-build: ## Build all deployable service images locally (api/worker/backend/frontend)
	IMAGE_REGISTRY=$(IMAGE_REGISTRY) IMAGE_TAG=$(IMAGE_TAG) PUSH=false ALSO_LATEST=false bash scripts/build_all_service_images.sh

images-build-latest: ## Build all deployable service images and tag :latest locally
	IMAGE_REGISTRY=$(IMAGE_REGISTRY) IMAGE_TAG=$(IMAGE_TAG) PUSH=false ALSO_LATEST=true bash scripts/build_all_service_images.sh

images-push: ## Build and push all deployable service images with IMAGE_TAG
	IMAGE_REGISTRY=$(IMAGE_REGISTRY) IMAGE_TAG=$(IMAGE_TAG) PUSH=true ALSO_LATEST=false bash scripts/build_all_service_images.sh

images-push-latest: ## Build and push all deployable service images with IMAGE_TAG and :latest
	IMAGE_REGISTRY=$(IMAGE_REGISTRY) IMAGE_TAG=$(IMAGE_TAG) PUSH=true ALSO_LATEST=true bash scripts/build_all_service_images.sh

images-print: ## Print image variables for CI/CD or deployment env files
	@echo "IMAGE_REGISTRY=$(IMAGE_REGISTRY)"
	@echo "IMAGE_TAG=$(IMAGE_TAG)"

docker-build: ## Build Docker image
	docker build -t dydx-trading-bot:latest .
	@echo "✅ Docker image built"

docker-run: ## Run bot in Docker container
	docker run -it --rm \
		-v $(PWD)/app:/app/app \
		-v $(PWD)/.env:/.env \
		--name dydx-bot \
		dydx-trading-bot:latest

docker-stop: ## Stop Docker container
	docker stop dydx-bot || true
	@echo "✅ Docker container stopped"

docker-logs: ## View Docker container logs
	docker logs -f dydx-bot || echo "Container not running"

docker-shell: ## Open shell in running Docker container
	docker exec -it dydx-bot /bin/bash

docker-dev: ## Build development Docker image with live code mounting
	docker build -f Dockerfile.dev -t dydx-trading-bot:dev .
	@echo "✅ Development Docker image built"

docker-clean: ## Remove Docker image and containers
	docker stop dydx-bot || true
	docker rm dydx-bot || true
	docker rmi dydx-trading-bot:latest dydx-trading-bot:dev || true
	@echo "✅ Docker resources cleaned"

docker-up: ## Start with Docker Compose
	docker-compose up -d
	@echo "✅ Services started with Docker Compose"

docker-down: ## Stop Docker Compose services
	docker-compose down
	@echo "✅ Docker Compose services stopped"

docker-up-logging: ## Start full observability stack (Loki + Grafana)
	docker-compose -f docker-compose.full-stack.yml up -d
	@echo "✅ Logging stack started"
	@echo "📊 Grafana: http://localhost:3000 (admin/admin)"
	@echo "📋 Loki: http://localhost:3100"

docker-down-logging: ## Stop logging stack
	docker-compose -f docker-compose.full-stack.yml down
	@echo "✅ Logging stack stopped"

# ============================================================================
# TESTING
# ============================================================================

test-loki: ## Test Loki connectivity (default environment)
	.venv/bin/python scripts/test_loki.py

test-loki-dev: ## Test Loki connectivity (development environment)
	.venv/bin/python scripts/test_loki.py development

test-loki-prod: ## Test Loki connectivity (production environment)
	.venv/bin/python scripts/test_loki.py production

# ============================================================================
# BACKTESTING
# ============================================================================

backtest-quick: ## Run quick 1-month backtest with 3 pairs
	.venv/bin/python scripts/run_backtest.py --start 2024-09-01 --end 2024-10-01 --pairs 3

backtest-3month: ## Run 3-month backtest with 10 pairs
	.venv/bin/python scripts/run_backtest.py --start 2024-07-01 --end 2024-10-01 --pairs 10

backtest: ## Run custom backtest (use START=YYYY-MM-DD END=YYYY-MM-DD PAIRS=N)
	@if [ -z "$(START)" ] || [ -z "$(END)" ] || [ -z "$(PAIRS)" ]; then \
		echo "Usage: make backtest START=2024-01-01 END=2024-03-31 PAIRS=5"; \
		exit 1; \
	fi
	.venv/bin/python scripts/run_backtest.py --start $(START) --end $(END) --pairs $(PAIRS)

backtest-analysis: ## Analyze backtest results
	.venv/bin/python scripts/analyze_backtest_results.py --top 5 --chart

backtest-clean: ## Clean up old backtest results (keeps 20 most recent)
	.venv/bin/python scripts/analyze_backtest_results.py --cleanup

# ============================================================================
# MIGRATIONS - Simple Commands
# ============================================================================

create-migration: ## Create new migration: make create-migration MSG='add user table'
	@if [ -z "$(MSG)" ]; then \
		echo "Usage: make create-migration MSG='describe your changes'"; \
		echo "Example: make create-migration MSG='add user profile columns'"; \
		exit 1; \
	fi
	.venv/bin/alembic revision --autogenerate -m "$(MSG)"
	@echo "✅ Migration created in alembic/versions/"

migration-up: ## Apply all pending migrations
	.venv/bin/alembic upgrade head
	@echo "✅ Database upgraded to latest migration"

migration-down: ## Rollback N migrations: make migration-down N=1
	@if [ -z "$(N)" ]; then \
		echo "Usage: make migration-down N=1"; \
		exit 1; \
	fi
	.venv/bin/alembic downgrade -$(N)
	@echo "✅ Rolled back $(N) migration(s)"

migration-verify: ## Show current migration & history
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "📍 CURRENT MIGRATION:"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@.venv/bin/alembic current
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "📜 MIGRATION HISTORY:"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@.venv/bin/alembic history --verbose
	@echo "✅ Verification complete"

db-init-schema: ## Initialize database schema (creates all tables)
	.venv/bin/python scripts/init_database.py --init
	@echo "✅ Database schema initialized"

db-verify-schema: ## Verify database schema integrity
	.venv/bin/python scripts/init_database.py --verify

db-reset: ## Reset database (drop and recreate all tables) - USE WITH CAUTION!
	.venv/bin/python scripts/init_database.py --reset

# Legacy/Advanced (kept for reference)
db-init: ## Initialize Alembic migrations (one-time setup)
	.venv/bin/alembic init alembic
	@echo "✅ Alembic initialized"

db-revision: ## Create migration (use MESSAGE=) - Use 'create-migration' instead
	@if [ -z "$(MESSAGE)" ]; then \
		echo "Usage: make db-revision MESSAGE='describe your changes'"; \
		exit 1; \
	fi
	.venv/bin/alembic revision --autogenerate -m "$(MESSAGE)"

db-upgrade: ## Apply migrations - Use 'migration-up' instead
	.venv/bin/alembic upgrade head

db-downgrade: ## Rollback - Use 'migration-down N=X' instead
	@if [ -z "$(STEPS)" ]; then \
		echo "Usage: make db-downgrade STEPS=1"; \
		exit 1; \
	fi
	.venv/bin/alembic downgrade -$(STEPS)

db-current: ## Show current migration - Use 'migration-verify' instead
	.venv/bin/alembic current

db-history: ## Show history - Use 'migration-verify' instead
	.venv/bin/alembic history --verbose

db-branches: ## Show migration branches
	.venv/bin/alembic branches

db-merge: ## Merge branches (use MESSAGE=)
	@if [ -z "$(MESSAGE)" ]; then \
		echo "Usage: make db-merge MESSAGE='description'"; \
		exit 1; \
	fi
	.venv/bin/alembic merge -m "$(MESSAGE)"

db-migrate-legacy: ## Run legacy migration (migrate_db.py)
	.venv/bin/python migrate_db.py

# ============================================================================
# UTILITY
# ============================================================================

db-up: ## Start backend DB services (mariadb + redis) via Docker Compose
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		docker compose -f backend/docker-compose.yml up -d mariadb redis; \
		echo "✅ Backend DB services started"; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot start DB services"; \
		exit 0; \
	fi

db-status: ## Show backend DB services status via Docker Compose
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		docker compose -f backend/docker-compose.yml ps mariadb redis; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot query DB service status"; \
		exit 0; \
	fi

db-down: ## Stop backend DB services (mariadb + redis) via Docker Compose
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		docker compose -f backend/docker-compose.yml stop mariadb redis; \
		echo "✅ Backend DB services stopped"; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot stop DB services"; \
		exit 0; \
	fi

infra-up: ## Start shared infra only (mariadb + redis) for local service development
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(INFRA_COMPOSE_FILE)" ]; then \
			echo "❌ Missing $(INFRA_COMPOSE_FILE)."; \
			echo "   Use make dev-infra (docker-run based local infra) as fallback."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(INFRA_COMPOSE_FILE) up -d --remove-orphans; \
		echo "✅ Infra started (mariadb:3306, redis:6379)"; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot start infra"; \
		exit 0; \
	fi

infra-down: ## Stop shared infra only (mariadb + redis)
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(INFRA_COMPOSE_FILE)" ]; then \
			echo "❌ Missing $(INFRA_COMPOSE_FILE). Nothing to stop via infra commands."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(INFRA_COMPOSE_FILE) down --remove-orphans; \
		echo "✅ Infra stopped"; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot stop infra"; \
		exit 0; \
	fi

infra-logs: ## Follow logs for shared infra services (mariadb + redis)
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(INFRA_COMPOSE_FILE)" ]; then \
			echo "❌ Missing $(INFRA_COMPOSE_FILE)."; \
			echo "   Tip: use docker logs for dev-infra containers ($(DEV_MARIADB_CONTAINER), $(DEV_BOT_MARIADB_CONTAINER), $(DEV_REDIS_CONTAINER))."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(INFRA_COMPOSE_FILE) logs -f --tail=100; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot fetch infra logs"; \
		exit 0; \
	fi

infra-ps: ## Show status for shared infra services (mariadb + redis)
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(INFRA_COMPOSE_FILE)" ]; then \
			echo "❌ Missing $(INFRA_COMPOSE_FILE)."; \
			echo "   Tip: use make dev-infra and inspect with docker ps | grep dydx-dev-."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(INFRA_COMPOSE_FILE) ps; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot fetch infra status"; \
		exit 0; \
	fi

check-no-legacy-db: ## Fail if active code/config contains legacy database patterns
	python3 scripts/check_no_legacy_database.py

dev-infra: ## Start local backend MariaDB + bot MariaDB + Redis and print matching runtime config
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "⚠️  Docker CLI is not installed"; \
		exit 0; \
	elif ! docker info >/dev/null 2>&1; then \
		echo "⚠️  Docker daemon is not reachable from this shell."; \
		echo "   If the error is 'permission denied' on /var/run/docker.sock, add your user to the docker group and re-login."; \
		echo "   Socket owner/group is typically root:docker and your user must be in that group."; \
		exit 0; \
	else \
		set -e; \
		docker network inspect $(DEV_INFRA_NETWORK) >/dev/null 2>&1 || docker network create $(DEV_INFRA_NETWORK); \
		docker volume inspect $(DEV_MARIADB_VOLUME) >/dev/null 2>&1 || docker volume create $(DEV_MARIADB_VOLUME) >/dev/null; \
		docker volume inspect $(DEV_BOT_MARIADB_VOLUME) >/dev/null 2>&1 || docker volume create $(DEV_BOT_MARIADB_VOLUME) >/dev/null; \
		if docker ps -a --format '{{.Names}}' | grep -qx '$(DEV_MARIADB_CONTAINER)'; then \
			docker start $(DEV_MARIADB_CONTAINER) >/dev/null; \
		else \
			docker run -d --name $(DEV_MARIADB_CONTAINER) \
				--network $(DEV_INFRA_NETWORK) \
				-p $(DEV_MARIADB_PORT):3306 \
				-e MYSQL_USER=$(DEV_MARIADB_USER) \
				-e MYSQL_PASSWORD=$(DEV_MARIADB_PASSWORD) \
				-e MYSQL_DATABASE=$(DEV_MARIADB_DB) \
				-e MYSQL_ROOT_PASSWORD=$(DEV_MARIADB_PASSWORD) \
				-v $(DEV_MARIADB_VOLUME):/var/lib/mysql \
				mariadb:11 >/dev/null; \
		fi; \
		if docker ps -a --format '{{.Names}}' | grep -qx '$(DEV_BOT_MARIADB_CONTAINER)'; then \
			docker start $(DEV_BOT_MARIADB_CONTAINER) >/dev/null; \
		else \
			docker run -d --name $(DEV_BOT_MARIADB_CONTAINER) \
				--network $(DEV_INFRA_NETWORK) \
				-p $(DEV_BOT_MARIADB_PORT):3306 \
				-e MYSQL_USER=$(DEV_BOT_MARIADB_USER) \
				-e MYSQL_PASSWORD=$(DEV_BOT_MARIADB_PASSWORD) \
				-e MYSQL_DATABASE=$(DEV_BOT_MARIADB_DB) \
				-e MYSQL_ROOT_PASSWORD=$(DEV_BOT_MARIADB_PASSWORD) \
				-v $(DEV_BOT_MARIADB_VOLUME):/var/lib/mysql \
				mariadb:11 >/dev/null; \
		fi; \
		if docker ps -a --format '{{.Names}}' | grep -qx '$(DEV_REDIS_CONTAINER)'; then \
			docker start $(DEV_REDIS_CONTAINER) >/dev/null; \
		else \
			docker run -d --name $(DEV_REDIS_CONTAINER) \
				--network $(DEV_INFRA_NETWORK) \
				-p $(DEV_REDIS_PORT):6379 \
				redis:7-alpine >/dev/null; \
		fi; \
		for i in 1 2 3 4 5 6 7 8 9 10; do \
			docker exec $(DEV_MARIADB_CONTAINER) mysqladmin ping -u $(DEV_MARIADB_USER) -p$(DEV_MARIADB_PASSWORD) >/dev/null 2>&1 && break; \
			sleep 1; \
		done; \
		for i in 1 2 3 4 5 6 7 8 9 10; do \
			docker exec $(DEV_BOT_MARIADB_CONTAINER) mysqladmin ping -u $(DEV_BOT_MARIADB_USER) -p$(DEV_BOT_MARIADB_PASSWORD) >/dev/null 2>&1 && break; \
			sleep 1; \
		done; \
		echo "✅ Dev infra ready: backend-mariadb=$(DEV_MARIADB_CONTAINER):$(DEV_MARIADB_PORT), bot-mariadb=$(DEV_BOT_MARIADB_CONTAINER):$(DEV_BOT_MARIADB_PORT), redis=$(DEV_REDIS_CONTAINER):$(DEV_REDIS_PORT)"; \
		echo "Use this runtime config:"; \
		echo '  "database": {'; \
		echo '    "DB_TYPE": "mysql",'; \
		echo '    "DB_HOST": "localhost",'; \
		echo '    "DB_PORT": '$(DEV_MARIADB_PORT)','; \
		echo '    "DB_NAME": "$(DEV_MARIADB_DB)",'; \
		echo '    "DB_USER": "$(DEV_MARIADB_USER)",'; \
		echo '    "DB_PASSWORD": "$(DEV_MARIADB_PASSWORD)",'; \
		echo '    "MYSQL_HOST": "localhost",'; \
		echo '    "MYSQL_PORT": '$(DEV_MARIADB_PORT)','; \
		echo '    "MYSQL_DATABASE": "$(DEV_MARIADB_DB)",'; \
		echo '    "MYSQL_USER": "$(DEV_MARIADB_USER)",'; \
		echo '    "MYSQL_PASSWORD": "$(DEV_MARIADB_PASSWORD)"'; \
		echo '  },'; \
		echo '  "bot_database": {'; \
		echo '    "BOT_DB_CUTOVER_MODE": "dedicated",'; \
		echo '    "BOT_DB_HOST": "localhost",'; \
		echo '    "BOT_DB_PORT": '$(DEV_BOT_MARIADB_PORT)','; \
		echo '    "BOT_DB_NAME": "$(DEV_BOT_MARIADB_DB)",'; \
		echo '    "BOT_DB_USER": "$(DEV_BOT_MARIADB_USER)",'; \
		echo '    "BOT_DB_PASSWORD": "$(DEV_BOT_MARIADB_PASSWORD)"'; \
		echo '  },'; \
		echo '  "redis": {'; \
		echo '    "REDIS_ENABLED": true,'; \
		echo '    "REDIS_HOST": "localhost",'; \
		echo '    "REDIS_PORT": '$(DEV_REDIS_PORT)','; \
		echo '    "REDIS_DB": 0,'; \
		echo '    "REDIS_SSL": false'; \
		echo '  }'; \
	fi

dev-infra-down: ## Stop/remove local backend MariaDB + bot MariaDB + Redis created by dev-infra
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "⚠️  Docker CLI is not installed"; \
		exit 0; \
	elif ! docker info >/dev/null 2>&1; then \
		echo "⚠️  Docker daemon is not reachable from this shell."; \
		echo "   If the error is 'permission denied' on /var/run/docker.sock, add your user to the docker group and re-login."; \
		exit 0; \
	else \
		docker rm -f $(DEV_MARIADB_CONTAINER) $(DEV_BOT_MARIADB_CONTAINER) $(DEV_REDIS_CONTAINER) >/dev/null 2>&1 || true; \
		echo "✅ Dev infra containers removed"; \
		echo "ℹ️  Volumes $(DEV_MARIADB_VOLUME) and $(DEV_BOT_MARIADB_VOLUME) were kept (data preserved)."; \
	fi

stack-up-dev: ## Start full integration stack (api + worker + frontend dev + mariadb + redis)
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(STACK_COMPOSE_FILE)" ]; then \
			echo "❌ Missing $(STACK_COMPOSE_FILE)."; \
			echo "   Use service-first workflow instead: make infra-up, then run backend/frontend/bot individually."; \
			exit 1; \
		fi; \
		set -e; \
		python3 scripts/validate_stack_env.py --environment development; \
		APP_CONFIG_ENV=development docker compose -f $(STACK_COMPOSE_FILE) --profile dev up -d --remove-orphans; \
		echo "✅ Dev stack started (frontend:5173, api:8889, worker enabled)"; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot start stack"; \
		exit 0; \
	fi

stack-up-prod: ## Start split app stack (api + worker + frontend preview + mariadb + redis)
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(STACK_COMPOSE_FILE)" ]; then \
			echo "❌ Missing $(STACK_COMPOSE_FILE)."; \
			echo "   Use service-first workflow instead: make infra-up, then run backend/frontend/bot individually."; \
			exit 1; \
		fi; \
		set -e; \
		python3 scripts/validate_stack_env.py --environment production --strict-prod; \
		APP_CONFIG_ENV=production docker compose -f $(STACK_COMPOSE_FILE) --profile prod up -d --remove-orphans; \
		echo "✅ Prod-like stack started (proxy:8080, api internal, frontend internal)"; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot start stack"; \
		exit 0; \
	fi

stack-up-integration: stack-up-dev ## Alias for full integration stack in dev profile

stack-down: ## Stop split app stack
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(STACK_COMPOSE_FILE)" ]; then \
			echo "❌ Missing $(STACK_COMPOSE_FILE). Nothing to stop via stack commands."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(STACK_COMPOSE_FILE) --profile dev --profile prod down --remove-orphans; \
		echo "✅ Stack stopped"; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot stop stack"; \
		exit 0; \
	fi

stack-logs: ## Follow logs for split app stack
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(STACK_COMPOSE_FILE)" ]; then \
			echo "❌ Missing $(STACK_COMPOSE_FILE)."; \
			echo "   Tip: use make infra-logs and service-level logs instead."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(STACK_COMPOSE_FILE) logs -f --tail=100; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot fetch logs"; \
		exit 0; \
	fi

stack-ps: ## Show status for split app stack services
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(STACK_COMPOSE_FILE)" ]; then \
			echo "❌ Missing $(STACK_COMPOSE_FILE)."; \
			echo "   Tip: use make infra-ps for infra status and service-specific run commands."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(STACK_COMPOSE_FILE) ps; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot fetch service status"; \
		exit 0; \
	fi

stack-env: ## Deprecated: stack reads structured JSON config directly
	@echo "⚠️  stack-env is deprecated."
	@echo "Use make dev-config or make prod-config instead."

stack-env-check: ## Validate required variables in structured config
	python3 scripts/validate_stack_env.py --environment $(MODE)

stack-env-check-prod: ## Validate production structured config with strict rules
	python3 scripts/validate_stack_env.py --environment production --strict-prod

.DEFAULT_GOAL := help
dev: ## Prepare repo-root run.json from the encrypted development profile
	@python3 scripts/render_run_config.py --environment development --output run.json
	@python3 scripts/validate_stack_env.py --environment development
	@echo "✅ run.json is ready for local development"

prod: ## Prepare repo-root run.json from the encrypted production profile
	@python3 scripts/render_run_config.py --environment production --output run.json
	@python3 scripts/validate_stack_env.py --environment production --strict-prod
	@echo "✅ run.json is ready for production-like startup"
