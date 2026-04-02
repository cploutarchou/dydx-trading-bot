.PHONY: help install dev build lint format test clean docker-build docker-run docker-stop docker-logs setup preview lint-fix format-check dev-env

# Default target
DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Project info
PROJECT_NAME := dYdX Trading Bot Frontend
PROJECT_VERSION := 1.0.0
NODE_ENV ?= development
MODE ?= development
DOCKER_IMAGE_NAME ?= dydx-frontend
DOCKER_IMAGE_TAG ?= latest
DOCKER_DEV_IMAGE ?= $(DOCKER_IMAGE_NAME)-dev:$(DOCKER_DEV_TAG)
DOCKER_PROD_IMAGE ?= $(DOCKER_IMAGE_NAME):$(DOCKER_IMAGE_TAG)
DOCKER_DEV_TAG ?= dev
PORT_DEV ?= 5173
PORT_PROD ?= 3000
API_URL ?= http://localhost:8889

# ============================================================================
# HELP COMMAND
# ============================================================================

help: ## Display this help message with all available commands
	@echo ""
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║$(NC) $(GREEN)$(PROJECT_NAME)$(NC) $(BLUE)║$(NC)"
	@echo "$(BLUE)║$(NC) Version: $(PROJECT_VERSION) $(BLUE)║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(YELLOW)📋 USAGE:$(NC)"
	@echo "  make <target>"
	@echo ""
	@echo "$(YELLOW)🚀 DEVELOPMENT TARGETS:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(dev|install|setup|format|lint)' | awk 'BEGIN {FS = ":.*?## "} {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)🏗️  BUILD & DEPLOYMENT TARGETS:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(build|preview|docker)' | awk 'BEGIN {FS = ":.*?## "} {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)🧹 CLEANUP TARGETS:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(clean|reset)' | awk 'BEGIN {FS = ":.*?## "} {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)📚 MISCELLANEOUS TARGETS:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -vE '(dev|install|setup|format|lint|build|preview|docker|clean|reset|help)' | awk 'BEGIN {FS = ":.*?## "} {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)⚙️  ENVIRONMENT VARIABLES:$(NC)"
	@echo "  NODE_ENV=production       # Set Node environment (default: development)"
	@echo "  API_URL=<url>            # Backend API URL (default: $(API_URL))"
	@echo "  DOCKER_IMAGE_TAG=<tag>   # Docker image tag (default: $(DOCKER_IMAGE_TAG))"
	@echo "  PORT_DEV=<port>          # Dev server port (default: $(PORT_DEV))"
	@echo ""
	@echo "$(YELLOW)📖 EXAMPLES:$(NC)"
	@echo "  make dev                 # Start development server"
	@echo "  make build               # Create production build"
	@echo "  make docker-build        # Build Docker production image"
	@echo "  make docker-run          # Run Docker container"
	@echo "  make lint format         # Check and format code"
	@echo "  make clean               # Remove all generated files"
	@echo ""
	@echo "$(YELLOW)🔗 QUICK LINKS:$(NC)"
	@echo "  Dev Server:      http://localhost:$(PORT_DEV)"
	@echo "  Backend API:     $(API_URL)"
	@echo "  Documentation:   ./docs/README.md"
	@echo ""

# ============================================================================
# SETUP & INSTALLATION
# ============================================================================

install: ## Install project dependencies using npm
	@echo "$(BLUE)📦 Installing dependencies...$(NC)"
	npm install
	@echo "$(GREEN)✓ Dependencies installed successfully$(NC)"

setup: install ## Complete project setup (install dependencies and configure environment)
	@echo "$(BLUE)🔧 Setting up project environment...$(NC)"
	@if [ ! -f ../.env ]; then \
		echo "$(YELLOW)⚠ Repo-root .env not found - create ../.env before starting the frontend$(NC)"; \
	else \
		echo "$(GREEN)✓ Using repo-root .env as the frontend environment source$(NC)"; \
	fi
	@echo "$(BLUE)📋 Environment configuration:$(NC)"
	@echo "  API_URL: $$(grep '^VITE_API_URL=' ../.env 2>/dev/null || echo 'VITE_API_URL=$(API_URL)')"
	@echo "$(GREEN)✓ Project setup complete!$(NC)"

