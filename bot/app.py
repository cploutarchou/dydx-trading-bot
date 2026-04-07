"""Compatibility module: root `app.py` now re-exports the canonical API app."""

import os

from src.shared.env_loader import load_repo_env

# Keep dotenv load before importing the canonical app entrypoint.
load_repo_env(__file__)

from src.api.server import app as app  # re-exported compatibility symbol

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.server:app",
        host=os.getenv("BOT_API_HOST", "0.0.0.0"),
        port=int(os.getenv("BOT_API_PORT", "8889")),
        reload=os.getenv("BOT_API_RELOAD", "true").lower() == "true",
        log_level="info",
        log_config=None,
    )
