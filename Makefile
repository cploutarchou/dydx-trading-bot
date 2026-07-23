.PHONY: help completion-powershell install-completion-powershell windows-check dev prod setup install test lint format clean run start stop status restart logs docker-build docker-run docker-stop docker-logs docker-shell docker-dev docker-clean docker-up docker-down docker-up-logging docker-down-logging test-loki test-loki-dev test-loki-prod backtest backtest-quick backtest-3month backtest-analysis backtest-clean api-run backend-run worker-run config edit-config dev-config prod-config config-keygen config-key-rotate install-config-key show-config-token encrypt-dev-config decrypt-dev-config encrypt-prod-config decrypt-prod-config install-security-tools env-setup env db-upgrade db-downgrade db-revision db-current db-history db-merge db-branches db-init create-migration migration-up migration-down migration-verify db-init-schema db-verify-schema db-reset db-migrate-legacy db-up db-status db-down infra-up infra-down infra-logs infra-ps dev-infra dev-infra-down stack-env stack-env-check stack-up-dev stack-up-prod stack-up-integration stack-down stack-logs stack-ps docs-governance images-build images-build-latest images-push images-push-latest images-print infra-up-arm64 infra-down-arm64 infra-logs-arm64 infra-ps-arm64 stack-up-dev-arm64 stack-up-prod-arm64 stack-up-integration-arm64 stack-down-arm64 stack-logs-arm64 stack-ps-arm64 images-build-arm64 images-build-latest-arm64 images-push-arm64 images-push-latest-arm64

# Windows GNU Make defaults to cmd.exe, but this Makefile intentionally uses
# POSIX recipes. Keep PowerShell as the interactive terminal and run recipes in
# an installed MSYS2/Git Bash. Override with `make WINDOWS_BASH=...` if needed.
ifeq ($(OS),Windows_NT)
PYTHON ?= python
# Git Bash inherits the Windows PATH (including Docker Desktop). A stock MSYS2
# Bash often exposes only MSYS tools, which makes an installed docker.exe look
# unavailable to recipes.
WINDOWS_BASH ?= $(firstword $(wildcard C:/PROGRA~1/Git/bin/bash.exe) $(wildcard C:/msys64/usr/bin/bash.exe))
ifneq ($(strip $(WINDOWS_BASH)),)
SHELL := $(WINDOWS_BASH)
endif
POWERSHELL ?= powershell.exe
else
PYTHON ?= python3
endif
MODE ?= development
STACK_COMPOSE_FILE ?= docker-compose.stack.yml
STACK_COMPOSE_FILE_ARM64 ?= docker-compose.stack.arm64.yml
INFRA_COMPOSE_FILE ?= docker-compose.infra.yml
INFRA_COMPOSE_FILE_ARM64 ?= docker-compose.infra.arm64.yml
IMAGE_REGISTRY ?= ghcr.io/cploutarchou/dydx-trading-bot
IMAGE_TAG ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo latest)

# Default target - show help when running just 'make'
help: ## Show this help message
	@$(PYTHON) scripts/make_tools.py help $(firstword $(MAKEFILE_LIST))

completion-powershell: ## Show how to enable Make target completion in PowerShell
	@$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/powershell/MakeCompletion.ps1 -ShowInstructions

install-completion-powershell: ## Install Make target completion in the PowerShell profile
	@$(POWERSHELL) -NoProfile -ExecutionPolicy Bypass -File scripts/powershell/MakeCompletion.ps1 -Install

windows-check: ## Check the Windows shell and PowerShell completion prerequisites
	@$(PYTHON) scripts/make_tools.py windows-check "$(WINDOWS_BASH)"

# ============================================================================
# ENVIRONMENT & SETUP
# ============================================================================

setup: ## Create Python virtual environment
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip setuptools wheel
	@echo "[OK] Virtual environment created at .venv/"
	@echo "[NOTE] Activate with: source .venv/bin/activate"

install: ## Install all dependencies including backend package
	@echo "Installing dependencies per service (backend/frontend/bot)..."
	cd backend && go mod download
	cd frontend && npm install
	cd bot && .venv/bin/pip install --upgrade pip setuptools wheel && .venv/bin/pip install -r requirements.txt
	@echo "[OK] Service dependencies installed"

