"""Startup configuration validation.

Surfaces missing/malformed REQUIRED configuration with a single clear, actionable
error instead of scattered cryptic runtime failures (e.g. every authenticated
request returning 401, Celery tasks failing to dispatch, unsigned mainnet orders).
Called by entrypoints after :func:`src.shared.env_loader.load_repo_env`.

Design:

- **Collect, don't fail-fast** — gathers *all* problems and reports them in one
  message so an operator can fix everything in a single pass.
- **Mode-aware** — raises :class:`src.exceptions.ConfigurationError` (enumerated)
  in production or when ``STARTUP_CONFIG_VALIDATION=strict``; logs a warning
  otherwise (development), so local/test workflows that intentionally omit
  optional config are not blocked.
- ``STARTUP_CONFIG_VALIDATION=skip`` bypasses entirely (emergency escape hatch).

Validation is intentionally ENV-VAR based — the post-``load_repo_env`` surface —
and covers only clearly-required, high-value config. It does NOT duplicate the
structured-config parsing in ``config/config.py`` (which has its own errors) or
attempt a live DB/broker connection (that is the runtime's job).
"""

from __future__ import annotations

import logging
import os

from src.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

_STRICT = "strict"
_SKIP = "skip"
_PRODUCTION_TOKENS = {"prod", "production"}


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if raw == "":
        return default
    return raw.lower() in {"1", "true", "yes", "y", "on"}


def _is_production() -> bool:
    """True if any standard environment marker reads as production."""
    for key in ("APP_CONFIG_ENV", "CONFIG_ENV", "ENVIRONMENT", "APP_ENV"):
        value = _env(key).lower()
        if value:
            return value in _PRODUCTION_TOKENS
    return False


def _collect_config_problems() -> list[str]:
    problems: list[str] = []
    bypass_auth = _env_bool("API_BYPASS_AUTH", False)

    # 1. Auth tokens — required in production when auth is not bypassed. The
    #    API_BYPASS_AUTH-in-production guard (src/api/server.py) already rejects
    #    bypass outside dev/test, so production + no-bypass must have a token or
    #    every mutating route returns 401.
    if _is_production() and not bypass_auth:
        has_token = bool(_env("BOT_API_TOKEN") or _env("BOT_API_TOKENS"))
        if not has_token:
            problems.append(
                "Authentication is enabled but no service token is configured: set "
                "BOT_API_TOKEN (or BOT_API_TOKENS) — every authenticated request "
                "would otherwise be rejected with 401."
            )

    # 2. Celery broker — required when backtests dispatch to Celery.
    backend = _env("BACKTEST_WORKER_BACKEND").lower() or "asyncio"
    if backend == "celery":
        has_broker = bool(
            _env("CELERY_BROKER_URL")
            or _env("CELERY_BROKER")
            or _env("REDIS_URL")
            or _env("VALKEY_URL")
        )
        if not has_broker:
            problems.append(
                "BACKTEST_WORKER_BACKEND=celery but no broker is configured: set "
                "CELERY_BROKER_URL (or REDIS_URL/VALKEY_URL) — Celery tasks cannot "
                "be dispatched without a broker."
            )

    # 3. Live trading on mainnet — dYdX signing credentials are required. The chain
    #    address is derived from the signing key, so the secret/mnemonic alone is the
    #    essential credential. Structured config flattens dydx_chain_secret into env;
    #    the canonical aliases (MNEMONIC, BOT_DYDX_SECRET) are also accepted.
    is_testnet = _env_bool("IS_TESTNET", True)
    place_trades = _env_bool("BOT_PLACE_TRADES", False)
    if place_trades and not is_testnet:
        has_signing_material = bool(
            _env("DYDX_CHAIN_SECRET")
            or _env("dydx_chain_secret")
            or _env("BOT_DYDX_SECRET")
            or _env("MNEMONIC")
        )
        if not has_signing_material:
            problems.append(
                "BOT_PLACE_TRADES=true with IS_TESTNET=false (mainnet live trading) "
                "but dYdX signing material is missing: provide the chain secret or "
                "MNEMONIC (dydx_chain_secret / MNEMONIC) — orders cannot be signed "
                "without it. (The chain address is derived from the signing key.)"
            )

    # 4. Integer port formats / ranges.
    for name in ("BOT_API_PORT", "BOT_DB_PORT", "DB_PORT", "POSTGRES_PORT"):
        raw = _env(name)
        if raw == "":
            continue
        try:
            port = int(raw)
        except ValueError:
            problems.append(f"{name}={raw!r} is not a valid integer port.")
            continue
        if not (1 <= port <= 65535):
            problems.append(f"{name}={port} is out of range (must be 1..65535).")

    # 5. Heuristic: an all-default database (localhost, no password) in production
    #    is almost certainly misconfigured.
    if _is_production():
        db_host_set = bool(
            _env("BOT_DB_HOST") or _env("DB_HOST") or _env("POSTGRES_HOST")
        )
        db_pwd_set = bool(
            _env("BOT_DB_PASSWORD") or _env("DB_PASSWORD") or _env("POSTGRES_PASSWORD")
        )
        if not db_host_set and not db_pwd_set:
            problems.append(
                "Database is using all-default connection params (localhost, no "
                "password) in production: set BOT_DB_HOST and BOT_DB_PASSWORD (or the "
                "DB_*/POSTGRES_* aliases) — the default is almost certainly wrong for "
                "a production deployment."
            )

    return problems


def validate_startup_config() -> None:
    """Validate required startup configuration; raise or warn on problems.

    Raises :class:`ConfigurationError` (with all problems enumerated) when running
    strict (production, or ``STARTUP_CONFIG_VALIDATION=strict``); otherwise logs a
    warning. ``STARTUP_CONFIG_VALIDATION=skip`` bypasses entirely.
    """
    mode = _env("STARTUP_CONFIG_VALIDATION").lower()
    if mode == _SKIP:
        logger.debug(
            "STARTUP_CONFIG_VALIDATION=skip — startup config validation bypassed."
        )
        return

    problems = _collect_config_problems()
    if not problems:
        return

    message = "Startup configuration validation found {} problem(s):\n  - {}".format(
        len(problems), "\n  - ".join(problems)
    )

    strict = mode == _STRICT or _is_production()
    if strict:
        raise ConfigurationError(message)
    logger.warning(
        "%s\n(Reporting only: env is not production and STARTUP_CONFIG_VALIDATION is "
        "not 'strict'. Set STARTUP_CONFIG_VALIDATION=strict to fail startup on these.)",
        message,
    )


__all__ = ["validate_startup_config"]
