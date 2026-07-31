from __future__ import annotations

import os
from urllib.parse import quote


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return str(value)
    return default


def redis_host(default: str = "localhost") -> str:
    return _first_env("REDIS_HOST", "VALKEY_HOST", default=default)


def redis_port(default: str = "6379") -> str:
    return _first_env("REDIS_PORT", "VALKEY_PORT", default=default)


def redis_db(default: str = "0") -> str:
    return _first_env("REDIS_DB", default=default)


def redis_password(default: str = "") -> str:
    return _first_env("REDIS_PASSWORD", default=default)


def redis_ssl_enabled(default: bool = False) -> bool:
    raw = (
        _first_env("REDIS_SSL", default="true" if default else "false").strip().lower()
    )
    return raw in {"1", "true", "yes", "on"}


def redis_url(*, db_offset: int = 0, prefer_celery_broker: bool = True) -> str:
    explicit_names = []
    if prefer_celery_broker:
        explicit_names.append("CELERY_BROKER_URL")
    explicit_names.extend(("REDIS_URL", "VALKEY_URL"))
    explicit = _first_env(*explicit_names)
    if explicit:
        return explicit

    host = redis_host()
    port = redis_port()
    try:
        db_index = int(redis_db() or "0") + db_offset
    except ValueError:
        db_index = db_offset
    password = redis_password()
    scheme = "rediss" if redis_ssl_enabled() else "redis"
    auth = f":{quote(password)}@" if password else ""
    return f"{scheme}://{auth}{host}:{port}/{db_index}"