config: ## Deprecated legacy config target (bot uses runtime config under bot/)
	@echo "[WARNING] 'make config' is deprecated for this monorepo layout."
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
	@echo "[WARNING] env-setup is deprecated."
	@echo "Use make dev-config / make prod-config, then make dev / make prod."

env: ## Show deprecation warning for .env
	@echo "[WARNING] repo-root .env is deprecated."
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
	@echo "[OK] Build artifacts cleaned"

# ============================================================================
# BOT COMMANDS
# ============================================================================

run: ## Run bot in foreground
	.venv/bin/python bot/main.py

backend-run: api-run ## Start bot API server (alias for api-run)

api-run: ## Start bot API server on port 8889
	.venv/bin/python -m uvicorn bot.src.api.server:app --reload --host 0.0.0.0 --port 8889

worker-run: ## Deprecated alias (kept for compatibility)
	@echo "[WARNING] 'make worker-run' is deprecated; use 'make api-run' instead."
	@$(MAKE) api-run

celery-worker: ## Start Celery worker for durable backtests
	# On macOS, use spawn instead of fork to avoid Objective-C runtime crashes
	cd bot && MP_START_METHOD=$${MP_START_METHOD:-spawn} PYTHON_MULTIPROCESSING_START_METHOD=$${MP_START_METHOD:-spawn} .venv/bin/celery -A src.infrastructure.workers.celery_app:celery_app worker --loglevel=$${CELERY_LOG_LEVEL:-INFO} --queues=$${CELERY_QUEUES:-backtests,default,high_priority,scheduled} --concurrency=$${CELERY_CONCURRENCY:-1}

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
		echo "[ERROR] scripts/manage_bot.sh not found"; \
		exit 1; \
	fi
	bash scripts/manage_bot.sh start
	@echo "[OK] Bot started in background"

stop: ## Stop background bot
	@if [ ! -f scripts/manage_bot.sh ]; then \
		echo "[ERROR] scripts/manage_bot.sh not found"; \
		exit 1; \
	fi
	bash scripts/manage_bot.sh stop
	@echo "[OK] Bot stopped"

restart: ## Restart background bot
	@if [ ! -f scripts/manage_bot.sh ]; then \
		echo "[ERROR] scripts/manage_bot.sh not found"; \
		exit 1; \
	fi
	bash scripts/manage_bot.sh restart
	@echo "[OK] Bot restarted"

status: ## Check if bot is running
	@if [ ! -f scripts/manage_bot.sh ]; then \
		echo "[ERROR] scripts/manage_bot.sh not found"; \
		exit 1; \
	fi
	bash scripts/manage_bot.sh status

logs: ## View recent bot logs
	@if [ -f bot_logs.txt ]; then \
		tail -100 bot_logs.txt; \
	else \
		echo "[ERROR] bot_logs.txt not found"; \
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
	@echo "[OK] Docker image built"

docker-run: ## Run bot in Docker container
	docker run -it --rm \
		-v $(PWD)/app:/app/app \
		-v $(PWD)/.env:/.env \
		--name dydx-bot \
		dydx-trading-bot:latest

docker-stop: ## Stop Docker container
	docker stop dydx-bot || true
	@echo "[OK] Docker container stopped"

docker-logs: ## View Docker container logs
	docker logs -f dydx-bot || echo "Container not running"

docker-shell: ## Open shell in running Docker container
	docker exec -it dydx-bot /bin/bash

docker-dev: ## Build development Docker image with live code mounting
	docker build -f Dockerfile.dev -t dydx-trading-bot:dev .
	@echo "[OK] Development Docker image built"

docker-clean: ## Remove Docker image and containers
	docker stop dydx-bot || true
	docker rm dydx-bot || true
	docker rmi dydx-trading-bot:latest dydx-trading-bot:dev || true
	@echo "[OK] Docker resources cleaned"

docker-up: ## Start with Docker Compose
	docker-compose up -d
	@echo "[OK] Services started with Docker Compose"

