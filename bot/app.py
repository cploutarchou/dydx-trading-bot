"""Legacy compatibility wrapper for API startup.

Canonical API app lives in `src.api.server:app`.
Canonical launcher lives in `src.api.start_api:main`.
"""

import sys
import warnings

from src.shared.env_loader import load_repo_env

# Keep environment loading before importing server/config modules.
load_repo_env(__file__)

from src.api.server import app  # re-export for `uvicorn app:app`
from src.api.start_api import main as start_api_main


def main() -> None:
    """Run the canonical API launcher from a legacy root entrypoint."""
    print(
        "[DEPRECATED] `app.py` is a compatibility entrypoint; use `src/api/start_api.py`.",
        file=sys.stderr,
    )
    warnings.warn(
        "`app.py` is a compatibility entrypoint; use `src/api/start_api.py` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    start_api_main()


if __name__ == "__main__":
    main()
