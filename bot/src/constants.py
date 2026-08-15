from config.config import config as app_config

_CONFIG = app_config()
if _CONFIG is None:
    raise RuntimeError("Configuration could not be loaded")

# For gathering testnet data or live market data for cointegration calculation
if _CONFIG.is_testnet:
    MARKET_DATA_MODE = "TESTNET"  # vs "MAINNET"
else:
    MARKET_DATA_MODE = "MAINNET"

import logging as _std_logging

_std_logging.getLogger(__name__).debug("Market Data Mode: %s", MARKET_DATA_MODE)
# Get bot settings from config
bot_settings = _CONFIG.botSettings
if bot_settings is None:
    raise RuntimeError("botSettings configuration is missing")

SUBACCOUNT_NUMBER = int(getattr(bot_settings, "subaccountNumber", 0) or 0)
CAPITAL_ALLOCATION_USD = float(
    getattr(bot_settings, "capitalAllocationUsd", 0.0) or 0.0
)

# Close all open positions and orders
ABORT_ALL_POSITIONS = bot_settings.abortAllPositions

# Find Cointegrated Pairs
FIND_COINTEGRATED = bot_settings.findCointegratedPairs

# Manage Exits
MANAGE_EXITS = bot_settings.manageExits

# Place Trades
PLACE_TRADES = bot_settings.placeTrades

# Resolution
RESOLUTION = bot_settings.resolutionTimeframe

# Stats Window
WINDOW = bot_settings.statsWindow

# Thresholds - Opening
MAX_HALF_LIFE = bot_settings.maxHalfLife
ZSCORE_THRESH = bot_settings.ZScoreThreshold
USD_PER_TRADE = bot_settings.usdPerTrade
USD_MIN_COLLATERAL = bot_settings.usdMinCollateral

# Thresholds - Closing
CLOSE_AT_ZSCORE_CROSS = bot_settings.closeAtZscoreCross
MAX_POSITIONS = int(getattr(bot_settings, "maxPositions", 5) or 0)
STOP_LOSS_PCT = float(getattr(bot_settings, "stopLossPct", 2.0) or 0.0)
TAKE_PROFIT_PCT = float(getattr(bot_settings, "takeProfitPct", 5.0) or 0.0)
POSITION_TIMEOUT_HOURS = int(getattr(bot_settings, "positionTimeoutHours", 72) or 0)

# Endpoint for Account Queries
INDEXER_ENDPOINT_TESTNET = "https://indexer.v4testnet.dydx.exchange"
INDEXER_ENDPOINT_MAINNET = "https://indexer.dydx.trade"
INDEXER_ACCOUNT_ENDPOINT = bot_settings.indexer_endpoint

if _CONFIG.is_testnet:
    if _CONFIG.dydx_testnet is None:
        raise RuntimeError("dydx_testnet configuration is missing")
    DYDX_ADDRESS = _CONFIG.dydx_testnet.dydx_chain_address
    SECRET_PHRASE = _CONFIG.dydx_testnet.dydx_chain_secret
else:
    if _CONFIG.dydx_mainnet is None:
        raise RuntimeError("dydx_mainnet configuration is missing")
    DYDX_ADDRESS = _CONFIG.dydx_mainnet.dydx_chain_address
    SECRET_PHRASE = _CONFIG.dydx_mainnet.dydx_chain_secret

# Get dydx and telegram settings from config
MNEMONIC = SECRET_PHRASE
TELEGRAM_TOKEN = _CONFIG.telegram.token if _CONFIG.telegram else ""
TELEGRAM_CHAT_ID = _CONFIG.telegram.chat_id if _CONFIG.telegram else ""
# Environment setting
ENVIRONMENT = _CONFIG.environment.lower()

logging_settings = getattr(_CONFIG, "logging", None)

if logging_settings is not None:
    LOG_LEVEL = logging_settings.level.upper()
    loki_settings = logging_settings.loki
    LOKI_ENABLED = bool(loki_settings.enabled)
    LOKI_BASE_URL = loki_settings.url.rstrip("/") if loki_settings.url else ""
    LOKI_PUSH_URL = f"{LOKI_BASE_URL}/loki/api/v1/push" if LOKI_BASE_URL else ""
    LOKI_USERNAME = loki_settings.username
    LOKI_PASSWORD = loki_settings.password
    LOKI_TENANT_ID = loki_settings.tenant_id
    LOKI_LABELS = dict(loki_settings.labels)
else:
    LOG_LEVEL = "INFO"
    LOKI_ENABLED = False
    LOKI_BASE_URL = ""
    LOKI_PUSH_URL = ""
    LOKI_USERNAME = ""
    LOKI_PASSWORD = ""
    LOKI_TENANT_ID = None
    LOKI_LABELS = {}

# ── Performance tuning ────────────────────────────────────────────────────────
import os as _os


def _env_flag(name: str, default: bool = False) -> bool:
    raw = _os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