docker-down: ## Stop Docker Compose services
	docker-compose down
	@echo "[OK] Docker Compose services stopped"

docker-up-logging: ## Start full observability stack (Loki + Grafana)
	docker-compose -f docker-compose.full-stack.yml up -d
	@echo "[OK] Logging stack started"
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "Loki: http://localhost:3100"

docker-down-logging: ## Stop logging stack
	docker-compose -f docker-compose.full-stack.yml down
	@echo "[OK] Logging stack stopped"

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
	@echo "[OK] Migration created in alembic/versions/"

migration-up: ## Apply all pending migrations
	.venv/bin/alembic upgrade head
	@echo "[OK] Database upgraded to latest migration"

migration-down: ## Rollback N migrations: make migration-down N=1
	@if [ -z "$(N)" ]; then \
		echo "Usage: make migration-down N=1"; \
		exit 1; \
	fi
	.venv/bin/alembic downgrade -$(N)
	@echo "[OK] Rolled back $(N) migration(s)"

migration-verify: ## Show current migration & history
	@echo "==========================================================="
	@echo "CURRENT MIGRATION:"
	@echo "==========================================================="
	@.venv/bin/alembic current
	@echo ""
	@echo "==========================================================="
	@echo "MIGRATION HISTORY:"
	@echo "==========================================================="
	@.venv/bin/alembic history --verbose
	@echo "[OK] Verification complete"

db-init-schema: ## Initialize database schema (creates all tables)
	.venv/bin/python scripts/init_database.py --init
	@echo "[OK] Database schema initialized"

db-verify-schema: ## Verify database schema integrity
	.venv/bin/python scripts/init_database.py --verify

db-reset: ## Reset database (drop and recreate all tables) - USE WITH CAUTION!
	.venv/bin/python scripts/init_database.py --reset

# Legacy/Advanced (kept for reference)
db-init: ## Initialize Alembic migrations (one-time setup)
	.venv/bin/alembic init alembic
	@echo "[OK] Alembic initialized"

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

db-up: ## Deprecated alias: start the shared local infrastructure stack
	@echo "[WARNING] db-up is deprecated; using make infra-up"
	@$(MAKE) infra-up

db-status: ## Deprecated alias: show the shared local infrastructure status
	@echo "[WARNING] db-status is deprecated; using make infra-ps"
	@$(MAKE) infra-ps

db-down: ## Deprecated alias: stop the shared local infrastructure stack
	@echo "[WARNING] db-down is deprecated; using make infra-down"
	@$(MAKE) infra-down

infra-up: ## Start shared infra only (PostgreSQL, Valkey, NATS, ClickHouse, MinIO) for local service development
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(INFRA_COMPOSE_FILE)" ]; then \
			echo "[ERROR] Missing $(INFRA_COMPOSE_FILE)."; \
			echo "   Use make dev-infra (docker-run based local infra) as fallback."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(INFRA_COMPOSE_FILE) up -d --remove-orphans; \
		echo ""; \
		echo "[OK] Infrastructure started:"; \
		echo "   PostgreSQL:       localhost:5432"; \
		echo "   Valkey (Redis):   localhost:6379"; \
		echo "   NATS JetStream:   localhost:4222 (monitoring: 8222)"; \
		echo "   ClickHouse:       localhost:8123"; \
		echo "   MinIO API:        localhost:9010"; \
		echo "   MinIO Console:    http://localhost:9011"; \
		echo ""; \
		echo "Services will auto-discover these via environment variables."; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot start infra"; \
		exit 0; \
	fi

infra-down: ## Stop shared infra only (PostgreSQL, Valkey, NATS, ClickHouse, MinIO)
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(INFRA_COMPOSE_FILE)" ]; then \
			echo "[ERROR] Missing $(INFRA_COMPOSE_FILE). Nothing to stop via infra commands."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(INFRA_COMPOSE_FILE) down --remove-orphans; \
		echo "[OK] Infrastructure stopped"; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot stop infra"; \
		exit 0; \
	fi

