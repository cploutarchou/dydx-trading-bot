#!/usr/bin/env python3
"""Compatibility launcher for the canonical API entrypoint in `src.api.start_api`."""

from dotenv import load_dotenv

# Keep dotenv load before importing the startup module.
load_dotenv()

from src.api.start_api import main


if __name__ == "__main__":
    main()

