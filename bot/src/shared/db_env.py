"""Canonical database environment-alias resolution.

The service accepts three environment-variable families for database
connection settings. Historically each consumer re-implemented the alias
chains inline (``config/config.py``, ``DatabaseConfig``, startup
validation, and the persistence-enabled predicates drifted apart — some
chains even dropped the ``POSTGRES_*`` family). This module defines the
chains exactly once:

- ``BOT_DB_*``    dedicated bot-database family (``BOT_DB_CUTOVER_MODE`` dedicated*)
- ``DB_*``        shared-database family (canonical)
- ``POSTGRES_*``  container/docker-convention aliases

Full chains resolve ``BOT_DB_* > DB_* > POSTGRES_*`` (first non-empty
wins). Shared-only chains resolve ``DB_* > POSTGRES_*`` and exist for the
resolution paths where a ``BOT_DB_*`` value must NOT leak into shared-mode
lookups (``DatabaseConfig`` shared mode and shared-target detection).

Explicit URL variables (``BOT_DATABASE_URL`` / ``DATABASE_URL``) carry
their own cutover-mode precedence in ``DatabaseConfig``
(``src/infrastructure/database.py``); here they are only checked for
non-emptiness by :func:`any_db_connection_configured`.
"""

from __future__ import annotations

import os
from typing import Optional

# Ordered alias chains per logical field; index 0 wins. Keyed by logical
# field name (not by an env-var name) so both chain flavors share keys.
_DB_FIELD_CHAINS: dict[str, tuple[str, ...]] = {
    "name": ("BOT_DB_NAME", "DB_NAME", "POSTGRES_DB"),
    "user": ("BOT_DB_USER", "DB_USER", "POSTGRES_USER"),
    "password": ("BOT_DB_PASSWORD", "DB_PASSWORD", "POSTGRES_PASSWORD"),
    "host": ("BOT_DB_HOST", "DB_HOST", "POSTGRES_HOST"),
    "port": ("BOT_DB_PORT", "DB_PORT", "POSTGRES_PORT"),
}

# Shared-mode flavor: identical order minus the BOT_DB_* family, so
# dedicated-bot values cannot leak into shared-database resolution.
_SHARED_DB_FIELD_CHAINS: dict[str, tuple[str, ...]] = {
    field: tuple(name for name in chain if not name.startswith("BOT_"))
    for field, chain in _DB_FIELD_CHAINS.items()
}

_DB_URL_VARIABLES: tuple[str, ...] = ("BOT_DATABASE_URL", "DATABASE_URL")


def _chain_source(chain: tuple[str, ...]) -> Optional[str]:
    for name in chain:
        value = os.getenv(name)
        if value is not None and value.strip() != "":
            return name
    return None


def db_env_source(field: str, *, shared_only: bool = False) -> Optional[str]:
    """Return the environment variable that supplies ``field``.

    ``None`` means the field fell through to its consumer default
    (no alias in the chain is set). Whitespace-only values count as
    unset — a blank host/port must not shadow a real alias.
    """
    chains = _SHARED_DB_FIELD_CHAINS if shared_only else _DB_FIELD_CHAINS
    chain = chains.get(field)
    if chain is None:
        raise KeyError(f"Unknown database env field {field!r}; known: {sorted(chains)}")
    return _chain_source(chain)


def db_env_value(field: str, default: str = "", *, shared_only: bool = False) -> str:
    """Resolve ``field`` through its alias chain, first non-empty wins."""
    source = db_env_source(field, shared_only=shared_only)
    if source is None:
        return default
    return os.environ[source]


def shared_db_env_value(field: str, default: str = "") -> str:
    """Resolve ``field`` from the shared family only (``DB_* > POSTGRES_*``)."""
    return db_env_value(field, default, shared_only=True)


def db_field_sources(*, shared_only: bool = False) -> dict[str, Optional[str]]:
    """Sanitized per-field provenance (env-var names, never values)."""
    return {
        field: db_env_source(field, shared_only=shared_only)
        for field in _DB_FIELD_CHAINS
    }


def any_db_connection_configured() -> bool:
    """True when any DB URL variable or full-chain field alias is set.

    Canonical predicate for "is a database configured at all" — used by
    the persistence-enabled checks so deployments configured through ANY
    supported family (previously ``POSTGRES_*``-only setups were missed
    by the truncated inline chains) are detected consistently.
    """
    names = set(_DB_URL_VARIABLES)
    for chain in _DB_FIELD_CHAINS.values():
        names.update(chain)
    return any(bool(os.getenv(name, "").strip()) for name in names)