infra-logs: ## Follow logs for shared infra services (PostgreSQL, Valkey, NATS, ClickHouse, MinIO)
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(INFRA_COMPOSE_FILE)" ]; then \
			echo "[ERROR] Missing $(INFRA_COMPOSE_FILE)."; \
			echo "   Tip: use docker logs for containers (dydx-postgresql, dydx-valkey, dydx-nats, dydx-clickhouse, dydx-minio)."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(INFRA_COMPOSE_FILE) logs -f --tail=100; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot fetch infra logs"; \
		exit 0; \
	fi

infra-ps: ## Show status for shared infra services (PostgreSQL, Valkey, NATS, ClickHouse, MinIO)
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(INFRA_COMPOSE_FILE)" ]; then \
			echo "[ERROR] Missing $(INFRA_COMPOSE_FILE)."; \
			echo "   Tip: use make dev-infra and inspect with docker ps | grep dydx-."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(INFRA_COMPOSE_FILE) ps; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot fetch infra status"; \
		exit 0; \
	fi

# ============================================================================
# APPLE SILICON (M1/M2/M3) SUPPORT
# ============================================================================

infra-up-arm64: ## Start ARM64 infrastructure (Apple Silicon) - PostgreSQL, Valkey, NATS, ClickHouse, MinIO
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(INFRA_COMPOSE_FILE_ARM64)" ]; then \
			echo "[ERROR] Missing $(INFRA_COMPOSE_FILE_ARM64)."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(INFRA_COMPOSE_FILE_ARM64) up -d --remove-orphans; \
		echo ""; \
		echo "[OK] ARM64 Infrastructure started:"; \
		echo "   PostgreSQL:       localhost:5432"; \
		echo "   Valkey (Redis):   localhost:6379"; \
		echo "   NATS JetStream:   localhost:4222 (monitoring: 8222)"; \
		echo "   ClickHouse:       localhost:8123"; \
		echo "   MinIO API:        localhost:9010"; \
		echo "   MinIO Console:    http://localhost:9011"; \
		echo ""; \
		echo "Services will auto-discover these via environment variables."; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot start ARM64 infra"; \
		exit 0; \
	fi

infra-down-arm64: ## Stop ARM64 infrastructure
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(INFRA_COMPOSE_FILE_ARM64)" ]; then \
			echo "[ERROR] Missing $(INFRA_COMPOSE_FILE_ARM64). Nothing to stop via ARM64 infra commands."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(INFRA_COMPOSE_FILE_ARM64) down --remove-orphans; \
		echo "[OK] ARM64 Infrastructure stopped"; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot stop ARM64 infra"; \
		exit 0; \
	fi

infra-logs-arm64: ## Follow logs for ARM64 infrastructure services
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(INFRA_COMPOSE_FILE_ARM64)" ]; then \
			echo "[ERROR] Missing $(INFRA_COMPOSE_FILE_ARM64)."; \
			echo "   Tip: use docker logs for containers (dydx-postgresql-arm64, dydx-valkey-arm64, etc.)"; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(INFRA_COMPOSE_FILE_ARM64) logs -f --tail=100; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot fetch ARM64 infra logs"; \
		exit 0; \
	fi

infra-ps-arm64: ## Show status for ARM64 infrastructure services
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(INFRA_COMPOSE_FILE_ARM64)" ]; then \
			echo "[ERROR] Missing $(INFRA_COMPOSE_FILE_ARM64)."; \
			echo "   Tip: use docker ps | grep dydx-.-arm64"; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(INFRA_COMPOSE_FILE_ARM64) ps; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot fetch ARM64 infra status"; \
		exit 0; \
	fi

stack-up-dev-arm64: ## Start ARM64 full integration stack (frontend + backend + bot + infrastructure)
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(STACK_COMPOSE_FILE_ARM64)" ]; then \
			echo "[ERROR] Missing $(STACK_COMPOSE_FILE_ARM64)."; \
			exit 1; \
		fi; \
		set -e; \
		python3 scripts/validate_stack_env.py --environment development; \
		APP_CONFIG_ENV=development docker compose -f $(STACK_COMPOSE_FILE_ARM64) --profile dev up -d --remove-orphans; \
		echo "[OK] ARM64 Dev stack started (frontend:5173, backend:8888, bot-api:8889, worker enabled)"; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot start ARM64 stack"; \
		exit 0; \
	fi

