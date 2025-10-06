.PHONY: help env config setup install test lint format clean run start stop status restart logs

# Default target - show help when running just 'make'
help: ## Show this help message
	@echo "dYdX Trading Bot - Availab	else \
		echo "Creating config.yaml file..."; \
		echo 'environment: "development"  # Options: "development", "dev", "production", "prod"' > $$CONFIG_DIR/config.yaml; \
		echo 'dydx:' >> $$CONFIG_DIR/config.yaml; \
		echo '  dydx_chain_address: "dydx1ENTERYOURTESTADDRESS"' >> $$CONFIG_DIR/config.yaml; \
		echo '  dydx_secret_phrase: "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12"' >> $$CONFIG_DIR/config.yaml; \
		echo '  is_testnet: false' >> $$CONFIG_DIR/config.yaml;ommands:"
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
	@if [ ! -d ".venv" ]; then \
		echo "Virtual environment not found. Run 'make setup install' first."; \
		exit 1; \
	fi
	@echo "Running linting tools..."
	@echo "→ Flake8..."
	.venv/bin/flake8 app/ --max-line-length=88 --extend-ignore=E203,W503
	@echo "→ Pylint..."
	.venv/bin/pylint app/ --disable=C0114,C0115,C0116 --max-line-length=88
	@echo "→ MyPy..."
	.venv/bin/mypy app/ --ignore-missing-imports --follow-imports=silent
	@echo "→ Bandit (security)..."
	.venv/bin/bandit -r app/ -f json || true

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
		echo "config.yaml file created successfully in $$CONFIG_DIR."; \
	fi
