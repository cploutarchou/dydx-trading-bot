"""Compatibility module: root `app.py` now re-exports the canonical API app."""

from dotenv import load_dotenv

# Keep dotenv load before importing the canonical app entrypoint.
load_dotenv()

from src.api.server import app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
