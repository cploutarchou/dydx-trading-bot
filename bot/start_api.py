#!/usr/bin/env python3
"""Legacy root launcher that delegates to `src.api.start_api:main`."""

import sys
import warnings

from src.shared.env_loader import load_repo_env

# Keep dotenv load before importing the startup module.
load_repo_env(__file__)

from src.api.start_api import main


def run() -> None:
    """Run the canonical API launcher from the legacy root path."""
    print(
        "[DEPRECATED] `start_api.py` is a compatibility entrypoint; use `src/api/start_api.py`.",
        file=sys.stderr,
    )
    warnings.warn(
        "`start_api.py` is a compatibility entrypoint; use `src/api/start_api.py` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    main()

if __name__ == "__main__":
    run()

