#!/bin/bash

# Start the API server locally using the project virtual environment.
set -euo pipefail

if [ ! -x ".venv/bin/python" ]; then
  echo "❌ Missing .venv interpreter at .venv/bin/python"
  echo "   Create it first: python -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi

echo "🚀 Starting dYdX Trading Bot API Server..."
echo "📊 Dashboard will be available at: http://localhost:8889"
echo "📖 API Documentation available at: http://localhost:8889/docs"
echo "🔍 Health check available at: http://localhost:8889/health"
echo ""

.venv/bin/python start_api.py
