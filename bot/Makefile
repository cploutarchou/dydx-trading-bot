# dYdX Trading Bot - Dev Container Makefile

.PHONY: help build up down logs shell restart clean test format lint type-check

CONTAINER_NAME := dydx-bot-dev
DOCKER_COMPOSE := docker-compose -f .devcontainer/docker-compose.yml

help:
	@echo "dYdX Trading Bot - Development Commands"
	@echo ""
	@echo "Setup & Initialization:"
	@echo "  make build              Build development container"
	@echo "  make up                 Start all services"
	@echo "  make down               Stop all services"
	@echo "  make init               Initialize database and install deps"
	@echo ""
	@echo "Container Management:"
	@echo "  make shell              Open shell in dev container"
	@echo "  make logs               View container logs"
	@echo "  make restart            Restart all services"
	@echo "  make clean              Remove containers and volumes"
	@echo ""
	@echo "Development:"
	@echo "  make test               Run pytest"
	@echo "  make test-cov           Run pytest with coverage"
	@echo "  make format             Format code with black"
	@echo "  make lint               Run ruff linter"
	@echo "  make type-check         Run mypy type checking"
	@echo "  make check              Run all checks (lint, format, type)"
	@echo ""
	@echo "Bot Management:"
	@echo "  make api                Start API server"
	@echo "  make bot                Start bot"
	@echo "  make migrate            Run database migrations"
	@echo ""
	@echo "Database:"
	@echo "  make db-shell           Open PostgreSQL shell"
	@echo "  make db-reset           Reset database"
	@echo "  make redis-shell        Open Redis CLI"
	@echo ""
	@echo "Utilities:"
	@echo "  make install-deps       Install project dependencies"
	@echo "  make install-dev        Install development dependencies"
	@echo "  make jupyter            Start Jupyter Lab"

## Setup & Initialization

build:
	@echo "Building development container..."
	$(DOCKER_COMPOSE) build

up:
	@echo "Starting development environment..."
	$(DOCKER_COMPOSE) up -d
	@echo "✅ Services started"
	@echo "   API: http://localhost:8889"
	@echo "   Postgres: localhost:5432"
	@echo "   Redis: localhost:6379"
	@echo "   pgAdmin: http://localhost:5050"
	@echo "   Redis Commander: http://localhost:8081"

down:
	@echo "Stopping development environment..."
	$(DOCKER_COMPOSE) down

init: up
	@echo "Initializing development environment..."
	$(DOCKER_COMPOSE) exec dev bash .devcontainer/post-create.sh
	@echo "✅ Initialization complete"

restart:
	@echo "Restarting services..."
	$(DOCKER_COMPOSE) restart
	@echo "✅ Services restarted"

logs:
	$(DOCKER_COMPOSE) logs -f

shell:
	$(DOCKER_COMPOSE) exec dev bash

clean:
	@echo "Cleaning up containers and volumes..."
	$(DOCKER_COMPOSE) down -v
	@echo "✅ Cleanup complete"

## Development

test:
	$(DOCKER_COMPOSE) exec dev pytest -v

test-cov:
	$(DOCKER_COMPOSE) exec dev pytest --cov --cov-report=html --cov-report=term

format:
	$(DOCKER_COMPOSE) exec dev black .

lint:
	$(DOCKER_COMPOSE) exec dev ruff check . --fix

type-check:
	$(DOCKER_COMPOSE) exec dev mypy . --ignore-missing-imports

check: format lint type-check
	@echo "✅ All checks passed"

## Bot Management

api:
	$(DOCKER_COMPOSE) exec dev python bot_api_server.py

bot:
	$(DOCKER_COMPOSE) exec dev python main.py

migrate:
	$(DOCKER_COMPOSE) exec dev alembic upgrade head

## Database

db-shell:
	$(DOCKER_COMPOSE) exec postgres psql -U postgres -d dydx_bot

db-reset:
	@echo "Resetting database..."
	$(DOCKER_COMPOSE) exec postgres psql -U postgres -d dydx_bot -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	@echo "Running migrations..."
	$(DOCKER_COMPOSE) exec dev alembic upgrade head
	@echo "✅ Database reset complete"

redis-shell:
	$(DOCKER_COMPOSE) exec redis redis-cli

## Utilities

install-deps:
	$(DOCKER_COMPOSE) exec dev pip install -r requirements.txt

install-dev:
	$(DOCKER_COMPOSE) exec dev pip install \
		pytest==7.4.3 \
		pytest-cov==4.1.0 \
		pytest-asyncio==0.21.1 \
		black==23.12.1 \
		ruff==0.1.11 \
		mypy==1.7.1 \
		jupyter==1.0.0 \
		jupyterlab==4.0.9

jupyter:
	$(DOCKER_COMPOSE) exec dev jupyter lab --ip=0.0.0.0 --no-browser

# Phony targets
.PHONY: $(MAKECMDGOALS)
