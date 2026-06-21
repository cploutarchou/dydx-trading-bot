#!/usr/bin/env python3
"""
Canonical API process launcher.

Use this module when running the API process directly.
"""

import os

import uvicorn

from src.shared.env_loader import load_repo_env

# Entry-point safety: load env before importing server/config modules.
load_repo_env(__file__)


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() == "true"


def main() -> None:
    host = os.getenv("BOT_API_HOST", "0.0.0.0")
    port = int(os.getenv("BOT_API_PORT", "8889"))
    reload_enabled = _env_bool("BOT_API_RELOAD")

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
        log_config=None,
    )


if __name__ == "__main__":
    main()
