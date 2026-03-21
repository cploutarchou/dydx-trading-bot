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

.PHONY: init-ssl
init-ssl: ## Generate SSL certificates for development
	@echo "$(CYAN)🔐 Generating SSL certificates...$(RESET)"
	@cd $(DOCKER_DIR)/ssl && chmod +x generate-ssl.sh && ./generate-ssl.sh

.PHONY: init-auth
init-auth: ## Initialize authentication database
	@echo "$(CYAN)🔑 Initializing authentication database...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec bot-api python init_auth_db.py

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
dev-api: ## Start bot API server locally with Python (port 8000)
	@echo "$(CYAN)🚀 Starting bot API server on http://0.0.0.0:8000$(RESET)"
	@echo "$(YELLOW)💡 Make sure .venv is activated$(RESET)"
	@if [ -d .venv ]; then \
		. .venv/bin/activate && python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --reload; \
	else \
		echo "$(RED)❌ Virtual environment not found at .venv$(RESET)"; \
		echo "$(YELLOW)Run: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt$(RESET)"; \
		exit 1; \
	fi

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
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f postgres

.PHONY: logs-nginx
logs-nginx: ## Show Nginx logs
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) logs -f nginx

# =============================================================================
# DATABASE COMMANDS
# =============================================================================

.PHONY: db-shell
db-shell: ## Connect to database shell
	@echo "$(CYAN)🗄️  Connecting to database...$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec postgres psql -U botuser -d dydx_trading_bot

.PHONY: db-backup
db-backup: ## Backup database
	@echo "$(CYAN)💾 Creating database backup...$(RESET)"
	@mkdir -p backups
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec postgres pg_dump -U botuser -d dydx_trading_bot | gzip > backups/backup_$(shell date +%Y%m%d_%H%M%S).sql.gz
	@echo "$(GREEN)✅ Database backup created in backups/$(RESET)"

.PHONY: db-reset
db-reset: ## Reset database (WARNING: deletes all data)
	@echo "$(RED)⚠️  This will DELETE ALL DATABASE DATA!$(RESET)"
	@read -p "Are you sure you want to reset the database? (y/N): " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) stop postgres; \
		docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) rm -f postgres; \
		docker volume rm $(PROJECT_NAME)_postgres_data || true; \
		docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up -d postgres; \
		sleep 10; \
		$(MAKE) init-auth; \
		echo "$(GREEN)✅ Database reset complete$(RESET)"; \
	else \
		echo "$(YELLOW)Operation cancelled$(RESET)"; \
	fi

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
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec postgres /bin/bash

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
	@curl -s http://localhost:8000/health | jq '.' 2>/dev/null || echo "  ❌ Not accessible"
	@echo ""
	@echo "$(GREEN)Authentication:$(RESET)"
	@curl -s http://localhost:8000/auth/health | jq '.' 2>/dev/null || echo "  ❌ Not accessible"
	@echo ""
	@echo "$(GREEN)Database:$(RESET)"
	@docker-compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) exec postgres pg_isready -U botuser 2>/dev/null && echo "  ✅ Healthy" || echo "  ❌ Not healthy"
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
preflight-testnet: ## Run local testnet preflight with production-like simulation checks
	@echo "$(CYAN)🧪 Running testnet preflight checks...$(RESET)"
	@python3 scripts/testnet_preflight.py --simulate-production

.PHONY: preflight-testnet-strict
preflight-testnet-strict: ## Run strict preflight (warnings fail)
	@echo "$(CYAN)🧪 Running strict testnet preflight checks...$(RESET)"
	@python3 scripts/testnet_preflight.py --simulate-production --strict

.PHONY: test-execution-safety
test-execution-safety: ## Run regression test for emergency cleanup on second-leg failure
	@echo "$(CYAN)🧪 Running execution safety regression tests...$(RESET)"
	@PYTHONPATH=$(PWD) pytest -q tests/test_bot_agent_emergency_cleanup.py

.PHONY: simulate-production-profile
simulate-production-profile: ## Run baseline vs production-profile simulation via backtest API
	@echo "$(CYAN)📈 Running production-profile simulation...$(RESET)"
	@python3 scripts/simulate_production_profile.py --skip-auth

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
