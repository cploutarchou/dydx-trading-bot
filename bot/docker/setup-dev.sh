#!/bin/bash
# =============================================================================
# Docker Development Setup Script for dYdX Trading Bot
# =============================================================================

set -e

# Configuration
DOCKER_DIR="$(dirname "$0")"
PROJECT_ROOT="$(dirname "$DOCKER_DIR")"

echo "============================================================"
echo "🐳 dYdX Trading Bot - Docker Development Setup"
echo "============================================================"

# Check if Docker is installed and running
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running. Please start Docker first."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are available"

# Create .env file if it doesn't exist
if [[ ! -f "$DOCKER_DIR/.env" ]]; then
    echo "📝 Creating .env file from template..."
    cp "$DOCKER_DIR/.env.docker" "$DOCKER_DIR/.env"
    echo "⚠️  Please edit docker/.env file with your actual configuration values"
else
    echo "✅ .env file exists"
fi

# Generate SSL certificates for development
echo "🔐 Setting up SSL certificates..."
cd "$DOCKER_DIR/ssl"
chmod +x generate-ssl.sh
./generate-ssl.sh

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p "$PROJECT_ROOT/logs"
mkdir -p "$PROJECT_ROOT/data"
mkdir -p "$PROJECT_ROOT/bot_states"

echo "============================================================"
echo "🎉 Setup Complete!"
echo "============================================================"
echo "Next steps:"
echo "1. Edit docker/.env with your configuration"
echo "2. Run 'make docker-dev' to start development environment"
echo "3. Run 'make docker-prod' to start production environment"
echo "4. Access the API at https://localhost (with SSL)"
echo "============================================================"