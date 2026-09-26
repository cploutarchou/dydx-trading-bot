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
# Trailing stop: once a pair's best unrealized P&L (% of its entry notional, the
# measure the stop loss uses) has reached this distance, the pair is closed when
# its P&L falls this many points below that best level. 0 disables it.
TRAILING_STOP_PCT = max(
    0.0, float(getattr(bot_settings, "trailingStopPct", 0.0) or 0.0)
)
# Bot-level drawdown limit on the equity of the subaccount the runtime trades
# on. Reaching it halts new entries (src/trading/drawdown_guard.py). 0 disables.
MAX_DRAWDOWN_PCT = max(0.0, float(getattr(bot_settings, "maxDrawdownPct", 0.0) or 0.0))

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

# Cost + funding entry gate (src/trading/entry_cost_gate.py). Startup defaults
# only: the decision path reads them through
# arbitrage_runtime_config.get_runtime_settings(), which clamps them and lets
# the backend override them at runtime. Off by default.
import src.trading.entry_cost_gate as _entry_cost_gate

COST_GATE_ENABLED = _env_flag("COST_GATE_ENABLED", False)
# Required edge / round-trip cost ratio.
COST_GATE_EDGE_MULTIPLE: float = float(
    _os.getenv("COST_GATE_EDGE_MULTIPLE", str(_entry_cost_gate.DEFAULT_EDGE_MULTIPLE))
)
# Taker fee per fill, shared with the backtest's default transaction_fee.
COST_GATE_TAKER_FEE: float = float(
    _os.getenv("COST_GATE_TAKER_FEE", str(_entry_cost_gate.DEFAULT_TAKER_FEE))
)
# Assumed slippage per fill, in basis points of the leg notional.
COST_GATE_SLIPPAGE_BPS_DEFAULT = 5.0
COST_GATE_SLIPPAGE_BPS: float = float(
    _os.getenv("COST_GATE_SLIPPAGE_BPS", str(COST_GATE_SLIPPAGE_BPS_DEFAULT))
)
# Hourly funding rate above which a leg counts as paying (tau). An entry whose
# long leg's rate is above tau AND whose short leg's rate is below -tau pays
# funding on both legs and is rejected.
FUNDING_SAME_SIDE_THRESHOLD_DEFAULT = 0.00001
FUNDING_SAME_SIDE_THRESHOLD: float = float(
    _os.getenv("FUNDING_SAME_SIDE_THRESHOLD", str(FUNDING_SAME_SIDE_THRESHOLD_DEFAULT))
)

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
# (see ``src/infrastructure/broadcast``). Default ON since 2026-08-16
# (Phase 2 flip): multi-worker deployments get cross-worker fan-out, while
# Redis-less deployments degrade gracefully — unconfigured → Noop bus;
# unreachable → fast-fail with a publish failure circuit (see bus.py) that
# bounds the cost to a few connect attempts per pause window. A Redis outage
# never breaks a broadcast (always local-first). Set =false to restore
# strictly local-only delivery.
WS_BROADCAST_ENABLED: bool = _env_flag("WS_BROADCAST_ENABLED", True)
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
# limits while the account as a whole is over-exposed. ON by default since the
# Phase B flip (2026-08-17, after the testnet burn-in recorded in
# docs/bot-risk-control-matrix.md); set =false to restore pre-Phase-A behavior.
# Any individual limit <= 0 still disables that check.
BOT_PORTFOLIO_RISK_ENABLED: bool = _env_flag("BOT_PORTFOLIO_RISK_ENABLED", True)
BOT_PORTFOLIO_MAX_OPEN_MARKETS: int = int(
    _os.getenv("BOT_PORTFOLIO_MAX_OPEN_MARKETS", "20")
)
BOT_PORTFOLIO_MAX_MARGIN_UTILIZATION_PCT: float = float(
    _os.getenv("BOT_PORTFOLIO_MAX_MARGIN_UTILIZATION_PCT", "60.0")
)
BOT_PORTFOLIO_MIN_FREE_COLLATERAL_USD: float = float(
    _os.getenv("BOT_PORTFOLIO_MIN_FREE_COLLATERAL_USD", "0.0")
)
# Account-level drawdown from the ratcheted all-time peak equity (Redis-backed
# peak per wallet address). Denies new entries at/after the cap; 0 disables.
# NOTE: this is the deployment-wide control. The per-strategy `max_drawdown_pct`
# (MAX_DRAWDOWN_PCT above) is separate: its peak is durable and it latches the
# entry halt instead of denying cycle by cycle.
BOT_PORTFOLIO_MAX_DRAWDOWN_PCT: float = float(
    _os.getenv("BOT_PORTFOLIO_MAX_DRAWDOWN_PCT", "0.0")
)
# Advanced portfolio controls (all individually opt-in, 0/empty disables):
# per-market USD notional concentration cap, gross-notional-as-%-of-equity cap
# (effective leverage ceiling), and the UTC-day self-healing loss limit (drops
# from the daily peak equity; the all-time drawdown above never resets itself).
BOT_PORTFOLIO_MAX_NOTIONAL_PER_MARKET_USD: float = float(
    _os.getenv("BOT_PORTFOLIO_MAX_NOTIONAL_PER_MARKET_USD", "0.0")
)
BOT_PORTFOLIO_MAX_TOTAL_NOTIONAL_PCT: float = float(
    _os.getenv("BOT_PORTFOLIO_MAX_TOTAL_NOTIONAL_PCT", "0.0")
)
BOT_PORTFOLIO_MAX_DAILY_LOSS_PCT: float = float(
    _os.getenv("BOT_PORTFOLIO_MAX_DAILY_LOSS_PCT", "0.0")
)
# Correlation buckets: "NAME:m1,m2,...:max_pct_of_equity" entries joined by ";".
# Each bucket caps the projected notional held in its member markets (as a % of
# equity). Malformed entries are skipped with a warning (fail-open parsing);
# the check itself is exchange-read-derived and fails closed like the other
# notional controls.
BOT_PORTFOLIO_CORRELATION_BUCKETS: str = _os.getenv(
    "BOT_PORTFOLIO_CORRELATION_BUCKETS", ""
).strip()
# Multi-account aggregation: deployment-wide caps across EVERY distinct wallet
# address configured in `bot_instances` (per network). Aggregate limits are
# opt-in individually (0 disables) and only take effect when the master switch
# above is on; enabling one also turns on cross-address public indexer reads.
BOT_PORTFOLIO_AGGREGATE_MAX_OPEN_MARKETS: int = int(
    _os.getenv("BOT_PORTFOLIO_AGGREGATE_MAX_OPEN_MARKETS", "0")
)
BOT_PORTFOLIO_AGGREGATE_MAX_MARGIN_UTILIZATION_PCT: float = float(
    _os.getenv("BOT_PORTFOLIO_AGGREGATE_MAX_MARGIN_UTILIZATION_PCT", "0.0")
)
# Enumeration/enrichment bounds: how many distinct subaccounts to consider and
# how long the (DB-decrypted) address list stays cached per process.
BOT_PORTFOLIO_AGGREGATE_MAX_ACCOUNTS: int = int(
    _os.getenv("BOT_PORTFOLIO_AGGREGATE_MAX_ACCOUNTS", "25")
)
BOT_PORTFOLIO_ACCOUNTS_CACHE_TTL_SECONDS: float = float(
    _os.getenv("BOT_PORTFOLIO_ACCOUNTS_CACHE_TTL_SECONDS", "60")
)
# Per-request timeout for the monitoring route's direct public indexer reads.
BOT_PORTFOLIO_ACCOUNTS_HTTP_TIMEOUT_SECONDS: float = float(
    _os.getenv("BOT_PORTFOLIO_ACCOUNTS_HTTP_TIMEOUT_SECONDS", "5.0")
)

# Max concurrent dYdX candle fetches when building the price matrix.
CANDLE_FETCH_CONCURRENCY: int = int(_os.getenv("CANDLE_FETCH_CONCURRENCY", "10"))
