#!/bin/bash
# Development utilities script for dYdX Trading Bot Frontend
# Provides helpful commands for local development inside DevContainer

set -euo pipefail

COMMAND=${1:-help}

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║ dYdX Trading Bot Frontend - Dev Tools  ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
}

show_help() {
    print_header
    echo ""
    echo -e "${YELLOW}Usage: dev-tools [command]${NC}"
    echo ""
    echo "Available commands:"
    echo ""
    echo -e "${GREEN}dev-tools dev${NC}              Start development server"
    echo -e "${GREEN}dev-tools build${NC}            Build for production"
    echo -e "${GREEN}dev-tools lint${NC}             Run ESLint"
    echo -e "${GREEN}dev-tools lint:fix${NC}         Fix linting errors"
    echo -e "${GREEN}dev-tools clean${NC}            Clean build artifacts and cache"
    echo -e "${GREEN}dev-tools install${NC}          Install dependencies"
    echo -e "${GREEN}dev-tools status${NC}           Show development status"
    echo -e "${GREEN}dev-tools services${NC}         Show Docker services status"
    echo -e "${GREEN}dev-tools logs${NC}             Show Docker services logs"
    echo -e "${GREEN}dev-tools start-backend${NC}    Start backend and DB services"
    echo -e "${GREEN}dev-tools stop-backend${NC}     Stop backend and DB services"
    echo -e "${GREEN}dev-tools reset${NC}            Clean slate (warning: deletes data)"
    echo ""
}

cmd_dev() {
    echo -e "${BLUE}🚀 Starting development server...${NC}"
    npm run dev
}

cmd_build() {
    echo -e "${BLUE}🏗️  Building for production...${NC}"
    npm run build
}

cmd_lint() {
    echo -e "${BLUE}🔍 Running linter...${NC}"
    npm run lint
}

cmd_lint_fix() {
    echo -e "${BLUE}🔧 Fixing linting errors...${NC}"
    npm run lint -- --fix
}

cmd_clean() {
    echo -e "${BLUE}🧹 Cleaning build artifacts...${NC}"
    rm -rf dist/ .vite/
    rm -rf node_modules/.vite
    echo -e "${GREEN}✅ Cleaned${NC}"
}

cmd_install() {
    echo -e "${BLUE}📦 Installing dependencies...${NC}"
    npm install
    echo -e "${GREEN}✅ Dependencies installed${NC}"
}

cmd_status() {
    print_header
    echo ""
    echo -e "${YELLOW}📊 Project Status${NC}"
    echo ""

    echo "Node version: $(node --version)"
    echo "npm version: $(npm --version)"

    echo ""
    echo -e "${YELLOW}📁 Project Files${NC}"
    echo "  Source files: $(find src -type f -name '*.ts*' | wc -l) files"
    echo "  Components: $(find src/components -type f -name '*.tsx' | wc -l) components"
    echo "  Pages: $(find src/pages -type f -name '*.tsx' | wc -l) pages"

    echo ""
    echo -e "${YELLOW}📦 Dependencies${NC}"
    echo "  Total: $(npm ls --depth=0 2>/dev/null | grep -c '├\|└' || echo 'unknown')"

    if [ -f "dist/index.html" ]; then
        echo ""
        echo -e "${GREEN}✅ Production build exists${NC}"
    fi
}

cmd_services() {
    echo -e "${YELLOW}Docker Services Status${NC}"
    docker-compose ps || echo "No docker-compose services running"
}

cmd_logs() {
    echo -e "${YELLOW}Docker Services Logs (Ctrl+C to exit)${NC}"
    docker-compose logs -f
}

cmd_start_backend() {
    echo -e "${BLUE}🚀 Starting backend services...${NC}"
    docker-compose up -d db redis backend
    echo -e "${GREEN}✅ Backend services started${NC}"
    echo "  PostgreSQL: postgresql://postgres:postgres@localhost:5432/dydx_trading"
    echo "  Redis: redis://localhost:6379"
    echo "  Go Backend (legacy): http://localhost:8888"
    echo "  Bot API (default): http://localhost:8889"
}

cmd_stop_backend() {
    echo -e "${BLUE}⏹️  Stopping backend services...${NC}"
    docker-compose down
    echo -e "${GREEN}✅ Backend services stopped${NC}"
}

cmd_reset() {
    echo -e "${RED}⚠️  WARNING: This will delete all local data!${NC}"
    read -p "Are you sure? Type 'yes' to confirm: " confirm
    if [ "$confirm" = "yes" ]; then
        echo "Resetting project..."
        docker-compose down -v
        rm -rf dist/ node_modules/ .vite/
        npm cache clean --force
        npm install
        echo -e "${GREEN}✅ Project reset complete${NC}"
    else
        echo "Reset cancelled"
    fi
}

# Main command handler
case $COMMAND in
    dev)
        cmd_dev
        ;;
    build)
        cmd_build
        ;;
    lint)
        cmd_lint
        ;;
    lint:fix)
        cmd_lint_fix
        ;;
    clean)
        cmd_clean
        ;;
    install)
        cmd_install
        ;;
    status)
        cmd_status
        ;;
    services)
        cmd_services
        ;;
    logs)
        cmd_logs
        ;;
    start-backend)
        cmd_start_backend
        ;;
    stop-backend)
        cmd_stop_backend
        ;;
    reset)
        cmd_reset
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $COMMAND${NC}"
        show_help
        exit 1
        ;;
esac
