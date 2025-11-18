#!/usr/bin/env python3
"""
API Server Startup Script
"""

import uvicorn
from bot_api_server import app

if __name__ == "__main__":
    print("🚀 Starting dYdX Trading Bot API Server...")
    print("📊 Dashboard will be available at: http://localhost:8000")
    print("📖 API Documentation available at: http://localhost:8000/docs")
    print("🔍 Health check available at: http://localhost:8000/health")
    print("")
    
    uvicorn.run(
        "bot_api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )