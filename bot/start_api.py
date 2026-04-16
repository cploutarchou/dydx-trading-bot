#!/usr/bin/env python3
"""Compatibility launcher for the canonical API entrypoint in `src.api.start_api`."""

from src.shared.env_loader import load_repo_env

# Keep dotenv load before importing the startup module.
load_repo_env(__file__)

from src.api.start_api import main

if __name__ == "__main__":
    main()
