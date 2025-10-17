.PHONY: help env config setup install test lint format clean run start stop status restart logs test-loki test-loki-dev test-loki-prod \
	docker-build docker-run docker-stop docker-logs docker-shell docker-dev docker-clean docker-up docker-down \
	devcontainer devcontainer-build devcontainer-up devcontainer-down devcontainer-shell devcontainer-logs

# Default target - show help when running just 'make'
help: ## Show this help message
	@echo "dYdX Trading Bot - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Quick start:"
	@echo "  1. make setup     # Create virtual environment"
	@echo "  2. make install   # Install dependencies"
	@echo "  3. make config    # Create configuration file"
	@echo "  4. make start     # Start the trading bot"
	@echo ""
	@echo "Bot management:"
	@echo "  make start        # Start bot in background"
	@echo "  make stop         # Stop running bot"
	@echo "  make restart      # Restart the bot"
	@echo "  make status       # Check bot status"
	@echo "  make logs         # View bot logs"
	@echo ""
	@echo "Docker commands:"
	@echo "  make docker-build    # Build Docker image"
	@echo "  make docker-run      # Run bot in Docker"
	@echo "  make docker-stop     # Stop Docker container"
	@echo "  make docker-logs     # View Docker logs"
	@echo "  make docker-up       # Start with Docker Compose"
	@echo "  make docker-down     # Stop Docker Compose services"
	@echo ""
	@echo "Development container:"
	@echo "  make devcontainer       # Open in VS Code Dev Container (recommended)"
	@echo "  make devcontainer-up    # Start dev container with Docker Compose"
	@echo "  make devcontainer-shell # Open shell in dev container"
	@echo "  make devcontainer-down  # Stop dev container"
	@echo ""
	@echo "Loki testing:"
	@echo "  make test-loki-dev   # Test Loki connection (development)"
	@echo "  make test-loki-prod  # Test Loki connection (production)"

env:
	@echo "⚠️  WARNING: .env configuration is DEPRECATED!"
	@echo "Use 'make config' to create the new YAML-based configuration instead."
	@echo "The .env file is no longer supported by this application."
	@if [ -f .env ]; then \
		read -p ".env file already exists. Do you want to overwrite it with a deprecation notice? (y/n): " answer; \
		if [ "$$answer"="y" ] || [ "$$answer"="yes" ]; then \
			echo "Creating deprecation notice in .env file..."; \
			echo '# ⚠️  DEPRECATED: This .env file is no longer used' > .env; \
			echo '# Configuration is now managed through app/config.yaml' >> .env; \
			echo '# Run `make config` to create the new configuration file' >> .env; \
			echo '# See README.md for migration instructions' >> .env; \
			echo "Deprecation notice created in .env file."; \
		else \
			echo "Operation cancelled."; \
		fi; \
	else \
		echo "Creating deprecation notice in .env file..."; \
		echo '# ⚠️  DEPRECATED: This .env file is no longer used' > .env; \
		echo '# Configuration is now managed through app/config.yaml' >> .env; \
		echo '# Run `make config` to create the new configuration file' >> .env; \
		echo '# See README.md for migration instructions' >> .env; \
		echo "Deprecation notice created in .env file."; \
	fi

setup: ## Set up development environment
	@echo "Setting up development environment..."
	python3 -m venv .venv
	@echo "Virtual environment created. Activate with: source .venv/bin/activate"

check-system: ## Check system dependencies
	@echo "Checking system dependencies..."
	@which gcc >/dev/null 2>&1 || (echo "❌ gcc not found. Install with: sudo apt install build-essential" && exit 1)
	@which python3-config >/dev/null 2>&1 || (echo "❌ Python dev headers not found. Install with: sudo apt install python3-dev python3.12-dev" && exit 1)
	@echo "✅ System dependencies OK"

