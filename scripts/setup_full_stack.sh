#!/bin/bash

# dYdX Backtest System - Setup Script
# Initializes the complete full-stack system

set -e

echo "🚀 dYdX Backtest System Setup"
echo "=============================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
check_prerequisites() {
    echo "${BLUE}Checking prerequisites...${NC}"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo "${YELLOW}Docker not found. Please install Docker.${NC}"
        exit 1
    fi
    echo "✓ Docker found: $(docker --version)"
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo "${YELLOW}Docker Compose not found. Please install Docker Compose.${NC}"
        exit 1
    fi
    echo "✓ Docker Compose found: $(docker-compose --version)"
    
    echo ""
}

# Create environment files
setup_env_files() {
    echo "${BLUE}Setting up environment files...${NC}"
    
    # Shared repo-root .env
    if [ ! -f .env ]; then
        cat > .env << EOF
# Shared monorepo environment
ENVIRONMENT=development
POSTGRES_PORT=5432
REDIS_PORT=6379
API_PORT=8888
POSTGRES_USER=dydx_bot
POSTGRES_PASSWORD=change-me-db-password
POSTGRES_DB=dydx_bot
SECRET_KEY=change-me-jwt-secret-min-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
DB_TYPE=postgres
DB_HOST=postgres
DB_PORT=5432
DB_NAME=dydx_bot
DB_USER=dydx_bot
DB_PASSWORD=change-me-db-password
REDIS_ENABLED=true
REDIS_HOST=localhost
REDIS_DB=0
BOT_API_URL=http://localhost:8889
BOT_API_HOST=0.0.0.0
BOT_API_PORT=8889
VITE_API_URL=http://localhost:8888
EOF
        echo "✓ Created .env"
    else
        echo "✓ .env already exists"
    fi

    echo "✓ Backend, bot, and frontend all use the repo-root .env"
    
    echo ""
}

# Build Docker images
build_images() {
    echo "${BLUE}Building Docker images...${NC}"
    
    docker-compose -f docker-compose.full-stack.yml build --no-cache
    
    echo "✓ Docker images built successfully"
    echo ""
}

# Start services
start_services() {
    echo "${BLUE}Starting services...${NC}"
    
    docker-compose -f docker-compose.full-stack.yml up -d
    
    echo "✓ Services started"
    echo ""
}

# Wait for services
wait_for_services() {
    echo "${BLUE}Waiting for services to be ready...${NC}"
    
    # Wait for backend
    echo "Waiting for backend..."
    for i in {1..30}; do
        if curl -f http://localhost:8000/health 2>/dev/null; then
            echo "✓ Backend is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "❌ Backend failed to start"
            exit 1
        fi
        sleep 1
    done
    
    # Wait for frontend
    echo "Waiting for frontend..."
    for i in {1..30}; do
        if curl -f http://localhost:3000 2>/dev/null || curl -f http://localhost:5173 2>/dev/null; then
            echo "✓ Frontend is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "❌ Frontend failed to start"
            exit 1
        fi
        sleep 1
    done
    
    echo ""
}

# Display endpoints
show_endpoints() {
    echo "${GREEN}✅ Setup Complete!${NC}"
    echo ""
    echo "Endpoints:"
    echo "  🌐 Frontend:   ${GREEN}http://localhost:3000${NC} (or http://localhost:5173 for dev)"
    echo "  🔌 Backend API: ${GREEN}http://localhost:8000${NC}"
    echo "  📚 API Docs:   ${GREEN}http://localhost:8000/docs${NC}"
    echo "  💾 Database:   ${GREEN}postgres://postgres:password@localhost:5432/dydx_backtest${NC}"
    echo "  🔴 Redis:      ${GREEN}redis://localhost:6379${NC}"
    echo ""
    echo "Default Login:"
    echo "  Username: ${GREEN}admin${NC}"
    echo "  Password: ${GREEN}password${NC}"
    echo ""
    echo "Useful Commands:"
    echo "  • View logs:        ${YELLOW}docker-compose -f docker-compose.full-stack.yml logs -f${NC}"
    echo "  • Stop services:    ${YELLOW}docker-compose -f docker-compose.full-stack.yml down${NC}"
    echo "  • Reset database:   ${YELLOW}docker-compose -f docker-compose.full-stack.yml down -v${NC}"
    echo "  • Restart services: ${YELLOW}docker-compose -f docker-compose.full-stack.yml restart${NC}"
    echo ""
}

# Main execution
main() {
    check_prerequisites
    setup_env_files
    build_images
    start_services
    wait_for_services
    show_endpoints
}

main
