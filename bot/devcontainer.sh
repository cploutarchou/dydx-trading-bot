#!/bin/bash
# Dev Container Helper Script - Quick commands for common tasks

set -e

DOCKER_COMPOSE="docker-compose -f .devcontainer/docker-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✅${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}❌${NC} $1"
}

# Check Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    
    log_success "Docker is available"
}

# Show status
status() {
    log_info "Checking development environment status..."
    $DOCKER_COMPOSE ps
}

# Start services
start() {
    log_info "Starting development environment..."
    $DOCKER_COMPOSE up -d
    log_success "Services started"
    
    log_info "Waiting for services to be ready..."
    sleep 5
    
    log_info "Service endpoints:"
    log_info "  API Server: http://localhost:8889"
    log_info "  API Docs: http://localhost:8889/docs"
    log_info "  PostgreSQL: localhost:5432"
    log_info "  Redis: localhost:6379"
    log_info "  pgAdmin: http://localhost:5050"
    log_info "  Redis Commander: http://localhost:8081"
}

# Stop services
stop() {
    log_info "Stopping development environment..."
    $DOCKER_COMPOSE down
    log_success "Services stopped"
}

# Reset everything
reset() {
    log_warning "This will remove all containers and volumes"
    read -p "Are you sure? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Resetting development environment..."
        $DOCKER_COMPOSE down -v
        log_success "Environment reset"
    fi
}

# View logs
logs() {
    $DOCKER_COMPOSE logs -f "$@"
}

# Execute command in container
exec_cmd() {
    $DOCKER_COMPOSE exec dev "$@"
}

# Shell access
shell() {
    log_info "Opening shell in dev container..."
    $DOCKER_COMPOSE exec dev bash
}

# Run tests
run_tests() {
    log_info "Running tests..."
    $DOCKER_COMPOSE exec dev pytest "$@"
}

# Format code
format() {
    log_info "Formatting code..."
    $DOCKER_COMPOSE exec dev black .
    log_success "Code formatted"
}

# Lint code
lint() {
    log_info "Running linter..."
    $DOCKER_COMPOSE exec dev ruff check . --fix
    log_success "Linting complete"
}

# Type checking
typecheck() {
    log_info "Running type checker..."
    $DOCKER_COMPOSE exec dev mypy . --ignore-missing-imports
    log_success "Type checking complete"
}

# All checks
check() {
    format
    lint
    typecheck
    log_success "All checks passed"
}

# Start API
start_api() {
    log_info "Starting API server..."
    $DOCKER_COMPOSE exec dev python start_api.py
}

# Start bot
start_bot() {
    log_info "Starting bot..."
    $DOCKER_COMPOSE exec dev python main.py
}

# Database operations
db_shell() {
    log_info "Opening PostgreSQL shell..."
    $DOCKER_COMPOSE exec postgres psql -U postgres -d dydx_bot
}

db_reset() {
    log_warning "This will reset the database"
    read -p "Are you sure? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Resetting database..."
        $DOCKER_COMPOSE exec postgres psql -U postgres -d dydx_bot -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
        log_info "Running migrations..."
        $DOCKER_COMPOSE exec dev alembic upgrade head
        log_success "Database reset complete"
    fi
}

# Redis operations
redis_shell() {
    log_info "Opening Redis CLI..."
    $DOCKER_COMPOSE exec redis redis-cli
}

# Help
show_help() {
    cat << EOF
dYdX Trading Bot - Dev Container Helper

Usage: $0 <command> [options]

Commands:
  check               Check Docker installation
  status              Show service status
  start               Start all services
  stop                Stop all services
  reset               Reset all services and volumes
  shell               Open shell in dev container
  logs [service]      View service logs (default: all)
  exec <cmd>          Execute command in dev container
  
  test [options]      Run pytest
  format              Format code with black
  lint                Run ruff linter
  typecheck           Run mypy type checker
  check               Run all checks (format, lint, typecheck)
  
  api                 Start API server
  bot                 Start bot
  
  db-shell            Open PostgreSQL shell
  db-reset            Reset database
  redis-shell         Open Redis CLI
  
  help                Show this help message

Examples:
  $0 start                    # Start development environment
  $0 shell                    # Open shell in container
  $0 test -v                  # Run tests with verbose output
  $0 format                   # Format code
  $0 check                    # Run all checks
  $0 exec python main.py      # Run bot
  $0 logs dev                 # View dev container logs

EOF
}

# Main script logic
main() {
    case "${1:-help}" in
        check)
            check_docker
            ;;
        status)
            status
            ;;
        start)
            check_docker
            start
            ;;
        stop)
            stop
            ;;
        reset)
            reset
            ;;
        shell)
            shell
            ;;
        logs)
            logs "${@:2}"
            ;;
        exec)
            exec_cmd "${@:2}"
            ;;
        test)
            run_tests "${@:2}"
            ;;
        format)
            format
            ;;
        lint)
            lint
            ;;
        typecheck)
            typecheck
            ;;
        check-all)
            check
            ;;
        api)
            start_api
            ;;
        bot)
            start_bot
            ;;
        db-shell)
            db_shell
            ;;
        db-reset)
            db_reset
            ;;
        redis-shell)
            redis_shell
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