install: check-system ## Install project dependencies
	@if [ ! -d ".venv" ]; then \
		echo "Virtual environment not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@echo "Installing dependencies..."
	.venv/bin/pip install --upgrade pip
	@echo "Installing main requirements..."
	.venv/bin/pip install -r requirements.txt
	@echo "Installing development tools..."
	.venv/bin/pip install flake8 pylint mypy bandit black isort pytest
	@echo "Dependencies installed successfully!"

test: ## Run tests
	@if [ ! -d ".venv" ]; then \
		echo "Virtual environment not found. Run 'make setup install' first."; \
		exit 1; \
	fi
	@echo "Running tests..."
	PYTHONPATH=. .venv/bin/pytest -q

lint: ## Run linting tools
	@echo "Running linting tools..."
	@echo "→ Flake8..."
	python3 -m flake8 app/ --max-line-length=88 --extend-ignore=E203,W503
	@echo "→ Pylint..."
	python3 -m pylint app/ --disable=C0114,C0115,C0116 --max-line-length=88
	@echo "→ MyPy..."
	python3 -m mypy app/ --ignore-missing-imports --follow-imports=silent
	@echo "→ Bandit (security)..."
	python3 -m bandit -r app/ -f json || true

format: ## Format code with Black and isort
	@if [ ! -d ".venv" ]; then \
		echo "Virtual environment not found. Run 'make setup install' first."; \
		exit 1; \
	fi
	@echo "Formatting code..."
	.venv/bin/black app/ --line-length=88
	.venv/bin/isort app/ --profile black

clean: ## Clean up generated files
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	@echo "Cleanup complete!"

run: ## Run the trading bot (foreground)
	@if [ ! -f "app/config.yaml" ]; then \
		echo "Configuration file not found. Run 'make config' first."; \
		exit 1; \
	fi
	@if [ ! -d ".venv" ]; then \
		echo "Virtual environment not found. Run 'make setup install' first."; \
		exit 1; \
	fi
	cd app && ../.venv/bin/python main.py

start: ## Start the trading bot in background
	@if [ ! -f "scripts/manage_bot.sh" ]; then \
		echo "Bot management script not found."; \
		exit 1; \
	fi
	@chmod +x scripts/manage_bot.sh
	./scripts/manage_bot.sh start

stop: ## Stop the running trading bot
	@if [ ! -f "scripts/manage_bot.sh" ]; then \
		echo "Bot management script not found."; \
		exit 1; \
	fi
	@chmod +x scripts/manage_bot.sh
	./scripts/manage_bot.sh stop

restart: ## Restart the trading bot
	@if [ ! -f "scripts/manage_bot.sh" ]; then \
		echo "Bot management script not found."; \
		exit 1; \
	fi
	@chmod +x scripts/manage_bot.sh
	./scripts/manage_bot.sh restart

status: ## Check trading bot status
	@if [ ! -f "scripts/manage_bot.sh" ]; then \
		echo "Bot management script not found."; \
		exit 1; \
	fi
	@chmod +x scripts/manage_bot.sh
	./scripts/manage_bot.sh status

logs: ## View recent bot logs (if logging to file)
	@echo "Recent bot activity:"
	@if [ -f "bot.log" ]; then \
		tail -n 50 bot.log; \
	else \
		echo "No log file found. Bot logs are sent to console and/or Loki."; \
		echo "To see live logs, use: make run"; \
		echo "Or check your Loki/Grafana dashboard if configured."; \
	fi

test-loki-dev: ## Test Loki connection in development mode (no auth)
	@if [ ! -f "scripts/test_loki.py" ]; then \
		echo "Loki test script not found."; \
		exit 1; \
	fi
	@if [ ! -d ".venv" ]; then \
		echo "Virtual environment not found. Run 'make setup install' first."; \
		exit 1; \
	fi
	@echo "Testing Loki connection in DEVELOPMENT mode (no authentication)..."
	.venv/bin/python scripts/test_loki.py development

