# =============================================================================
# Makefile for dYdX Trading Bot - Docker Operations
# =============================================================================
# Comprehensive Docker management commands for development and production
# =============================================================================

# Variables
DOCKER_DIR := docker
COMPOSE_FILE := $(DOCKER_DIR)/docker-compose.yml
ENV_FILE := $(DOCKER_DIR)/.env
PROJECT_NAME := dydx-trading-bot
DOCKER_REPO := dydx-trading-bot
VERSION := $(shell git describe --tags --always --dirty 2>/dev/null || echo "latest")

# Detect OS and set appropriate paths
# For Windows (PowerShell/cmd), we need to explicitly use bash/sh
# Check if we're on Windows by looking for typical Windows environment variables
ifdef COMSPEC
    # We're on Windows (cmd.exe or PowerShell sets COMSPEC)
    # Use Windows path with escaped spaces for native Make
    SHELL := C:/Program\ Files/Git/usr/bin/sh.exe
    export SHELL
    VENV_PYTHON := .venv/Scripts/python.exe
else
    # Try uname for Unix-like systems (including MSYS2 bash)
    UNAME := $(shell uname -s 2>/dev/null)
    ifeq ($(findstring MINGW,$(UNAME)),MINGW)
        # MSYS2/MinGW - use Scripts directory
        SHELL := C:/Program\ Files/Git/usr/bin/sh.exe
        export SHELL
        VENV_PYTHON := .venv/Scripts/python.exe
    else ifeq ($(findstring CYGWIN,$(UNAME)),CYGWIN)
        # Cygwin also uses Scripts directory
        SHELL := C:/Program\ Files/Git/usr/bin/sh.exe
        export SHELL
        VENV_PYTHON := .venv/Scripts/python.exe
    else ifeq ($(UNAME),)
        # Empty UNAME - assume Unix-like
        VENV_PYTHON := .venv/bin/python
    else
        # Unix-like systems use bin directory
        VENV_PYTHON := .venv/bin/python
    endif
endif

MODE ?= development

# Reusable helper for local Python commands that must run via project venv.
# Usage in recipes: $(call run-venv-python,<args>)
define run-venv-python
	@$(VENV_PYTHON) $(1)
endef

# Reusable helper for local Python commands that need inline env prefixes.
# Usage in recipes: $(call run-venv-python-env,<ENV_VARS>,<args>)
define run-venv-python-env
	@$(1) $(VENV_PYTHON) $(2)