dev-env: ## Update repo-root .env frontend settings for development|production (usage: make dev-env MODE=development)
	@MODE_VALUE="$(MODE)"; \
	if [ "$$MODE_VALUE" != "development" ] && [ "$$MODE_VALUE" != "production" ]; then \
		echo "$(RED)Invalid MODE='$$MODE_VALUE'. Use MODE=development or MODE=production$(NC)"; \
		exit 1; \
	fi; \
	@if [ ! -f ../.env ]; then touch ../.env; fi; \
	MODE_VALUE="$$MODE_VALUE" python3 -c "from pathlib import Path; import os; mode=os.environ['MODE_VALUE']; p=Path('../.env'); lines=p.read_text().splitlines() if p.exists() else []; updates={'VITE_API_URL':('http://localhost:8888' if mode=='development' else 'https://your-backend-domain.example')}; out=[]; keys_done=set();\nfor line in lines:\n    if not line or line.lstrip().startswith('#') or '=' not in line:\n        out.append(line);\n        continue\n    key=line.split('=',1)[0]\n    if key in updates:\n        out.append(f'{key}={updates[key]}'); keys_done.add(key)\n    else:\n        out.append(line)\nfor key, value in updates.items():\n    if key not in keys_done and not any(existing.startswith(f'{key}=') for existing in out):\n        out.append(f'{key}={value}')\np.write_text('\\n'.join(out).rstrip() + '\\n'); print(f'Updated {p} for {mode}')";
	@echo "$(GREEN)✓ Repo-root .env updated for $(MODE)$(NC)"

# ============================================================================
# DEVELOPMENT
# ============================================================================

dev: ## Start development server with HMR (Hot Module Replacement)
	@echo "$(BLUE)🚀 Starting development server...$(NC)"
	@echo "$(YELLOW)ℹ Server will run on: http://localhost:$(PORT_DEV)$(NC)"
	@echo "$(YELLOW)ℹ Backend API: $(API_URL)$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to stop$(NC)"
	npm run dev

dev-debug: ## Start development server with verbose logging for debugging
	@echo "$(BLUE)🐛 Starting development server with DEBUG mode...$(NC)"
	DEBUG=* npm run dev

# ============================================================================
# LINTING & CODE QUALITY
# ============================================================================

lint: ## Run ESLint to check code quality
	@echo "$(BLUE)🔍 Running ESLint...$(NC)"
	npm run lint
	@echo "$(GREEN)✓ Linting complete$(NC)"

lint-fix: ## Run ESLint and automatically fix fixable issues
	@echo "$(BLUE)🔧 Running ESLint with --fix...$(NC)"
	npx eslint src --ext .ts,.tsx --fix
	@echo "$(GREEN)✓ Automatic fixes applied$(NC)"

format: ## Format code using Prettier
	@echo "$(BLUE)💅 Formatting code with Prettier...$(NC)"
	@if command -v prettier >/dev/null 2>&1; then \
		prettier --write "src/**/*.{ts,tsx,css,json}"; \
		echo "$(GREEN)✓ Code formatted successfully$(NC)"; \
	else \
		echo "$(YELLOW)⚠ Prettier not installed, trying npx...$(NC)"; \
		npx prettier --write "src/**/*.{ts,tsx,css,json}"; \
		echo "$(GREEN)✓ Code formatted successfully$(NC)"; \
	fi

format-check: ## Check code formatting without making changes
	@echo "$(BLUE)🔍 Checking code formatting...$(NC)"
	@if command -v prettier >/dev/null 2>&1; then \
		prettier --check "src/**/*.{ts,tsx,css,json}" || exit 1; \
		echo "$(GREEN)✓ Code formatting is correct$(NC)"; \
	else \
		npx prettier --check "src/**/*.{ts,tsx,css,json}" || exit 1; \
		echo "$(GREEN)✓ Code formatting is correct$(NC)"; \
	fi

# ============================================================================
# BUILD & OPTIMIZATION
# ============================================================================

build: ## Build for production with optimizations
	@echo "$(BLUE)🔨 Building for production...$(NC)"
	NODE_ENV=production npm run build
	@echo "$(BLUE)📊 Build statistics:$(NC)"
	@du -sh dist/ 2>/dev/null || echo "  (dist folder size unavailable)"
	@echo "$(GREEN)✓ Production build complete$(NC)"
	@echo "$(YELLOW)ℹ Output directory: ./dist$(NC)"