ARBITRAGE_IMPROVEMENTS_ENABLED = _env_flag("ARBITRAGE_IMPROVEMENTS_ENABLED", False)
PAIR_PRIORITY_ENGINE_ENABLED = _env_flag("PAIR_PRIORITY_ENGINE_ENABLED", False)
POLYMARKET_SIGNALS_ENABLED = _env_flag("POLYMARKET_SIGNALS_ENABLED", False)
DEFILLAMA_SIGNALS_ENABLED = _env_flag("DEFILLAMA_SIGNALS_ENABLED", False)
NEWS_SIGNALS_ENABLED = _env_flag("NEWS_SIGNALS_ENABLED", False)
AUTO_EXECUTION_CHANGES_ENABLED = _env_flag("AUTO_EXECUTION_CHANGES_ENABLED", False)

# Per-call sleep between dYdX API requests (milliseconds → seconds).
# Set DYDX_API_THROTTLE_MS=0 to disable; default 200 ms.
DYDX_API_THROTTLE_SECONDS: float = (
    float(_os.getenv("DYDX_API_THROTTLE_MS", "200")) / 1000.0
)

# How long to cache the perpetual markets list (seconds). 0 = disabled.
MARKETS_CACHE_TTL_SECONDS: float = float(_os.getenv("MARKETS_CACHE_TTL_SECONDS", "60"))

# How long to cache recent-candle responses per market (seconds). 0 = disabled.
CANDLES_RECENT_CACHE_TTL_SECONDS: float = float(
    _os.getenv("CANDLES_RECENT_CACHE_TTL_SECONDS", "30")
)

# Shared (L2) Redis market-data cache. Even when enabled, runtime Redis failures
# degrade per-command to a cache miss (never break a market-data call). The
# shared candles key (`market:candles:{market}:{resolution}`) interoperate with
# the Celery Beat producer in `market_sync_tasks.py`.
MARKET_DATA_CACHE_ENABLED: bool = _env_flag("MARKET_DATA_CACHE_ENABLED", True)
# Optional explicit Redis URL; falls back to the Celery broker / REDIS_URL /
# VALKEY_URL resolution in `src/shared/redis_env.py` when unset.
MARKET_DATA_CACHE_REDIS_URL: str = _os.getenv("MARKET_DATA_CACHE_REDIS_URL", "")
# Per-command socket timeout (seconds) so a down Redis cannot stall market data.
MARKET_DATA_CACHE_SOCKET_TIMEOUT_SECONDS: float = float(
    _os.getenv("MARKET_DATA_CACHE_SOCKET_TIMEOUT_SECONDS", "1.0")
)

# Cross-worker WebSocket broadcast bus (Redis pub/sub). The ``ConnectionManager``
# in ``src/api/websocket_server.py`` is process-local, so a broadcast on one
# Uvicorn worker never reaches clients connected to another. When enabled, every
# ``broadcast_to_bot`` additionally publishes to a shared pub/sub channel and
# each worker's subscriber fans the message out to its own local connections
# (see ``src/infrastructure/broadcast``). Default OFF: single-worker deployments
# and tests behave identically to today, and a Redis outage degrades to
# local-only delivery (never breaks a broadcast).
WS_BROADCAST_ENABLED: bool = _env_flag("WS_BROADCAST_ENABLED", False)
# Optional explicit Redis URL; falls back to the Celery broker / REDIS_URL /
# VALKEY_URL resolution in `src/shared/redis_env.py` when unset.
WS_BROADCAST_REDIS_URL: str = _os.getenv("WS_BROADCAST_REDIS_URL", "")
# Per-command socket timeout (seconds) so a down Redis cannot stall a broadcast.
WS_BROADCAST_SOCKET_TIMEOUT_SECONDS: float = float(
    _os.getenv("WS_BROADCAST_SOCKET_TIMEOUT_SECONDS", "1.0")
)
# Upper bound for one cross-worker dispatch (deliver_local_broadcast) before the
# subscriber cancels it and counts a dispatch_timeout — bounds a stuck WebSocket
# consumer from stalling the whole listener under a burst.
WS_BROADCAST_DISPATCH_TIMEOUT_SECONDS: float = float(
    _os.getenv("WS_BROADCAST_DISPATCH_TIMEOUT_SECONDS", "5.0")
)

# Account-level (portfolio) risk controls — evaluate the SHARED dYdX subaccount
# (equity / free collateral / open perpetual markets) before any new entry, so
# N instances sharing one account cannot each stay inside their per-instance
# limits while the account as a whole is over-exposed. Phase A: opt-in (default
# off) until proven in production; any limit <= 0 disables that check.
BOT_PORTFOLIO_RISK_ENABLED: bool = _env_flag("BOT_PORTFOLIO_RISK_ENABLED", False)
BOT_PORTFOLIO_MAX_OPEN_MARKETS: int = int(
    _os.getenv("BOT_PORTFOLIO_MAX_OPEN_MARKETS", "20")
)
BOT_PORTFOLIO_MAX_MARGIN_UTILIZATION_PCT: float = float(
    _os.getenv("BOT_PORTFOLIO_MAX_MARGIN_UTILIZATION_PCT", "60.0")
)
BOT_PORTFOLIO_MIN_FREE_COLLATERAL_USD: float = float(
    _os.getenv("BOT_PORTFOLIO_MIN_FREE_COLLATERAL_USD", "0.0")
)

# Max concurrent dYdX candle fetches when building the price matrix.
CANDLE_FETCH_CONCURRENCY: int = int(_os.getenv("CANDLE_FETCH_CONCURRENCY", "10"))