stack-up-prod-arm64: ## Start ARM64 production-like stack
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(STACK_COMPOSE_FILE_ARM64)" ]; then \
			echo "[ERROR] Missing $(STACK_COMPOSE_FILE_ARM64)."; \
			exit 1; \
		fi; \
		set -e; \
		python3 scripts/validate_stack_env.py --environment production --strict-prod; \
		APP_CONFIG_ENV=production docker compose -f $(STACK_COMPOSE_FILE_ARM64) --profile prod up -d --remove-orphans; \
		echo "[OK] ARM64 Prod-like stack started (proxy:8080, api internal, frontend internal)"; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot start ARM64 stack"; \
		exit 0; \
	fi

stack-up-integration-arm64: stack-up-dev-arm64 ## Alias for ARM64 full integration stack

stack-down-arm64: ## Stop ARM64 split app stack
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(STACK_COMPOSE_FILE_ARM64)" ]; then \
			echo "[ERROR] Missing $(STACK_COMPOSE_FILE_ARM64). Nothing to stop via ARM64 stack commands."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(STACK_COMPOSE_FILE_ARM64) --profile dev --profile prod down --remove-orphans; \
		echo "[OK] ARM64 Stack stopped"; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot stop ARM64 stack"; \
		exit 0; \
	fi

stack-logs-arm64: ## Follow logs for ARM64 split app stack
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(STACK_COMPOSE_FILE_ARM64)" ]; then \
			echo "[ERROR] Missing $(STACK_COMPOSE_FILE_ARM64)."; \
			echo "   Tip: use docker logs for ARM64 containers"; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(STACK_COMPOSE_FILE_ARM64) logs -f --tail=100; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot fetch ARM64 logs"; \
		exit 0; \
	fi

stack-ps-arm64: ## Show status for ARM64 split app stack services
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(STACK_COMPOSE_FILE_ARM64)" ]; then \
			echo "[ERROR] Missing $(STACK_COMPOSE_FILE_ARM64)."; \
			echo "   Tip: use docker ps | grep dydx-.-arm64"; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(STACK_COMPOSE_FILE_ARM64) ps; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot fetch ARM64 service status"; \
		exit 0; \
	fi

images-build-arm64: ## Build all ARM64 service images locally
	IMAGE_REGISTRY=$(IMAGE_REGISTRY) IMAGE_TAG=$(IMAGE_TAG) PUSH=false ALSO_LATEST=false PLATFORM=linux/arm64 bash scripts/build_all_service_images.sh

images-build-latest-arm64: ## Build all ARM64 service images with :latest tag locally
	IMAGE_REGISTRY=$(IMAGE_REGISTRY) IMAGE_TAG=$(IMAGE_TAG) PUSH=false ALSO_LATEST=true PLATFORM=linux/arm64 bash scripts/build_all_service_images.sh

images-push-arm64: ## Build and push all ARM64 service images
	IMAGE_REGISTRY=$(IMAGE_REGISTRY) IMAGE_TAG=$(IMAGE_TAG) PUSH=true ALSO_LATEST=false PLATFORM=linux/arm64 bash scripts/build_all_service_images.sh

images-push-latest-arm64: ## Build and push all ARM64 service images with :latest tag
	IMAGE_REGISTRY=$(IMAGE_REGISTRY) IMAGE_TAG=$(IMAGE_TAG) PUSH=true ALSO_LATEST=true PLATFORM=linux/arm64 bash scripts/build_all_service_images.sh

check-no-legacy-db: ## Fail if active code/config contains legacy database patterns
	python3 scripts/check_no_legacy_database.py

dev-infra: ## Deprecated alias: start the shared local infrastructure stack
	@echo "[WARNING] dev-infra is deprecated; using make infra-up"
	@$(MAKE) infra-up

dev-infra-down: ## Deprecated alias: stop the shared local infrastructure stack
	@echo "[WARNING] dev-infra-down is deprecated; using make infra-down"
	@$(MAKE) infra-down