build-analyze: ## Build for production and analyze bundle size
	@echo "$(BLUE)📦 Building with bundle analysis...$(NC)"
	NODE_ENV=production npm run build
	@echo "$(BLUE)📊 Build Analysis:$(NC)"
	@echo "  Total size: $$(du -sh dist/ 2>/dev/null | cut -f1)"
	@echo "  Files: $$(find dist -type f | wc -l)"
	@echo "$(YELLOW)ℹ Run 'make preview' to test the production build locally$(NC)"

preview: ## Preview production build locally
	@echo "$(BLUE)👁️  Starting production preview server...$(NC)"
	@echo "$(YELLOW)ℹ Preview will run on: http://localhost:4173$(NC)"
	npm run preview

# ============================================================================
# DOCKER OPERATIONS
# ============================================================================

docker-build: ## Build Docker production image
	@echo "$(BLUE)🐳 Building Docker production image...$(NC)"
	@echo "  Image: $(DOCKER_PROD_IMAGE)"
	docker build -t $(DOCKER_PROD_IMAGE) .
	@echo "$(GREEN)✓ Docker image built successfully$(NC)"
	@echo "$(YELLOW)ℹ Run with: make docker-run$(NC)"

docker-build-dev: ## Build Docker development image with HMR support
	@echo "$(BLUE)🐳 Building Docker development image...$(NC)"
	@echo "  Image: $(DOCKER_DEV_IMAGE)"
	docker build -f Dockerfile.dev -t $(DOCKER_DEV_IMAGE) .
	@echo "$(GREEN)✓ Docker development image built successfully$(NC)"

docker-run: docker-build ## Build and run Docker production container
	@echo "$(BLUE)🚀 Running Docker container...$(NC)"
	@echo "  Image: $(DOCKER_PROD_IMAGE)"
	@echo "  Port: $(PORT_PROD)"
	docker run -p $(PORT_PROD):3000 $(DOCKER_PROD_IMAGE)

docker-run-dev: docker-build-dev ## Build and run Docker development container with HMR
	@echo "$(BLUE)🚀 Running Docker development container...$(NC)"
	@echo "  Image: $(DOCKER_DEV_IMAGE)"
	@echo "  Port: $(PORT_DEV)"
	docker run -p $(PORT_DEV):5173 $(DOCKER_DEV_IMAGE)

docker-stop: ## Stop all running Docker containers for this project
	@echo "$(BLUE)🛑 Stopping Docker containers...$(NC)"
	@docker ps --filter "ancestor=$(DOCKER_PROD_IMAGE)" --format "{{.ID}}" | xargs -r docker stop
	@docker ps --filter "ancestor=$(DOCKER_DEV_IMAGE)" --format "{{.ID}}" | xargs -r docker stop
	@echo "$(GREEN)✓ Containers stopped$(NC)"

docker-logs: ## Display logs from running Docker containers
	@echo "$(BLUE)📋 Docker container logs...$(NC)"
	docker logs -f $$(docker ps --filter "ancestor=$(DOCKER_PROD_IMAGE) OR ancestor=$(DOCKER_DEV_IMAGE)" --format "{{.ID}}" | head -1) 2>/dev/null || echo "$(YELLOW)⚠ No running containers found$(NC)"

docker-clean: ## Remove Docker images and stopped containers
	@echo "$(BLUE)🧹 Cleaning Docker resources...$(NC)"
	docker rmi $(DOCKER_PROD_IMAGE) 2>/dev/null || true
	docker rmi $(DOCKER_DEV_IMAGE) 2>/dev/null || true
	docker system prune -f
	@echo "$(GREEN)✓ Docker cleanup complete$(NC)"

# ============================================================================
# CLEANING & MAINTENANCE
# ============================================================================

clean: ## Remove all generated files and caches
	@echo "$(BLUE)🧹 Cleaning project...$(NC)"
	@echo "  Removing: dist/, node_modules/, .vite/"
	rm -rf dist/
	rm -rf .vite/
	rm -rf coverage/
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

clean-all: clean docker-clean ## Deep clean: remove all generated files, caches, and Docker resources
	@echo "$(BLUE)🧹 Performing deep clean...$(NC)"
	@echo "  Keeping repo-root .env untouched (single source of truth)"
	@echo "$(GREEN)✓ Deep cleanup complete$(NC)"