test-loki-prod: ## Test Loki connection in production mode (with auth)
	@if [ ! -f "scripts/test_loki.py" ]; then \
		echo "Loki test script not found."; \
		exit 1; \
	fi
	@if [ ! -d ".venv" ]; then \
		echo "Virtual environment not found. Run 'make setup install' first."; \
		exit 1; \
	fi
	@echo "Testing Loki connection in PRODUCTION mode (with authentication)..."
	.venv/bin/python scripts/test_loki.py production

test-loki: ## Test Loki connection (auto-detect environment from config)
	@if [ ! -f "scripts/test_loki.py" ]; then \
		echo "Loki test script not found."; \
		exit 1; \
	fi
	@if [ ! -d ".venv" ]; then \
		echo "Virtual environment not found. Run 'make setup install' first."; \
		exit 1; \
	fi
	@echo "Testing Loki connection (auto-detecting environment from config.yaml)..."
	.venv/bin/python scripts/test_loki.py

config:
	@if [ -d app ]; then \
		CONFIG_DIR="app"; \
	else \
		CONFIG_DIR="."; \
	fi; \
	if [ -f $$CONFIG_DIR/config.yaml ]; then \
		read -p "config.yaml file already exists in $$CONFIG_DIR. Do you want to overwrite it? (y/n): " answer; \
		if [ "$$answer"="y" ] || [ "$$answer"="yes" ]; then \
			echo "Creating config.yaml file..."; \
			echo 'dydx:' > $$CONFIG_DIR/config.yaml; \
			echo '  dydx_chain_address: "dydx1ENTERYOURTESTADDRESS"' >> $$CONFIG_DIR/config.yaml; \
			echo '  dydx_secret_phrase: "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12"' >> $$CONFIG_DIR/config.yaml; \
			echo '  is_testnet: false' >> $$CONFIG_DIR/config.yaml; \
			echo 'telegram:' >> $$CONFIG_DIR/config.yaml; \
			echo '  token: "5860211111:AAGABUQiYet-jI9txy20-hCEgt7NypNwUI"' >> $$CONFIG_DIR/config.yaml; \
			echo '  chat_id: "5236746578"' >> $$CONFIG_DIR/config.yaml; \
			echo 'botSettings:' >> $$CONFIG_DIR/config.yaml; \
			echo '  abortAllPositions: true' >> $$CONFIG_DIR/config.yaml; \
			echo '  findCointegratedPairs: true' >> $$CONFIG_DIR/config.yaml; \
			echo '  manageExits: true' >> $$CONFIG_DIR/config.yaml; \
			echo '  placeTrades: true' >> $$CONFIG_DIR/config.yaml; \
			echo '  resolutionTimeframe: "1HOUR"' >> $$CONFIG_DIR/config.yaml; \
			echo '  strategy: "cointegration"' >> $$CONFIG_DIR/config.yaml; \
			echo '  statsWindow: 21' >> $$CONFIG_DIR/config.yaml; \
			echo '  # Thresholds - Opening' >> $$CONFIG_DIR/config.yaml; \
			echo '  maxHalfLife: 24' >> $$CONFIG_DIR/config.yaml; \
			echo '  ZScoreThreshold: 1.5' >> $$CONFIG_DIR/config.yaml; \
			echo '  usdPerTrade: 10' >> $$CONFIG_DIR/config.yaml; \
			echo '  usdMinCollateral: 100' >> $$CONFIG_DIR/config.yaml; \
			echo '  # Thresholds - Closing' >> $$CONFIG_DIR/config.yaml; \
			echo '  closeAtZscoreCross: true' >> $$CONFIG_DIR/config.yaml; \
			echo '  indexer_endpoint:' >> $$CONFIG_DIR/config.yaml; \
			echo '    testnet: "https://indexer.v4testnet.dydx.exchange"' >> $$CONFIG_DIR/config.yaml; \
			echo '    mainnet: "https://indexer.dydx.trade"' >> $$CONFIG_DIR/config.yaml; \
			echo 'logging:' >> $$CONFIG_DIR/config.yaml; \
			echo '  level: "INFO"' >> $$CONFIG_DIR/config.yaml; \
			echo '  loki:' >> $$CONFIG_DIR/config.yaml; \
			echo '    enabled: false' >> $$CONFIG_DIR/config.yaml; \
			echo '    url: ""' >> $$CONFIG_DIR/config.yaml; \
			echo '    username: ""' >> $$CONFIG_DIR/config.yaml; \
			echo '    password: ""' >> $$CONFIG_DIR/config.yaml; \
			echo '    tenant_id: null' >> $$CONFIG_DIR/config.yaml; \
			echo '    labels:' >> $$CONFIG_DIR/config.yaml; \
			echo '      app: "dydx-trading-bot"' >> $$CONFIG_DIR/config.yaml; \
			echo '      environment: "development"' >> $$CONFIG_DIR/config.yaml; \
			echo 'backtesting:' >> $$CONFIG_DIR/config.yaml; \
			echo '  # Historical data settings' >> $$CONFIG_DIR/config.yaml; \
			echo '  candleResolution: "1HOUR"' >> $$CONFIG_DIR/config.yaml; \
			echo '  maxHistoryDays: 90' >> $$CONFIG_DIR/config.yaml; \
			echo '  # Simulation parameters' >> $$CONFIG_DIR/config.yaml; \
			echo '  startingBalance: 1000.0' >> $$CONFIG_DIR/config.yaml; \
			echo '  transactionFee: 0.0005  # 0.05% per trade (dYdX maker fee)' >> $$CONFIG_DIR/config.yaml; \
			echo '  slippage: 0.001  # 0.1% estimated slippage' >> $$CONFIG_DIR/config.yaml; \
			echo '  # Analysis settings' >> $$CONFIG_DIR/config.yaml; \
			echo '  benchmarkSymbol: "BTC-USD"' >> $$CONFIG_DIR/config.yaml; \
			echo '  riskFreeRate: 0.02  # Annual risk-free rate (2%)' >> $$CONFIG_DIR/config.yaml; \
			echo "config.yaml file created successfully in $$CONFIG_DIR."; \
		else \
			echo "Operation cancelled."; \
		fi; \
	else \
		echo "Creating config.yaml file..."; \
		echo 'environment: "development"  # Options: "development", "dev", "production", "prod"' > $$CONFIG_DIR/config.yaml; \
		echo 'dydx:' >> $$CONFIG_DIR/config.yaml; \
		echo '  dydx_chain_address: "dydx1ENTERYOURTESTADDRESS"' >> $$CONFIG_DIR/config.yaml; \
		echo '  dydx_secret_phrase: "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12"' >> $$CONFIG_DIR/config.yaml; \
		echo '  is_testnet: false' >> $$CONFIG_DIR/config.yaml; \
		echo 'telegram:' >> $$CONFIG_DIR/config.yaml; \
		echo '  token: "5860211111:AAGABUQiYet-jI9txy20-hCEgt7NypNwUI"' >> $$CONFIG_DIR/config.yaml; \
		echo '  chat_id: "5236746578"' >> $$CONFIG_DIR/config.yaml; \
		echo 'botSettings:' >> $$CONFIG_DIR/config.yaml; \
		echo '  abortAllPositions: true' >> $$CONFIG_DIR/config.yaml; \
		echo '  findCointegratedPairs: true' >> $$CONFIG_DIR/config.yaml; \
		echo '  manageExits: true' >> $$CONFIG_DIR/config.yaml; \
		echo '  placeTrades: true' >> $$CONFIG_DIR/config.yaml; \
		echo '  resolutionTimeframe: "1HOUR"' >> $$CONFIG_DIR/config.yaml; \
		echo '  strategy: "cointegration"' >> $$CONFIG_DIR/config.yaml; \
		echo '  statsWindow: 21' >> $$CONFIG_DIR/config.yaml; \
		echo '  # Thresholds - Opening' >> $$CONFIG_DIR/config.yaml; \
		echo '  maxHalfLife: 24' >> $$CONFIG_DIR/config.yaml; \
		echo '  ZScoreThreshold: 1.5' >> $$CONFIG_DIR/config.yaml; \
		echo '  usdPerTrade: 10' >> $$CONFIG_DIR/config.yaml; \
		echo '  usdMinCollateral: 100' >> $$CONFIG_DIR/config.yaml; \
		echo '  # Thresholds - Closing' >> $$CONFIG_DIR/config.yaml; \
		echo '  closeAtZscoreCross: true' >> $$CONFIG_DIR/config.yaml; \
		echo '  indexer_endpoint:' >> $$CONFIG_DIR/config.yaml; \
		echo '    testnet: "https://indexer.v4testnet.dydx.exchange"' >> $$CONFIG_DIR/config.yaml; \
		echo '    mainnet: "https://indexer.dydx.trade"' >> $$CONFIG_DIR/config.yaml; \
		echo 'logging:' >> $$CONFIG_DIR/config.yaml; \
		echo '  level: "INFO"' >> $$CONFIG_DIR/config.yaml; \
		echo '  loki:' >> $$CONFIG_DIR/config.yaml; \
		echo '    enabled: false' >> $$CONFIG_DIR/config.yaml; \
		echo '    url: ""' >> $$CONFIG_DIR/config.yaml; \
		echo '    username: ""' >> $$CONFIG_DIR/config.yaml; \
		echo '    password: ""' >> $$CONFIG_DIR/config.yaml; \
		echo '    tenant_id: null' >> $$CONFIG_DIR/config.yaml; \
		echo '    labels:' >> $$CONFIG_DIR/config.yaml; \
		echo '      app: "dydx-trading-bot"' >> $$CONFIG_DIR/config.yaml; \
		echo '      environment: "development"' >> $$CONFIG_DIR/config.yaml; \
		echo 'backtesting:' >> $$CONFIG_DIR/config.yaml; \
		echo '  # Historical data settings' >> $$CONFIG_DIR/config.yaml; \
		echo '  candleResolution: "1HOUR"' >> $$CONFIG_DIR/config.yaml; \
		echo '  maxHistoryDays: 90' >> $$CONFIG_DIR/config.yaml; \
		echo '  # Simulation parameters' >> $$CONFIG_DIR/config.yaml; \
		echo '  startingBalance: 1000.0' >> $$CONFIG_DIR/config.yaml; \
		echo '  transactionFee: 0.0005  # 0.05% per trade (dYdX maker fee)' >> $$CONFIG_DIR/config.yaml; \
		echo '  slippage: 0.001  # 0.1% estimated slippage' >> $$CONFIG_DIR/config.yaml; \
		echo '  # Analysis settings' >> $$CONFIG_DIR/config.yaml; \
		echo '  benchmarkSymbol: "BTC-USD"' >> $$CONFIG_DIR/config.yaml; \
		echo '  riskFreeRate: 0.02  # Annual risk-free rate (2%)' >> $$CONFIG_DIR/config.yaml; \
		echo "config.yaml file created successfully in $$CONFIG_DIR."; \
	fi