stack-up-dev: ## Start full integration stack (frontend + backend + bot + PostgreSQL + Valkey + NATS + ClickHouse + MinIO)
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(STACK_COMPOSE_FILE)" ]; then \
			echo "[ERROR] Missing $(STACK_COMPOSE_FILE)."; \
			echo "   Use service-first workflow instead: make infra-up, then run backend/frontend/bot individually."; \
			exit 1; \
		fi; \
		set -e; \
		python3 scripts/validate_stack_env.py --environment development; \
		APP_CONFIG_ENV=development docker compose -f $(STACK_COMPOSE_FILE) --profile dev up -d --remove-orphans; \
		echo "[OK] Dev stack started (frontend:5173, backend:8888, bot-api:8889, worker enabled)"; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot start stack"; \
		exit 0; \
	fi

stack-up-prod: ## Start production-like stack (frontend + backend + bot + PostgreSQL + Valkey + NATS + ClickHouse + MinIO)
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(STACK_COMPOSE_FILE)" ]; then \
			echo "[ERROR] Missing $(STACK_COMPOSE_FILE)."; \
			echo "   Use service-first workflow instead: make infra-up, then run backend/frontend/bot individually."; \
			exit 1; \
		fi; \
		set -e; \
		python3 scripts/validate_stack_env.py --environment production --strict-prod; \
		APP_CONFIG_ENV=production docker compose -f $(STACK_COMPOSE_FILE) --profile prod up -d --remove-orphans; \
		echo "[OK] Prod-like stack started (proxy:8080, api internal, frontend internal)"; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot start stack"; \
		exit 0; \
	fi

stack-up-integration: stack-up-dev ## Alias for full integration stack in dev profile

stack-down: ## Stop split app stack
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(STACK_COMPOSE_FILE)" ]; then \
			echo "[ERROR] Missing $(STACK_COMPOSE_FILE). Nothing to stop via stack commands."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(STACK_COMPOSE_FILE) --profile dev --profile prod down --remove-orphans; \
		echo "[OK] Stack stopped"; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot stop stack"; \
		exit 0; \
	fi

stack-logs: ## Follow logs for split app stack
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(STACK_COMPOSE_FILE)" ]; then \
			echo "[ERROR] Missing $(STACK_COMPOSE_FILE)."; \
			echo "   Tip: use make infra-logs and service-level logs instead."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(STACK_COMPOSE_FILE) logs -f --tail=100; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot fetch logs"; \
		exit 0; \
	fi

stack-ps: ## Show status for split app stack services
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		if [ ! -f "$(STACK_COMPOSE_FILE)" ]; then \
			echo "[ERROR] Missing $(STACK_COMPOSE_FILE)."; \
			echo "   Tip: use make infra-ps for infra status and service-specific run commands."; \
			exit 1; \
		fi; \
		APP_CONFIG_ENV=$(MODE) docker compose -f $(STACK_COMPOSE_FILE) ps; \
	else \
		echo "[WARNING] Docker daemon unavailable; cannot fetch service status"; \
		exit 0; \
	fi

stack-env: ## Deprecated: stack reads structured JSON config directly
	@echo "[WARNING] stack-env is deprecated."
	@echo "Use make dev-config or make prod-config instead."

stack-env-check: ## Validate required variables in structured config
	python3 scripts/validate_stack_env.py --environment $(MODE)

stack-env-check-prod: ## Validate production structured config with strict rules
	python3 scripts/validate_stack_env.py --environment production --strict-prod

.DEFAULT_GOAL := help
dev: ## Prepare repo-root run.json from the encrypted development profile
	@python3 scripts/render_run_config.py --environment development --output run.json
	@python3 scripts/validate_stack_env.py --environment development
	@echo "[OK] run.json is ready for local development"

prod: ## Prepare repo-root run.json from the encrypted production profile
	@python3 scripts/render_run_config.py --environment production --output run.json
	@python3 scripts/validate_stack_env.py --environment production --strict-prod
	@echo "[OK] run.json is ready for production-like startup"
