from config.config import config as app_config

_CONFIG = app_config()
if _CONFIG is None:
    raise RuntimeError("Configuration could not be loaded")

# For gathering testnet data or live market data for cointegration calculation
if _CONFIG.is_testnet:
    MARKET_DATA_MODE = "TESTNET"  # vs "MAINNET"
else:
    MARKET_DATA_MODE = "MAINNET"

print(f"Market Data Mode: {MARKET_DATA_MODE}")
# Get bot settings from config
bot_settings = _CONFIG.botSettings
if bot_settings is None:
    raise RuntimeError("botSettings configuration is missing")

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