# ============================================================================
# Docker Commands
# ============================================================================

docker-build: ## Build Docker image for production
	@echo "🐳 Building Docker image for production..."
	@if [ ! -f "app/config.yaml" ]; then \
		echo "⚠️  Configuration file not found. Run 'make config' first."; \
		exit 1; \
	fi
	docker build -t dydx-trading-bot:latest --target production .
	@echo "✅ Docker image built successfully!"

docker-build-dev: ## Build Docker image for development
	@echo "🐳 Building Docker image for development..."
	docker build -t dydx-trading-bot:dev --target development .
	@echo "✅ Development Docker image built successfully!"

docker-run: ## Run trading bot in Docker container (production)
	@echo "🚀 Starting trading bot in Docker..."
	@if [ ! -f "app/config.yaml" ]; then \
		echo "⚠️  Configuration file not found. Run 'make config' first."; \
		exit 1; \
	fi
	docker run -d \
		--name dydx-trading-bot \
		--restart unless-stopped \
		-v $(PWD)/app/config.yaml:/app/app/config.yaml:ro \
		-v $(PWD)/app/bot_agents.json:/app/app/bot_agents.json \
		-v $(PWD)/app/cointegrated_pairs.csv:/app/app/cointegrated_pairs.csv \
		dydx-trading-bot:latest
	@echo "✅ Trading bot started in Docker! Use 'make docker-logs' to see output."

