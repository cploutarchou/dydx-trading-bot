.PHONY: help setup install test lint format clean run start stop status restart logs docker-build docker-run docker-stop docker-logs docker-shell docker-dev docker-clean docker-up docker-down docker-up-logging docker-down-logging devcontainer devcontainer-build devcontainer-up devcontainer-down devcontainer-shell devcontainer-logs test-loki test-loki-dev test-loki-prod backtest backtest-quick backtest-3month backtest-analysis backtest-clean backend-run worker-run config env-setup env db-upgrade db-downgrade db-revision db-current db-history db-merge db-branches db-init create-migration migration-up migration-down migration-verify db-init-schema db-verify-schema db-reset db-migrate-legacy db-up db-status db-down stack-env stack-up-dev stack-up-prod stack-down stack-logs stack-ps

# Default target - show help when running just 'make'
help: ## Show this help message
	@echo "dYdX Trading Bot - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Quick start:"
	@echo "  1. make setup           # Create virtual environment"
	@echo "  2. make install         # Install dependencies"
	@echo "  3. make config          # Create configuration file"
	@echo "  4. make start           # Start the trading bot"
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
	.venv/bin/pip install --upgrade pip setuptools wheel
	.venv/bin/pip install -r requirements.txt
	.venv/bin/pip install -e ./backend --use-pep517
	@echo "✅ All dependencies installed"
	@echo "📌 Backend package installed in editable mode"

config: ## Create configuration file from template
	@if [ -f app/config.yaml ]; then \
		echo "⚠️  app/config.yaml already exists. Backing up to app/config.yaml.bak"; \
		cp app/config.yaml app/config.yaml.bak; \
	fi
	@echo "Creating app/config.yaml from template..."
	@if [ ! -f app/config.yaml ]; then \
		cp app/config.yaml.example app/config.yaml 2>/dev/null || echo "⚠️  config.yaml.example not found. Please create app/config.yaml manually."; \
	fi
	@echo "✅ Configuration file ready at app/config.yaml"

env-setup: ## Set up environment variables from .env.example
	@if [ -f .env ]; then \
		echo "⚠️  .env already exists. Backing up to .env.bak"; \
		cp .env .env.bak; \
	fi
	@echo "Creating .env from template..."
	@cp .env.example.new .env 2>/dev/null || cp .env.example .env
	@echo "✅ Environment file created at .env"
	@echo "📌 Edit .env with your specific settings (keys, addresses, etc.)"
	@echo ""
	@echo "🔐 Generate encryption key with:"
	@echo "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
	@echo ""

env: ## Show deprecation warning for .env
	@echo "⚠️  WARNING: .env configuration is DEPRECATED!"
	@echo "Use 'make config' to create the new YAML-based configuration instead."
	@echo "The .env file is no longer supported by this application."

# ============================================================================
# DEVELOPMENT
# ============================================================================

test: ## Run pytest suite (tests/ directory only)
	PYTHONPATH=$(PWD) .venv/bin/pytest tests/ -v --tb=short

lint: ## Check code with flake8 and pylint
	.venv/bin/flake8 app/ backend/ --max-line-length=120 --exclude=__pycache__
	.venv/bin/pylint app/ backend/ --disable=C0111,W0212 || true

format: ## Auto-format code with black
	.venv/bin/black app/ backend/ --line-length=120

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
	.venv/bin/python app/main.py

backend-run: worker-run ## Start backend server (alias for worker-run)

worker-run: ## Start backend worker (FastAPI server on port 8888)
	.venv/bin/python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8888

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
# DEVELOPMENT CONTAINER
# ============================================================================

devcontainer: ## Open in VS Code Dev Container (recommended)
	code --remote="container-url?" .

devcontainer-build: ## Build dev container image
	docker-compose -f docker-compose.yml build --no-cache
	@echo "✅ Dev container built"

devcontainer-up: ## Start dev container with Docker Compose
	docker-compose up -d
	@echo "✅ Dev container started"

devcontainer-down: ## Stop dev container
	docker-compose down
	@echo "✅ Dev container stopped"

devcontainer-shell: ## Open shell in dev container
	docker-compose exec -it dydx-bot /bin/bash

devcontainer-logs: ## View dev container logs
	docker-compose logs -f

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

db-up: ## Start backend DB services (postgres + redis) via Docker Compose
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		docker compose -f backend/docker-compose.yml up -d postgres redis; \
		echo "✅ Backend DB services started"; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot start DB services"; \
		exit 0; \
	fi

db-status: ## Show backend DB services status via Docker Compose
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		docker compose -f backend/docker-compose.yml ps postgres redis; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot query DB service status"; \
		exit 0; \
	fi

db-down: ## Stop backend DB services (postgres + redis) via Docker Compose
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		docker compose -f backend/docker-compose.yml stop postgres redis; \
		echo "✅ Backend DB services stopped"; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot stop DB services"; \
		exit 0; \
	fi

stack-up-dev: ## Start split app stack (api + worker + frontend dev + postgres + redis)
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		ENV_OPT=$$( [ -f .env.stack ] && echo "--env-file .env.stack" ); \
		docker compose $$ENV_OPT -f docker-compose.stack.yml --profile dev up -d; \
		echo "✅ Dev stack started (frontend:5173, api:8889)"; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot start stack"; \
		exit 0; \
	fi

stack-up-prod: ## Start split app stack (api + worker + frontend preview + postgres + redis)
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		ENV_OPT=$$( [ -f .env.stack ] && echo "--env-file .env.stack" ); \
		docker compose $$ENV_OPT -f docker-compose.stack.yml --profile prod up -d; \
		echo "✅ Prod-like stack started (proxy:8080, api internal, frontend internal)"; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot start stack"; \
		exit 0; \
	fi

stack-down: ## Stop split app stack
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		ENV_OPT=$$( [ -f .env.stack ] && echo "--env-file .env.stack" ); \
		docker compose $$ENV_OPT -f docker-compose.stack.yml down; \
		echo "✅ Stack stopped"; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot stop stack"; \
		exit 0; \
	fi

stack-logs: ## Follow logs for split app stack
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		ENV_OPT=$$( [ -f .env.stack ] && echo "--env-file .env.stack" ); \
		docker compose $$ENV_OPT -f docker-compose.stack.yml logs -f --tail=100; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot fetch logs"; \
		exit 0; \
	fi

stack-ps: ## Show status for split app stack services
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		ENV_OPT=$$( [ -f .env.stack ] && echo "--env-file .env.stack" ); \
		docker compose $$ENV_OPT -f docker-compose.stack.yml ps; \
	else \
		echo "⚠️  Docker daemon unavailable; cannot fetch service status"; \
		exit 0; \
	fi

stack-env: ## Create .env.stack from template (safe; won't overwrite existing)
	@if [ -f .env.stack ]; then \
		echo "ℹ️ .env.stack already exists"; \
	else \
		cp .env.stack.example .env.stack; \
		echo "✅ Created .env.stack (edit secrets before production use)"; \
	fi

.DEFAULT_GOAL := help
