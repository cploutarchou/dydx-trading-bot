#!/bin/bash
set -e

echo "🚀 Setting up dYdX Trading Bot Development Environment..."

# Update pip
echo "📦 Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install project dependencies
echo "📦 Installing project dependencies..."
cd /workspace
pip install -r requirements.txt

# Install development dependencies
echo "📦 Installing development dependencies..."
pip install \
    pytest==7.4.3 \
    pytest-cov==4.1.0 \
    pytest-asyncio==0.21.1 \
    pytest-mock==3.12.0 \
    black==23.12.1 \
    ruff==0.1.11 \
    pylint==3.0.3 \
    mypy==1.7.1 \
    ipython==8.18.1 \
    jupyter==1.0.0 \
    notebook==7.0.6 \
    jupyterlab==4.0.9 \
    ipdb==0.13.13 \
    pre-commit==3.5.0 \
    requests==2.31.0 \
    httpx==0.25.2

# Install postgres and redis clients for testing
echo "📦 Installing database clients..."
pip install \
    pgcli==4.0.1 \
    redis==5.0.1

# Create .env file if it doesn't exist
if [ ! -f /workspace/.env ]; then
    echo "📝 Creating .env file from example..."
    cp /workspace/.env.example /workspace/.env
    echo "⚠️  Please update .env with your credentials"
else
    echo "✅ .env file already exists"
fi

# Setup pre-commit hooks
echo "🪝 Setting up pre-commit hooks..."
cd /workspace
git init 2>/dev/null || true
pre-commit install 2>/dev/null || true

# Create directories if they don't exist
echo "📁 Creating necessary directories..."
mkdir -p /workspace/logs
mkdir -p /workspace/data
mkdir -p /workspace/reports

# Run initial database migrations
echo "🗄️  Setting up database..."
cd /workspace
if command -v alembic &> /dev/null; then
    echo "Running Alembic migrations..."
    alembic upgrade head 2>/dev/null || echo "⚠️  Database migrations skipped (may need manual setup)"
else
    echo "⚠️  Alembic not found, skipping migrations"
fi

echo ""
echo "✅ Development environment setup complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Review and update .env with your dYdX API credentials"
echo "   2. Update config.yaml with your trading parameters"
echo "   3. Run: python main.py (for bot)"
echo "   4. Run: python start_api.py (for API server)"
echo "   5. Run: pytest (to run tests)"
echo ""
echo "📚 Documentation:"
echo "   - QUICK_START.md - Get started in 5 minutes"
echo "   - API_USAGE_GUIDE.md - Complete API reference"
echo "   - SETUP_AND_DEPLOYMENT.md - Detailed setup guide"
echo ""
echo "🔗 Available Services:"
echo "   - API Server: http://localhost:8889"
echo "   - FastAPI Docs: http://localhost:8889/docs"
echo "   - PostgreSQL: localhost:5432"
echo "   - Redis: localhost:6379"
echo ""