docker-stop: ## Stop and remove Docker container
	@echo "🛑 Stopping Docker container..."
	@if [ $$(docker ps -q -f name=dydx-trading-bot) ]; then \
		docker stop dydx-trading-bot; \
	fi
	@if [ $$(docker ps -aq -f name=dydx-trading-bot) ]; then \
		docker rm dydx-trading-bot; \
	fi
	@echo "✅ Docker container stopped and removed."

docker-logs: ## View Docker container logs
	@echo "📋 Viewing Docker logs..."
	@if [ $$(docker ps -q -f name=dydx-trading-bot) ]; then \
		docker logs -f dydx-trading-bot; \
	else \
		echo "❌ No running container found. Use 'make docker-run' to start."; \
	fi

docker-shell: ## Open shell in running Docker container
	@echo "🐚 Opening shell in Docker container..."
	@if [ $$(docker ps -q -f name=dydx-trading-bot) ]; then \
		docker exec -it dydx-trading-bot /bin/bash; \
	else \
		echo "❌ No running container found. Use 'make docker-run' to start."; \
	fi

docker-dev: ## Start development container with volume mounts
	@echo "🔧 Starting development Docker container..."
	docker run -it --rm \
		--name dydx-trading-bot-dev \
		-v $(PWD):/app \
		-w /app \
		dydx-trading-bot:dev /bin/bash
	@echo "✅ Development container ready! You're now inside the container."

