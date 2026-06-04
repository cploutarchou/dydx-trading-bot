#!/bin/bash

# dYdX Trading Bot - Development Start Script
# Starts backend, frontend, and database services with hot-reload

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PROJECT_ROOT="/workspaces/dydx-trading-bot"
PYTHON_VENV="$PROJECT_ROOT/venv"

# Banner
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║   dYdX Trading Bot - Development Mode                      ║"
echo "║   Backend + Frontend + Database (Hot-Reload Enabled)       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "${YELLOW}Cleaning up...${NC}"
    # Kill background processes
    jobs -p | xargs -r kill 2>/dev/null || true
    echo "${GREEN}✓ Cleanup complete${NC}"
}

trap cleanup EXIT

# Check prerequisites
check_prerequisites() {
    echo "${BLUE}[1/6] Checking prerequisites...${NC}"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo "${RED}✗ Docker not found. Please install Docker.${NC}"
        exit 1
    fi
    echo "  ✓ Docker found"
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo "${RED}✗ Docker Compose not found. Please install Docker Compose.${NC}"
        exit 1
    fi
    echo "  ✓ Docker Compose found"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo "${RED}✗ Python 3 not found. Please install Python 3.${NC}"
        exit 1
    fi
    echo "  ✓ Python 3 found: $(python3 --version)"
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        echo "${RED}✗ Node.js not found. Please install Node.js.${NC}"
        exit 1
    fi
    echo "  ✓ Node.js found: $(node --version)"
    
    echo ""
}

# Setup Python virtual environment
setup_python_env() {
    echo "${BLUE}[2/6] Setting up Python environment...${NC}"
    
    if [ ! -d "$PYTHON_VENV" ]; then
        echo "  Creating virtual environment..."
        python3 -m venv "$PYTHON_VENV"
        echo "  ✓ Virtual environment created"
    else
        echo "  ✓ Virtual environment already exists"
    fi
    
    # Activate venv
    source "$PYTHON_VENV/bin/activate"
    
    # Install dependencies
    echo "  Installing backend dependencies..."
    pip install -q -r "$PROJECT_ROOT/backend/requirements.txt"
    echo "  ✓ Dependencies installed"
    
    echo ""
}

# Validate structured config files
setup_env_files() {
    echo "${BLUE}[3/6] Checking structured config...${NC}"

    if [ ! -f "$PROJECT_ROOT/run.json" ]; then
        echo "${YELLOW}  run.json not found. Generating it with 'make dev'...${NC}"
        (cd "$PROJECT_ROOT" && PATH="$HOME/.local/bin:$PATH" make dev) || {
            echo "${RED}  ✗ Failed to generate run.json${NC}"
            exit 1
        }
    fi

    if [ ! -f "$PROJECT_ROOT/run.json" ]; then
        echo "${RED}  ✗ Missing $PROJECT_ROOT/run.json${NC}"
        exit 1
    fi

    if ! python3 "$PROJECT_ROOT/scripts/validate_stack_env.py" --environment development >/dev/null; then
        echo "${RED}  ✗ Structured config validation failed${NC}"
        echo "${YELLOW}  Run 'make dev-config' and then 'make dev' from the repo root.${NC}"
        exit 1
    fi

    echo "  ✓ Structured config is valid"
    echo "  ✓ Backend, bot, and frontend will load from run.json"
    echo ""
}

# Start Docker containers (PostgreSQL & Redis)
start_docker_services() {
    echo "${BLUE}[4/6] Starting Docker services (PostgreSQL & Redis)...${NC}"
    
    # Check if already running
    if docker ps | grep -q dydx_backtest_db; then
        echo "  ✓ PostgreSQL already running"
    else
        echo "  Starting PostgreSQL and Redis..."
        cd "$PROJECT_ROOT"
        docker-compose -f docker-compose.full-stack.yml up -d postgres redis
        
        # Wait for PostgreSQL to be ready
        echo "  Waiting for PostgreSQL to be ready..."
        for i in {1..30}; do
            if docker exec dydx_backtest_db pg_isready -U postgres &> /dev/null; then
                echo "  ✓ PostgreSQL is ready"
                break
            fi
            if [ $i -eq 30 ]; then
                echo "${RED}  ✗ PostgreSQL failed to start${NC}"
                exit 1
            fi
            sleep 1
        done
    fi
    
    echo ""
}

# Start backend
start_backend() {
    echo "${BLUE}[5/6] Starting Backend Server...${NC}"
    
    cd "$PROJECT_ROOT"
    source "$PYTHON_VENV/bin/activate"
    export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
    
    echo "  🚀 Backend starting on http://localhost:8000"
    echo "  📚 API Docs on http://localhost:8000/docs"
    echo "  🔄 Hot-reload enabled (changes auto-detected)"
    echo ""
    
    # Run backend in background
    uvicorn backend.main:app \
        --reload \
        --host 0.0.0.0 \
        --port 8000 \
        --log-level info &
    
    BACKEND_PID=$!
    echo "  ✓ Backend PID: $BACKEND_PID"
    
    # Wait for backend to be ready
    echo "  Waiting for backend to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "  ✓ Backend is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "${RED}  ✗ Backend failed to start${NC}"
            exit 1
        fi
        sleep 1
    done
    
    echo ""
}

# Start frontend
start_frontend() {
    echo "${BLUE}[6/6] Starting Frontend Server...${NC}"
    
    cd "$PROJECT_ROOT/frontend"
    
    # Check/install node modules
    if [ ! -d "node_modules" ]; then
        echo "  Installing Node dependencies..."
        npm install -q
        echo "  ✓ Dependencies installed"
    else
        echo "  ✓ Node modules already exist"
    fi
    
    echo "  🚀 Frontend starting on http://localhost:5173"
    echo "  🔄 Hot Module Replacement (HMR) enabled"
    echo ""
    
    # Run frontend in background
    npm run dev &
    
    FRONTEND_PID=$!
    echo "  ✓ Frontend PID: $FRONTEND_PID"
    
    echo ""
}

# Show final info
show_final_info() {
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           ${GREEN}✅ DEVELOPMENT ENVIRONMENT READY!${NC}                    ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "${GREEN}Access Points:${NC}"
    echo "  🌐 Frontend:    http://localhost:5173"
    echo "  🔌 Backend:     http://localhost:8000"
    echo "  📚 API Docs:    http://localhost:8000/docs"
    echo "  💾 Database:    postgresql://localhost:5432/dydx_backtest"
    echo "  🔴 Redis:       redis://localhost:6379"
    echo ""
    echo "${GREEN}Login Credentials:${NC}"
    echo "  Email:    admin@executionlab.io"
    echo "  Password: password"
    echo ""
    echo "${GREEN}Features Enabled:${NC}"
    echo "  ✓ Backend auto-reload on file changes"
    echo "  ✓ Frontend Hot Module Replacement (HMR)"
    echo "  ✓ API interactive documentation"
    echo "  ✓ Full debug logging"
    echo ""
    echo "${YELLOW}To Stop All Services:${NC}"
    echo "  Press Ctrl+C to stop this script"
    echo ""
    echo "${YELLOW}Useful Commands:${NC}"
    echo "  • View backend logs:     tail -f /tmp/backend.log"
    echo "  • View frontend logs:    tail -f /tmp/frontend.log"
    echo "  • Reset database:        docker-compose down -v && docker-compose up postgres redis"
    echo "  • Test API endpoint:     curl http://localhost:8000/health"
    echo ""
    echo "${BLUE}Development workflow:${NC}"
    echo "  1. Edit backend/*.py or frontend/src/*.tsx files"
    echo "  2. Save the file"
    echo "  3. Changes auto-reload in browser"
    echo "  4. Check console for errors"
    echo ""
    echo "Happy coding! 🎉"
    echo ""
}

# Main execution
main() {
    check_prerequisites
    setup_python_env
    setup_env_files
    start_docker_services
    start_backend
    start_frontend
    show_final_info
    
    # Keep running until Ctrl+C
    wait
}

# Run main
main
