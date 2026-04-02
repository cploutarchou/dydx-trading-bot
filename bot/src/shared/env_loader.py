from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


def find_repo_root(anchor: PathLike) -> Path:
    current = Path(anchor).resolve()
    search_from = current.parent if current.is_file() else current

    for candidate in (search_from, *search_from.parents):
        if (candidate / ".github").exists() and (candidate / "AGENTS.md").exists():
            return candidate

    return search_from.parents[2]


def load_repo_env(anchor: PathLike, override: bool = False) -> Path:
    env_path = find_repo_root(anchor) / ".env"
    if env_path.exists():
        load_dotenv = import_module("dotenv").load_dotenv
        load_dotenv(env_path, override=override)
    return env_path