endef

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
MAGENTA := \033[0;35m
CYAN := \033[0;36m
WHITE := \033[0;37m
RESET := \033[0m

# Default target
.DEFAULT_GOAL := help

# =============================================================================
# HELP AND INFORMATION
# =============================================================================

.PHONY: help
help: ## Show this help message
	@echo "$(CYAN)============================================================$(RESET)"
	@echo "$(CYAN)🐳 dYdX Trading Bot - Docker Commands$(RESET)"
	@echo "$(CYAN)============================================================$(RESET)"
	@echo ""
	@echo "$(GREEN)📦 SETUP COMMANDS:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E "(setup|install|init)" | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)🚀 DEVELOPMENT COMMANDS:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E "(dev|development|build|test)" | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)🏭 PRODUCTION COMMANDS:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E "(prod|production|deploy)" | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)🔧 MANAGEMENT COMMANDS:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E "(logs|status|clean|stop|restart)" | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)🔒 SECURITY COMMANDS:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E "(ssl|auth|security|backup)" | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)============================================================$(RESET)"

.PHONY: info
info: ## Show project information and status
	@echo "$(CYAN)============================================================$(RESET)"
	@echo "$(CYAN)📋 dYdX Trading Bot - Project Information$(RESET)"
	@echo "$(CYAN)============================================================$(RESET)"
	@echo "$(GREEN)Project:$(RESET)       $(PROJECT_NAME)"
	@echo "$(GREEN)Version:$(RESET)       $(VERSION)"
	@echo "$(GREEN)Docker Dir:$(RESET)    $(DOCKER_DIR)"
	@echo "$(GREEN)Compose File:$(RESET)  $(COMPOSE_FILE)"
	@echo "$(GREEN)Environment:$(RESET)   $(ENV_FILE)"
	@echo ""
	@echo "$(GREEN)🐳 Docker Status:$(RESET)"
	@docker version --format "  Docker:        {{.Server.Version}}" 2>/dev/null || echo "  Docker:        Not available"
	@docker-compose version --short 2>/dev/null | sed 's/^/  Compose:       /' || echo "  Compose:       Not available"
	@echo ""
	@echo "$(GREEN)📦 Running Containers:$(RESET)"
	@docker ps --filter "name=$(PROJECT_NAME)" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "  No containers running"
	@echo ""
	@echo "$(CYAN)============================================================$(RESET)"

# =============================================================================
# SETUP COMMANDS
# =============================================================================

.PHONY: setup
setup: ## Setup development environment (run this first)
	@echo "$(CYAN)🔧 Setting up dYdX Trading Bot development environment...$(RESET)"
	@$(DOCKER_DIR)/setup-dev.sh

.PHONY: init-env
init-env: ## Initialize environment file from template
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "$(YELLOW)📝 Creating environment file...$(RESET)"; \
		cp $(DOCKER_DIR)/.env.docker $(ENV_FILE); \
		echo "$(GREEN)✅ Environment file created at $(ENV_FILE)$(RESET)"; \
		echo "$(YELLOW)⚠️  Please edit $(ENV_FILE) with your configuration$(RESET)"; \
	else \
		echo "$(GREEN)✅ Environment file already exists$(RESET)"; \
	fi

.PHONY: dev-env
dev-env: ## Deprecated: bot now reads config/profiles directly
	@echo "$(YELLOW)⚠ dev-env is deprecated. Use make dev-config or make prod-config from the repo root.$(RESET)"

.PHONY: init-ssl
init-ssl: ## Generate SSL certificates for development
	@echo "$(CYAN)🔐 Generating SSL certificates...$(RESET)"
	@cd $(DOCKER_DIR)/ssl && chmod +x generate-ssl.sh && ./generate-ssl.sh

.PHONY: init-auth
init-auth: ## Initialize authentication database
	@echo "$(CYAN)🔑 Initializing authentication database...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec bot-api python init_auth_db.py

.PHONY: credentials-keygen
credentials-keygen: ## Generate a 32-byte key for encrypting bot_instances credentials
	@echo "$(CYAN)🔑 Generating credential encryption key (32 bytes)...$(RESET)"
	@KEY=$$(openssl rand -base64 32) ; \
	echo "$(GREEN)Base64 key (set as BOT_CREDENTIALS_ENCRYPTION_KEY):$(RESET)" ; \
	echo "$$KEY" ; \
	echo "$(YELLOW)Or write the raw 32 bytes to a file and point BOT_CREDENTIALS_ENCRYPTION_KEY_FILE at it.$(RESET)" ; \
	echo "$(YELLOW)Store this key securely; losing it makes sealed credentials unrecoverable.$(RESET)"

.PHONY: config-keygen
config-keygen: ## Generate a 32-byte key for structured config-file encryption (.configkey.bin)
	@echo "$(CYAN)🔑 Generating structured-config encryption key (.configkey.bin)...$(RESET)"
	@KEYFILE=$$(pwd)/.configkey.bin ; \
	if [ -f "$$KEYFILE" ]; then \
		echo "$(YELLOW)⚠️  $$KEYFILE already exists; leaving it untouched.$(RESET)" ; \
	else \
		dd if=/dev/urandom of="$$KEYFILE" bs=32 count=1 status=none ; \
		chmod 600 "$$KEYFILE" ; \
		echo "$(GREEN)✅ Wrote 32-byte key to $$KEYFILE (chmod 600)$(RESET)" ; \
		echo "$(YELLOW)Set APP_CONFIG_KEY_FILE to override this path.$(RESET)" ; \
	fi

.PHONY: encrypt-bot-credentials
encrypt-bot-credentials: ## Backfill-encrypt existing bot_instances credentials (use --dry-run first)
	@echo "$(CYAN)🔒 Running credential encryption backfill...$(RESET)"
	@$(call run-venv-python,scripts/encrypt_bot_credentials.py $(ARGS))

.PHONY: ensure-venv
ensure-venv: ## Ensure local virtual environment exists
	@if [ -x "$(VENV_PYTHON)" ]; then \
		echo "$(GREEN)✅ Using interpreter: $(VENV_PYTHON)$(RESET)"; \
	else \
		echo "$(RED)❌ Virtual environment interpreter not found at $(VENV_PYTHON)$(RESET)"; \
		echo "$(YELLOW)Setup: python -m venv .venv && .venv\Scripts\python -m pip install -r requirements.txt$(RESET)"; \
		exit 1; \
	fi

# =============================================================================
# BUILD COMMANDS
# =============================================================================

.PHONY: build
build: ## Build Docker images
	@echo "$(CYAN)🏗️  Building Docker images...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) build

.PHONY: build-dev
build-dev: ## Build development Docker images
	@echo "$(CYAN)🏗️  Building development Docker images...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) build --target development

.PHONY: build-prod
build-prod: ## Build production Docker images
	@echo "$(CYAN)🏗️  Building production Docker images...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) build --target production

.PHONY: build-no-cache
build-no-cache: ## Build Docker images without cache
	@echo "$(CYAN)🏗️  Building Docker images (no cache)...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) build --no-cache

# =============================================================================
# DEVELOPMENT COMMANDS
# =============================================================================

.PHONY: dev
dev: ## Start development environment (with hot reload)
	@echo "$(CYAN)🚀 Starting development environment...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up --build

.PHONY: dev-api
dev-api: ensure-venv ## Start bot API server locally with Python (port 8889)
	@echo "$(CYAN)🚀 Starting bot API server on http://0.0.0.0:8889$(RESET)"
	$(call run-venv-python,-m uvicorn src.api.server:app --host 0.0.0.0 --port 8889 --reload)

.PHONY: local-api
local-api: ensure-venv ## Start canonical local API server (port 8889)
	@echo "$(CYAN)🚀 Starting local API server on http://0.0.0.0:8889$(RESET)"
	$(call run-venv-python-env,BOT_API_RELOAD=false,src/api/start_api.py)

.PHONY: local-api-reload
local-api-reload: ensure-venv ## Start local API server with hot reload (dev/debug only)
	@echo "$(CYAN)🚀 Starting local API server with reload on http://0.0.0.0:8889$(RESET)"
	$(call run-venv-python-env,BOT_API_RELOAD=true,src/api/start_api.py)

.PHONY: local-bot
local-bot: ensure-venv ## Start trading bot runtime locally
	@echo "$(CYAN)🚀 Starting local trading bot runtime$(RESET)"
	$(call run-venv-python,main.py)

.PHONY: local-worker
local-worker: ensure-venv ## Start Celery worker locally for backtests/runtime jobs
	@echo "$(CYAN)👷 Starting local Celery worker for strategy backtests$(RESET)"
	# On macOS, use spawn instead of fork to avoid Objective-C runtime crashes
	MP_START_METHOD=$${MP_START_METHOD:-spawn} CELERY_BROKER_URL=$${CELERY_BROKER_URL:-$${REDIS_URL:-$${VALKEY_URL:-redis://localhost:6379/1}}} CELERY_RESULT_BACKEND=$${CELERY_RESULT_BACKEND:-$${REDIS_RESULT_BACKEND_URL:-$${VALKEY_RESULT_BACKEND_URL:-redis://localhost:6379/2}}} CELERY_QUEUES=$${CELERY_QUEUES:-backtests,default,high_priority,scheduled} PYTHON_MULTIPROCESSING_START_METHOD=$${MP_START_METHOD:-spawn} $(VENV_PYTHON) -m celery -A src.infrastructure.workers.celery_app:celery_app worker -l info -Q $${CELERY_QUEUES:-backtests,default,high_priority,scheduled} -E

.PHONY: dev-detached
dev-detached: ## Start development environment in background
	@echo "$(CYAN)🚀 Starting development environment (detached)...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up --build -d
	@echo "$(GREEN)✅ Development environment started$(RESET)"
	@$(MAKE) status

.PHONY: test
test: ## Run tests in Docker container
	@echo "$(CYAN)🧪 Running tests...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec bot-api python -m pytest

.PHONY: test-auth
test-auth: ## Test authentication system
	@echo "$(CYAN)🔐 Testing authentication system...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec bot-api python test_api_database_integration.py

.PHONY: test-cov
test-cov: ensure-venv ## Run tests with coverage (terminal report, missing lines shown)
	@echo "$(CYAN)🧪 Running tests with coverage...$(RESET)"
	$(call run-venv-python-env,PYTHONPATH=$(CURDIR),-m pytest tests/ --cov=src --cov-report=term-missing)

.PHONY: test-cov-html
test-cov-html: ensure-venv ## Run tests with coverage and write HTML report (htmlcov/index.html)
	@echo "$(CYAN)🧪 Running tests with coverage (HTML)...$(RESET)"
	$(call run-venv-python-env,PYTHONPATH=$(CURDIR),-m pytest tests/ --cov=src --cov-report=html --cov-report=term-missing)
	@echo "$(GREEN)📄 HTML report written to htmlcov/index.html$(RESET)"

.PHONY: install-hooks
install-hooks: ensure-venv ## Install git pre-commit hooks (run once after clone)
	@echo "$(CYAN)🪝 Installing pre-commit hooks...$(RESET)"
	$(VENV_PYTHON) -m pre_commit install
	@echo "$(GREEN)✅ Pre-commit hooks installed — they run on every commit.$(RESET)"
	@echo "$(YELLOW)   Requires bot/.venv active at commit time. Run '$(CYAN)make hooks-run$(RESET)$(YELLOW)' to check all files.$(RESET)"

.PHONY: hooks-run
hooks-run: ensure-venv ## Run pre-commit on all files (manual check)
	$(VENV_PYTHON) -m pre_commit run --all-files

.PHONY: hooks-update
hooks-update: ensure-venv ## Update pre-commit hook repos to their latest tags
	$(VENV_PYTHON) -m pre_commit autoupdate

# =============================================================================
# PRODUCTION COMMANDS
# =============================================================================

.PHONY: prod
prod: ## Start production environment
	@echo "$(CYAN)🏭 Starting production environment...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up -d
	@echo "$(GREEN)✅ Production environment started$(RESET)"
	@$(MAKE) status

.PHONY: deploy
deploy: build-prod prod ## Build and deploy production environment
	@echo "$(GREEN)🚀 Deployment complete!$(RESET)"

# =============================================================================
# MANAGEMENT COMMANDS
# =============================================================================

.PHONY: start
start: ## Start all services
	@echo "$(CYAN)▶️  Starting services...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) start

.PHONY: stop
stop: ## Stop all services
	@echo "$(CYAN)⏹️  Stopping services...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) stop

.PHONY: restart
restart: ## Restart all services
	@echo "$(CYAN)🔄 Restarting services...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) restart

.PHONY: down
down: ## Stop and remove containers
	@echo "$(CYAN)⬇️  Stopping and removing containers...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down

.PHONY: status
status: ## Show container status
	@echo "$(CYAN)📊 Container Status:$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) ps

.PHONY: logs
logs: ## Show logs for all services
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs

.PHONY: logs-api
logs-api: ## Show API server logs
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f bot-api

.PHONY: logs-db
logs-db: ## Show database logs
	@docker compose -f ../docker-compose.infra.yml logs -f postgresql

.PHONY: logs-nginx
logs-nginx: ## Show Nginx logs
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f nginx

# =============================================================================
# DATABASE COMMANDS
# =============================================================================

.PHONY: db-shell
db-shell: ## Connect to database shell
	@echo "$(CYAN)🗄️  Connecting to database...$(RESET)"
	@docker exec -it dydx-postgresql psql -U $${POSTGRES_USER:-dydx_bot} -d $${POSTGRES_DB:-dydx_bot}

.PHONY: db-backup
db-backup: ## Backup database
	@echo "$(CYAN)💾 Creating database backup...$(RESET)"
	@mkdir -p backups
	@docker exec dydx-postgresql pg_dump -U $${POSTGRES_USER:-dydx_bot} $${POSTGRES_DB:-dydx_bot} | gzip > backups/backup_$(shell date +%Y%m%d_%H%M%S).sql.gz
	@echo "$(GREEN)✅ Database backup created in backups/$(RESET)"

.PHONY: db-reset
db-reset: ## Reset database (WARNING: deletes all data)
	@echo "$(YELLOW)⚠️  db-reset no longer manages a bot-local database container.$(RESET)"
	@echo "Use the repo-root infrastructure workflow instead:"
	@echo "  make infra-down"
	@echo "  docker volume rm dydx-trading-bot_postgresql_data  # if a full local reset is intentional"
	@echo "  make infra-up"

# =============================================================================
# SHELL AND DEBUGGING COMMANDS
# =============================================================================

.PHONY: shell
shell: ## Open shell in API container
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec bot-api /bin/bash

.PHONY: shell-nginx
shell-nginx: ## Open shell in Nginx container
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec nginx /bin/sh

.PHONY: shell-db
shell-db: ## Open shell in database container
	@docker exec -it dydx-postgresql /bin/sh

# =============================================================================
# SECURITY COMMANDS
# =============================================================================

.PHONY: update-ssl
update-ssl: ## Update SSL certificates
	@echo "$(CYAN)🔐 Updating SSL certificates...$(RESET)"
	@cd $(DOCKER_DIR)/ssl && ./generate-ssl.sh

# =============================================================================
# MONITORING COMMANDS
# =============================================================================

.PHONY: health
health: ## Check health of all services
	@echo "$(CYAN)🏥 Checking service health...$(RESET)"
	@echo ""
	@echo "$(GREEN)API Server:$(RESET)"
	@curl -s http://localhost:8889/health | jq '.' 2>/dev/null || echo "  ❌ Not accessible"
	@echo ""
	@echo "$(GREEN)Authentication:$(RESET)"
	@curl -s http://localhost:8889/api/v1/auth/health | jq '.' 2>/dev/null || echo "  ❌ Not accessible"
	@echo ""
	@echo "$(GREEN)Database:$(RESET)"
	@docker exec dydx-postgresql pg_isready -U $${POSTGRES_USER:-dydx_bot} -d $${POSTGRES_DB:-dydx_bot} >/dev/null 2>&1 && echo "  ✅ Healthy" || echo "  ❌ Not healthy"
	@echo ""

# =============================================================================
# CLEANUP COMMANDS
# =============================================================================

.PHONY: clean
clean: ## Clean up Docker resources (containers, networks)
	@echo "$(CYAN)🧹 Cleaning up Docker resources...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down --remove-orphans
	@docker system prune -f

.PHONY: clean-all
clean-all: ## Clean up all Docker resources (including images and volumes)
	@echo "$(RED)⚠️  This will remove ALL Docker resources for this project!$(RESET)"
	@read -p "Are you sure? (y/N): " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) down -v --remove-orphans; \
		docker rmi $(shell docker images -q $(PROJECT_NAME)*) 2>/dev/null || true; \
		docker system prune -af; \
		echo "$(GREEN)✅ Cleanup complete$(RESET)"; \
	else \
		echo "$(YELLOW)Operation cancelled$(RESET)"; \
	fi

# =============================================================================
# UTILITY COMMANDS
# =============================================================================

.PHONY: update
update: ## Update all images to latest versions
	@echo "$(CYAN)⬆️  Updating Docker images...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) pull

.PHONY: preflight-testnet
preflight-testnet: ensure-venv ## Run local testnet preflight with production-like simulation checks
	@echo "$(CYAN)🧪 Running testnet preflight checks...$(RESET)"
	$(call run-venv-python,scripts/testnet_preflight.py --simulate-production)

.PHONY: preflight-testnet-strict
preflight-testnet-strict: ensure-venv ## Run strict preflight (warnings fail)
	@echo "$(CYAN)🧪 Running strict testnet preflight checks...$(RESET)"
	$(call run-venv-python,scripts/testnet_preflight.py --simulate-production --strict)

.PHONY: test-execution-safety
test-execution-safety: ensure-venv ## Run regression test for emergency cleanup on second-leg failure
	@echo "$(CYAN)🧪 Running execution safety regression tests...$(RESET)"
	$(call run-venv-python-env,PYTHONPATH=$(CURDIR),-m pytest -q tests/test_bot_agent_emergency_cleanup.py)

.PHONY: simulate-production-profile
simulate-production-profile: ensure-venv ## Run baseline vs production-profile simulation via backtest API
	@echo "$(CYAN)📈 Running production-profile simulation...$(RESET)"
	$(call run-venv-python,scripts/simulate_production_profile.py --skip-auth)

.PHONY: ps
ps: ## Show running containers
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) ps

.PHONY: quick-start
quick-start: init-env init-ssl build dev-detached ## Quick start development environment
	@echo "$(GREEN)🎉 Quick start complete!$(RESET)"
	@echo "$(CYAN)📋 Access Points:$(RESET)"
	@echo "  API Documentation: https://localhost/docs"
	@echo "  Health Check:      https://localhost/health"
	@echo "  Logs:             make logs-api"
	@echo "  Shell:            make shell"

# Check if required files exist
$(ENV_FILE):
	@echo "$(YELLOW)⚠️  Environment file not found. Creating from template...$(RESET)"
	@$(MAKE) init-env

.PHONY: local-flower
local-flower: ensure-venv ## Start Celery Flower locally only (port 5555)
	@echo "$(CYAN)🌸 Starting Celery Flower on http://0.0.0.0:5555$(RESET)"
	# On macOS, use spawn instead of fork to avoid Objective-C runtime crashes
	MP_START_METHOD=$${MP_START_METHOD:-spawn} FLOWER_UNAUTHENTICATED_API=false CELERY_BROKER_URL=$${CELERY_BROKER_URL:-$${REDIS_URL:-$${VALKEY_URL:-redis://localhost:6379/1}}} CELERY_RESULT_BACKEND=$${CELERY_RESULT_BACKEND:-$${REDIS_RESULT_BACKEND_URL:-$${VALKEY_RESULT_BACKEND_URL:-redis://localhost:6379/2}}} PYTHON_MULTIPROCESSING_START_METHOD=$${MP_START_METHOD:-spawn} $(VENV_PYTHON) -m celery -A src.infrastructure.workers.celery_app:celery_app flower --address=0.0.0.0 --port=5555
