#!/bin/bash

# Activate virtual environment and start the API server
echo "🔧 Activating virtual environment..."
source venv/bin/activate

echo "📦 Installing/updating dependencies..."
pip install -r requirements.txt

echo "🚀 Starting dYdX Trading Bot API Server..."
echo "📊 Dashboard will be available at: http://localhost:8000"
echo "📖 API Documentation available at: http://localhost:8000/docs"
echo "🔍 Health check available at: http://localhost:8000/health"
echo ""

python start_api.py