docker-clean: ## Remove Docker images and containers
	@echo "🧹 Cleaning up Docker resources..."
	@if [ $$(docker ps -aq -f name=dydx-trading-bot) ]; then \
		docker rm -f $$(docker ps -aq -f name=dydx-trading-bot); \
	fi
	@if [ $$(docker images -q dydx-trading-bot) ]; then \
		docker rmi $$(docker images -q dydx-trading-bot); \
	fi
	@echo "✅ Docker cleanup complete."

# Docker Compose commands
docker-up: ## Start services with Docker Compose (production)
	@echo "🐳 Starting services with Docker Compose..."
	@if [ ! -f "app/config.yaml" ]; then \
		echo "⚠️  Configuration file not found. Run 'make config' first."; \
		exit 1; \
	fi
	docker compose up -d dydx-trading-bot
	@echo "✅ Services started! Use 'docker compose logs -f' to see output."

docker-up-dev: ## Start development services with Docker Compose  
	@echo "🔧 Starting development services with Docker Compose..."
	docker compose --profile dev up -d dydx-dev
	@echo "✅ Development services started!"

docker-up-logging: ## Start with logging stack (Loki + Grafana)
	@echo "📊 Starting services with logging stack..."
	docker compose --profile logging up -d
	@echo "✅ Services with logging started!"
	@echo "   - Grafana: http://localhost:3000 (admin/admin)"
	@echo "   - Loki: http://localhost:3100"

docker-down: ## Stop Docker Compose services
	@echo "🛑 Stopping Docker Compose services..."
	docker compose down --remove-orphans
	@echo "✅ Services stopped."

