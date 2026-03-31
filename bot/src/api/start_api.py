#!/usr/bin/env python3
"""
API Server Startup Script
"""

import os
from pathlib import Path

from dotenv import load_dotenv
import uvicorn

# Entry-point safety: load env before importing server/config modules.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def main() -> None:
    host = os.getenv("BOT_API_HOST", "0.0.0.0")
    port = int(os.getenv("BOT_API_PORT", "8889"))
    reload_enabled = os.getenv("BOT_API_RELOAD", "true").lower() == "true"

    print("🚀 Starting dYdX Trading Bot API Server...")
    print(f"📊 Dashboard will be available at: http://localhost:{port}")
    print(f"📖 API Documentation available at: http://localhost:{port}/docs")
    print(f"🔍 Health check available at: http://localhost:{port}/health")
    print("")

    uvicorn.run(
        "src.api.server:app",
        host=host,
        port=port,
        reload=reload_enabled,
        log_level="info",
    )


if __name__ == "__main__":
    main()
