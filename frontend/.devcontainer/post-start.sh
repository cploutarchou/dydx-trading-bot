#!/bin/bash
# DevContainer Post-Start Script
# Runs every time the container starts (after post-create)
# Handles runtime setup like starting services or background tasks

set -euo pipefail

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
MAGENTA='\033[0;35m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_section() {
    echo ""
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}${1}${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Main start routine
log_section "🚀 Container Started - Preparing Environment"

# 1. Verify environment
log_info "Verifying Node environment..."
node --version || echo "Node not found"
npm --version || echo "npm not found"
log_success "Environment verified"

# 2. Check if dependencies are installed
if [ ! -d "node_modules" ]; then
    log_info "Dependencies not found, installing..."
    if npm install --prefer-offline --no-audit 2>&1; then
        log_success "Dependencies installed"
    else
        log_info "Dependencies installation had issues but continuing..."
    fi
else
    log_success "Dependencies already installed"
fi

# 3. Load shell aliases
if [ -f ~/.bashrc ]; then
    log_info "Loading shell configuration..."
    source ~/.bashrc
    log_success "Shell configuration loaded"
fi

# 4. Display quick reference
log_section "💡 Quick Reference"
echo -e "${YELLOW}Start Development:${NC}"
echo -e "  ${BLUE}npm run dev${NC} or ${BLUE}dev${NC}"
echo ""
echo -e "${YELLOW}Common Commands:${NC}"
echo -e "  ${BLUE}build${NC}      - Build for production"
echo -e "  ${BLUE}lint${NC}       - Run ESLint"
echo -e "  ${BLUE}lint-fix${NC}   - Fix linting errors"
echo -e "  ${BLUE}start-api${NC}  - Start backend services"
echo ""
echo -e "${YELLOW}Access Points:${NC}"
echo -e "  Dev Server:  ${BLUE}http://localhost:5173${NC}"
echo -e "  Preview:     ${BLUE}http://localhost:3000${NC}"
echo -e "  Backend API: ${BLUE}http://localhost:8888${NC}"
echo ""
echo -e "${GREEN}Ready to start development!${NC}"