docker-status: ## Show Docker container status
	@echo "📊 Docker container status:"
	@echo ""
	@docker ps -a --filter "name=dydx" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "Images:"
	@docker images --filter "reference=dydx-trading-bot" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}"

# ============================================================================
# Development Container Commands
# ============================================================================

devcontainer: ## Open project in VS Code Dev Container (recommended)
	@echo "🚀 Opening project in VS Code Dev Container..."
	@if ! command -v code >/dev/null 2>&1; then \
		echo "❌ VS Code CLI not found. Please install VS Code and ensure 'code' command is available."; \
		echo "   Or manually: Open VS Code → Open Folder → Choose this directory → Reopen in Container"; \
		exit 1; \
	fi
	@if [ ! -f .devcontainer/devcontainer.json ]; then \
		echo "❌ Dev container configuration not found at .devcontainer/devcontainer.json"; \
		exit 1; \
	fi
	code .
	@echo "✅ VS Code should now prompt to 'Reopen in Container' or use Ctrl/Cmd+Shift+P → 'Dev Containers: Rebuild and Reopen in Container'"

devcontainer-build: ## Build development container image
	@echo "🔧 Building development container image..."
	@if [ ! -f .devcontainer/devcontainer.json ]; then \
		echo "❌ Dev container configuration not found at .devcontainer/devcontainer.json"; \
		exit 1; \
	fi
	cd .devcontainer && docker build -f Dockerfile -t dydx-trading-bot-devcontainer ..
	@echo "✅ Development container image built successfully!"

devcontainer-up: ## Start development container with Docker Compose
	@echo "🚀 Starting development container with Docker Compose..."
	@if [ ! -f .devcontainer/docker-compose.yml ]; then \
		echo "❌ Dev container compose file not found at .devcontainer/docker-compose.yml"; \
		exit 1; \
	fi
	cd .devcontainer && docker-compose up -d devcontainer
	@echo "✅ Development container started!"
	@echo "📝 Connect with: make devcontainer-shell"
	@echo "📊 View logs with: make devcontainer-logs"

devcontainer-down: ## Stop development container
	@echo "🛑 Stopping development container..."
	@if [ ! -f .devcontainer/docker-compose.yml ]; then \
		echo "❌ Dev container compose file not found at .devcontainer/docker-compose.yml"; \
		exit 1; \
	fi
	cd .devcontainer && docker-compose down
	@echo "✅ Development container stopped."

devcontainer-shell: ## Open shell in development container
	@echo "🐚 Opening shell in development container..."
	@if [ ! -f .devcontainer/docker-compose.yml ]; then \
		echo "❌ Dev container compose file not found"; \
		exit 1; \
	fi
	cd .devcontainer && docker-compose exec devcontainer bash
	@echo "🎉 You're now in the development container!"

devcontainer-logs: ## View development container logs
	@echo "📋 Viewing development container logs..."
	@if [ ! -f .devcontainer/docker-compose.yml ]; then \
		echo "❌ Dev container compose file not found"; \
		exit 1; \
	fi
	cd .devcontainer && docker-compose logs -f devcontainer

devcontainer-setup: ## Quick setup inside development container
	@echo "🔧 Running quick setup for development container..."
	@if command -v bot-setup >/dev/null 2>&1; then \
		bot-setup; \
	else \
		echo "Setting up development environment manually..."; \
		pip install --upgrade pip setuptools wheel; \
		if [ -f requirements.txt ]; then pip install -r requirements.txt; fi; \
		if [ -f requirements-dev.txt ]; then pip install -r requirements-dev.txt; fi; \
		echo "✅ Development environment setup complete!"; \
	fi

devcontainer-status: ## Show development container status
	@echo "📊 Development container status:"
	@echo ""
	@if [ -f .devcontainer/docker-compose.yml ]; then \
		cd .devcontainer && docker-compose ps; \
	else \
		docker ps -a --filter "name=dydx.*dev" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"; \
	fi
	@echo ""
	@echo "Development images:"
	@docker images --filter "reference=*dydx*dev*" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}"

