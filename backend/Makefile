# Makefile for dYdX Trading Bot Backend

.PHONY: help help-check build run test clean lint fmt vet install-tools docker-build docker-run migrate-up migrate-down dev dev-env tasks-summary tasks-validate tasks-governance

# Variables
BINARY_NAME=dydx-bot
MAIN_PATH=./cmd/server
GO=go
GOFLAGS=-v
GOLANGCI_LINT=golangci-lint
MIGRATE=migrate
DOCKER_IMAGE=dydx-trading-bot
DOCKER_TAG=latest
MODE ?= development

# Colors for output
CYAN=\033[0;36m
GREEN=\033[0;32m
RED=\033[0;31m
NC=\033[0m # No Color

## help: Display this help message
help:
	@echo "$(CYAN)dYdX Trading Bot - Available Commands:$(NC)"
	@echo ""
	@awk '/^## / { \
		line = $$0; \
		sub(/^## /, "", line); \
		sep = index(line, ":"); \
		if (sep > 0) { \
			cmd = substr(line, 1, sep - 1); \
			desc = substr(line, sep + 2); \
			gsub(/\r/, "", desc); \
			printf "  %-16s %s\n", cmd, desc; \
		} \
	}' $(MAKEFILE_LIST)
	@echo ""

## help-check: Validate Makefile help metadata format
help-check:
	@echo "$(CYAN)Validating Makefile help metadata...$(NC)"
	@awk 'BEGIN { ok = 1 } \
		/^## / { \
			line = $$0; \
			sub(/^## /, "", line); \
			sep = index(line, ":"); \
			if (sep == 0) { \
				printf "Invalid help entry (missing colon): %s\n", $$0; \
				ok = 0; \
				next; \
			} \
			cmd = substr(line, 1, sep - 1); \
			if (cmd !~ /^[A-Za-z0-9_.-]+$$/) { \
				printf "Invalid help command token '%s' in line: %s\n", cmd, $$0; \
				ok = 0; \
			} \
		} \
		END { \
			if (!ok) { \
				exit 1; \
			} \
		}' $(MAKEFILE_LIST)
	@echo "$(GREEN)✓ Help metadata looks good$(NC)"

## build: Build the application binary
build:
	@echo "$(CYAN)Building application...$(NC)"
	$(GO) build $(GOFLAGS) -o bin/$(BINARY_NAME) $(MAIN_PATH)
	@echo "$(GREEN)✓ Build complete: bin/$(BINARY_NAME)$(NC)"

## run: Run the application
run:
	@echo "$(CYAN)Running application...$(NC)"
	$(GO) run $(MAIN_PATH)/main.go

## dev: Run application with auto-reload (requires air)
dev:
	@echo "$(CYAN)Running in development mode with hot-reload...$(NC)"
	@if command -v air > /dev/null; then \
		air; \
	else \
		echo "$(RED)air not installed. Run: make install-tools$(NC)"; \
		exit 1; \
	fi

## dev-env: Deprecated: backend now reads config/profiles directly
dev-env:
	@echo "$(YELLOW)⚠ dev-env is deprecated. Use make dev-config or make prod-config from repo root.$(NC)"

## test: Run all tests
test:
	@echo "$(CYAN)Running tests...$(NC)"
	$(GO) test -v -race -coverprofile=coverage.out ./...
	@echo "$(GREEN)✓ Tests complete$(NC)"

## test-coverage: Run tests and show coverage report
test-coverage: test
	@echo "$(CYAN)Generating coverage report...$(NC)"
	$(GO) tool cover -html=coverage.out -o coverage.html
	@echo "$(GREEN)✓ Coverage report: coverage.html$(NC)"

## bench: Run benchmarks
bench:
	@echo "$(CYAN)Running benchmarks...$(NC)"
	$(GO) test -bench=. -benchmem ./...

## lint: Run golangci-lint
lint:
	@echo "$(CYAN)Running linter...$(NC)"
	@if command -v $(GOLANGCI_LINT) > /dev/null; then \
		$(GOLANGCI_LINT) run --config .golangci.yml ./...; \
		echo "$(GREEN)✓ Linting complete$(NC)"; \
	else \
		echo "$(RED)golangci-lint not installed. Run: make install-tools$(NC)"; \
		exit 1; \
	fi

## lint-fix: Run golangci-lint and auto-fix issues
lint-fix:
	@echo "$(CYAN)Running linter with auto-fix...$(NC)"
	@if command -v $(GOLANGCI_LINT) > /dev/null; then \
		$(GOLANGCI_LINT) run --config .golangci.yml --fix ./...; \
		echo "$(GREEN)✓ Linting with fixes complete$(NC)"; \
	else \
		echo "$(RED)golangci-lint not installed. Run: make install-tools$(NC)"; \
		exit 1; \
	fi

## fmt: Format code with gofmt
fmt:
	@echo "$(CYAN)Formatting code...$(NC)"
	$(GO) fmt ./...
	@echo "$(GREEN)✓ Formatting complete$(NC)"

## vet: Run go vet
vet:
	@echo "$(CYAN)Running go vet...$(NC)"
	$(GO) vet ./...
	@echo "$(GREEN)✓ Vet complete$(NC)"

## tidy: Tidy up go.mod and go.sum
tidy:
	@echo "$(CYAN)Tidying dependencies...$(NC)"
	$(GO) mod tidy
	@echo "$(GREEN)✓ Dependencies tidied$(NC)"

## clean: Clean build artifacts and caches
clean:
	@echo "$(CYAN)Cleaning...$(NC)"
	rm -rf bin/
	rm -f coverage.out coverage.html
	$(GO) clean -cache -testcache -modcache
	@echo "$(GREEN)✓ Clean complete$(NC)"

## install-tools: Install development tools
install-tools:
	@echo "$(CYAN)Installing development tools...$(NC)"
	@echo "Installing golangci-lint..."
	@if ! command -v golangci-lint > /dev/null; then \
		curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | sh -s -- -b $$(go env GOPATH)/bin v1.55.2; \
	fi
	@echo "Installing air (hot reload)..."
	@if ! command -v air > /dev/null; then \
		go install github.com/air-verse/air@v1.61.7; \
	fi
	@echo "Installing golang-migrate..."
	@if ! command -v migrate > /dev/null; then \
		go install -tags 'postgres sqlite3' github.com/golang-migrate/migrate/v4/cmd/migrate@v4.19.0; \
	fi
	@echo "Installing mockgen..."
	@if ! command -v mockgen > /dev/null; then \
		go install github.com/golang/mock/mockgen@v1.6.0; \
	fi
	@echo "$(GREEN)✓ Tools installed$(NC)"

## migrate-up: Run database migrations up
migrate-up:
	@echo "$(CYAN)Running migrations up...$(NC)"
	@if [ -z "$$DB_TYPE" ]; then \
		echo "$(RED)DB_TYPE not set. Defaulting to sqlite3$(NC)"; \
		export DB_TYPE=sqlite3; \
	fi; \
	if [ "$$DB_TYPE" = "sqlite3" ]; then \
		$(MIGRATE) -path migrations -database "sqlite3://trading_bot.db" up; \
	else \
		$(MIGRATE) -path migrations -database "$$DATABASE_URL" up; \
	fi
	@echo "$(GREEN)✓ Migrations complete$(NC)"

## migrate-down: Rollback database migrations
migrate-down:
	@echo "$(CYAN)Rolling back migrations...$(NC)"
	@if [ -z "$$DB_TYPE" ]; then \
		echo "$(RED)DB_TYPE not set. Defaulting to sqlite3$(NC)"; \
		export DB_TYPE=sqlite3; \
	fi; \
	if [ "$$DB_TYPE" = "sqlite3" ]; then \
		$(MIGRATE) -path migrations -database "sqlite3://trading_bot.db" down 1; \
	else \
		$(MIGRATE) -path migrations -database "$$DATABASE_URL" down 1; \
	fi
	@echo "$(GREEN)✓ Rollback complete$(NC)"

## migrate-create: Create new migration file (usage: make migrate-create NAME=migration_name)
migrate-create:
	@if [ -z "$(NAME)" ]; then \
		echo "$(RED)Please provide NAME variable: make migrate-create NAME=your_migration_name$(NC)"; \
		exit 1; \
	fi
	@echo "$(CYAN)Creating migration: $(NAME)...$(NC)"
	$(MIGRATE) create -ext sql -dir migrations -seq $(NAME)
	@echo "$(GREEN)✓ Migration files created$(NC)"

## tasks-summary: Recompute Completed/Pending summary counts in backend/bot/frontend tasks.md files
tasks-summary:
	@echo "$(CYAN)Updating task status summaries...$(NC)"
	@python3 scripts/update_task_summary.py
	@echo "$(GREEN)✓ Task status summaries updated$(NC)"

## tasks-validate: Validate cross-service task governance consistency
tasks-validate:
	@echo "$(CYAN)Validating task governance...$(NC)"
	@python3 scripts/validate_task_governance.py
	@echo "$(GREEN)✓ Task governance validation passed$(NC)"

## tasks-governance: Update and validate cross-service task governance
tasks-governance: tasks-summary tasks-validate
	@echo "$(GREEN)✓ Task governance update + validation complete$(NC)"

## docker-build: Build Docker image
docker-build:
	@echo "$(CYAN)Building Docker image...$(NC)"
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .
	@echo "$(GREEN)✓ Docker image built$(NC)"

## docker-run: Run application in Docker
docker-run:
	@echo "$(CYAN)Running Docker container...$(NC)"
	docker run -p 8888:8888 \
		-e APP_CONFIG_ENV=$(MODE) \
		-v $(PWD)/../config:/app/config:ro \
		$(DOCKER_IMAGE):$(DOCKER_TAG)

## deps: Download dependencies
deps:
	@echo "$(CYAN)Downloading dependencies...$(NC)"
	$(GO) mod download
	@echo "$(GREEN)✓ Dependencies downloaded$(NC)"

## verify: Run all verification checks (fmt, vet, lint, test)
verify: fmt vet lint test
	@echo "$(GREEN)✓ All verification checks passed$(NC)"

## security: Run security checks with gosec
security:
	@echo "$(CYAN)Running security checks...$(NC)"
	@if command -v gosec > /dev/null; then \
		gosec -fmt=json -out=gosec-report.json ./...; \
		echo "$(GREEN)✓ Security scan complete: gosec-report.json$(NC)"; \
	else \
		echo "$(RED)gosec not installed. Installing...$(NC)"; \
		go install github.com/securego/gosec/v2/cmd/gosec@latest; \
		gosec -fmt=json -out=gosec-report.json ./...; \
	fi

## mock: Generate mocks for interfaces
mock:
	@echo "$(CYAN)Generating mocks...$(NC)"
	@if command -v mockgen > /dev/null; then \
		go generate ./...; \
		echo "$(GREEN)✓ Mocks generated$(NC)"; \
	else \
		echo "$(RED)mockgen not installed. Run: make install-tools$(NC)"; \
		exit 1; \
	fi

## check: Quick check (fmt + vet + build)
check: fmt vet build
	@echo "$(GREEN)✓ Quick check passed$(NC)"

## all: Run full build pipeline
all: clean deps verify build
	@echo "$(GREEN)✓ Full build complete$(NC)"

.DEFAULT_GOAL := help
