# Makefile for dYdX Trading Bot Backend

.PHONY: help build run test clean lint fmt vet install-tools docker-build docker-run migrate-up migrate-down dev

# Variables
BINARY_NAME=dydx-bot
MAIN_PATH=./cmd/server
GO=go
GOFLAGS=-v
GOLANGCI_LINT=golangci-lint
MIGRATE=migrate
DOCKER_IMAGE=dydx-trading-bot
DOCKER_TAG=latest

# Colors for output
CYAN=\033[0;36m
GREEN=\033[0;32m
RED=\033[0;31m
NC=\033[0m # No Color

## help: Display this help message
help:
	@echo "$(CYAN)dYdX Trading Bot - Available Commands:$(NC)"
	@echo ""
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## /  /' | column -t -s ':' | sed 's/^/  /'
	@echo ""

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
		go install github.com/air-verse/air@latest; \
	fi
	@echo "Installing golang-migrate..."
	@if ! command -v migrate > /dev/null; then \
		go install -tags 'postgres sqlite3' github.com/golang-migrate/migrate/v4/cmd/migrate@latest; \
	fi
	@echo "Installing mockgen..."
	@if ! command -v mockgen > /dev/null; then \
		go install github.com/golang/mock/mockgen@latest; \
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

## docker-build: Build Docker image
docker-build:
	@echo "$(CYAN)Building Docker image...$(NC)"
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .
	@echo "$(GREEN)✓ Docker image built$(NC)"

## docker-run: Run application in Docker
docker-run:
	@echo "$(CYAN)Running Docker container...$(NC)"
	docker run -p 8888:8888 --env-file .env $(DOCKER_IMAGE):$(DOCKER_TAG)

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
