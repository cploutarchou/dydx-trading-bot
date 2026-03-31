"""Compatibility module: root `app.py` now re-exports the canonical API app."""

import os

from dotenv import load_dotenv

# Keep dotenv load before importing the canonical app entrypoint.
load_dotenv()

from src.api.server import app as app  # re-exported compatibility symbol


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.server:app",
        host=os.getenv("BOT_API_HOST", "0.0.0.0"),
        port=int(os.getenv("BOT_API_PORT", "8889")),
        reload=os.getenv("BOT_API_RELOAD", "true").lower() == "true",
        log_level="info",
    )