# ============================================================================
# Backtesting Commands
# ============================================================================

backtest: ## Run backtest for specified period (START=YYYY-MM-DD END=YYYY-MM-DD PAIRS=N or ALL)
	@if [ -z "$(START)" ] || [ -z "$(END)" ]; then \
		echo "❌ Please provide START and END dates"; \
		echo "Usage: make backtest START=2024-01-01 END=2024-03-31 PAIRS=10"; \
		echo "       make backtest START=2024-09-01 END=2024-10-15 PAIRS=ALL"; \
		exit 1; \
	fi
	@if [ ! -d ".venv" ]; then \
		echo "❌ Virtual environment not found. Run 'make setup install' first."; \
		exit 1; \
	fi
	@echo "🔬 Running backtest: $(START) to $(END) ($(or $(PAIRS),5) pairs)..."
	.venv/bin/python scripts/run_backtest.py --start $(START) --end $(END) --pairs $(or $(PAIRS),5)

backtest-quick: ## Run quick 1-month backtest with 3 pairs
	@if [ ! -d ".venv" ]; then \
		echo "❌ Virtual environment not found. Run 'make setup install' first."; \
		exit 1; \
	fi
	@echo "⚡ Running quick backtest (1 month, 3 pairs)..."
	.venv/bin/python scripts/run_backtest.py --start 2024-01-01 --end 2024-01-31 --pairs 3

backtest-3month: ## Run comprehensive 3-month backtest with 10 pairs
	@if [ ! -d ".venv" ]; then \
		echo "❌ Virtual environment not found. Run 'make setup install' first."; \
		exit 1; \
	fi
	@echo "📊 Running 3-month backtest (10 pairs)..."
	.venv/bin/python scripts/run_backtest.py --start 2024-01-01 --end 2024-03-31 --pairs 10

backtest-all: ## Run backtest with ALL available pairs (START=YYYY-MM-DD END=YYYY-MM-DD)
	@if [ -z "$(START)" ] || [ -z "$(END)" ]; then \
		echo "❌ Please provide START and END dates"; \
		echo "Usage: make backtest-all START=2024-09-01 END=2024-10-15"; \
		exit 1; \
	fi
	@if [ ! -d ".venv" ]; then \
		echo "❌ Virtual environment not found. Run 'make setup install' first."; \
		exit 1; \
	fi
	@echo "🚀 Running backtest with ALL pairs: $(START) to $(END)..."
	.venv/bin/python scripts/run_backtest.py --start $(START) --end $(END) --pairs ALL

backtest-all-recent: ## Run backtest with ALL pairs for recent 1 month period
	@if [ ! -d ".venv" ]; then \
		echo "❌ Virtual environment not found. Run 'make setup install' first."; \
		exit 1; \
	fi
	@echo "🌟 Running recent ALL-pairs backtest (1 month)..."
	.venv/bin/python scripts/run_backtest.py --start 2024-09-15 --end 2024-10-15 --pairs ALL

backtest-analysis: ## Analyze all saved backtest results
	@if [ ! -d ".venv" ]; then \
		echo "❌ Virtual environment not found. Run 'make setup install' first."; \
		exit 1; \
	fi
	@if [ ! -d "app/backtest_results" ]; then \
		echo "❌ No backtest results directory found. Run a backtest first."; \
		exit 1; \
	fi
	@echo "📈 Analyzing backtest results..."
	.venv/bin/python scripts/analyze_backtest_results.py

backtest-clean: ## Clean up old backtest results (keeps 20 most recent)
	@echo "🧹 Cleaning up old backtest results..."
	@if [ -d "app/backtest_results" ]; then \
		.venv/bin/python -c "from app.models.backtest_storage import backtest_storage; print(f'Cleaned up {backtest_storage.cleanup_old_results(20)} old results')"; \
	else \
		echo "No backtest results directory found."; \
	fi