reset: clean install ## Reset project to clean state (remove and reinstall dependencies)
	@echo "$(BLUE)🔄 Project reset complete$(NC)"
	@echo "$(YELLOW)ℹ Run 'make setup' to configure environment$(NC)"

# ============================================================================
# UTILITIES & DIAGNOSTICS
# ============================================================================

info: ## Display project information and environment details
	@echo "$(BLUE)ℹ️  Project Information$(NC)"
	@echo "  Name: $(PROJECT_NAME)"
	@echo "  Version: $(PROJECT_VERSION)"
	@echo "  Node version: $$(node --version)"
	@echo "  npm version: $$(npm --version)"
	@echo ""
	@echo "$(BLUE)📁 Directory Structure:$(NC)"
	@tree -L 2 -I 'node_modules|dist' 2>/dev/null || find . -maxdepth 2 -type d ! -path '*/\.*' ! -path '*/node_modules' ! -path '*/dist' | head -20
	@echo ""
	@echo "$(BLUE)📦 Key Dependencies:$(NC)"
	@grep -E '"react"|"vite"|"tailwindcss"|"zustand"' package.json | head -5

check-env: ## Verify environment configuration and dependencies
	@echo "$(BLUE)✓ Environment Check$(NC)"
	@echo ""
	@echo "$(BLUE)Checking Node.js and npm:$(NC)"
	@echo "  Node: $$(node --version)"
	@echo "  npm: $$(npm --version)"
	@echo ""
	@echo "$(BLUE)Checking repo-root .env configuration:$(NC)"
	@if [ -f ../.env ]; then \
		echo "  $(GREEN)✓ ../.env exists$(NC)"; \
		grep -E '^VITE_' ../.env || echo "  $(YELLOW)⚠ No VITE_ variables found$(NC)"; \
	else \
		echo "  $(YELLOW)⚠ ../.env not found - create the repo-root .env first$(NC)"; \
	fi
	@echo ""
	@echo "$(BLUE)Checking important files:$(NC)"
	@for file in vite.config.ts tsconfig.json package.json; do \
		if [ -f $$file ]; then \
			echo "  $(GREEN)✓$$file$(NC)"; \
		else \
			echo "  $(RED)✗$$file$(NC)"; \
		fi; \
	done
	@echo ""
	@echo "$(GREEN)✓ Environment check complete$(NC)"

deps: ## Display project dependencies
	@echo "$(BLUE)📦 Project Dependencies:$(NC)"
	npm list --depth=0

# ============================================================================
# ADVANCED TARGETS
# ============================================================================

test: ## Run tests (if configured)
	@echo "$(BLUE)🧪 Running tests...$(NC)"
	@if grep -q '"test"' package.json; then \
		npm run test; \
	else \
		echo "$(YELLOW)⚠ No test script configured in package.json$(NC)"; \
	fi

type-check: ## Run TypeScript type checking
	@echo "$(BLUE)🔍 Running TypeScript type check...$(NC)"
	npx tsc --noEmit
	@echo "$(GREEN)✓ Type checking complete - no errors$(NC)"

type-check-strict: ## Run strict TypeScript type checking with diagnostics
	@echo "$(BLUE)🔍 Running strict TypeScript type check...$(NC)"
	npx tsc --noEmit --listFilesOnly --diagnostics
	@echo "$(GREEN)✓ Strict type checking complete$(NC)"

all: clean install lint build ## Run full CI pipeline: clean, install, lint, and build
	@echo "$(GREEN)✓ Full build pipeline complete$(NC)"

ci: format-check lint type-check build ## Run CI checks: format, lint, type-check, and build
	@echo "$(BLUE)🔄 Running CI checks...$(NC)"
	@echo "$(GREEN)✓ All CI checks passed$(NC)"

# ============================================================================
# PHONY TARGETS (to avoid conflicts with actual files)
# ============================================================================

.PHONY: help install dev dev-debug build build-analyze preview lint lint-fix format format-check
.PHONY: docker-build docker-build-dev docker-run docker-run-dev docker-stop docker-logs docker-clean
.PHONY: clean clean-all reset info check-env deps test type-check type-check-strict all ci setup dev-env
