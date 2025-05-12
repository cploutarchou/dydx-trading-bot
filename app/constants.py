# from dydx3.constants import API_HOST_MAINNET, API_HOST_GOERLI
from config import config as app_config


# For gathering tesnet data or live market data for cointegration calculation
if app_config().is_testnet:
    MARKET_DATA_MODE = "TESTNET"  # vs "MAINNET"
else:
    MARKET_DATA_MODE = "MAINNET"

# Get bot settings from config
bot_settings = app_config().botSettings

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
INDEXER_ENDPOINT_TESTNET = bot_settings.indexer_endpoint.testnet
INDEXER_ENDPOINT_MAINNET = bot_settings.indexer_endpoint.mainnet
INDEXER_ACCOUNT_ENDPOINT = INDEXER_ENDPOINT_TESTNET if app_config().is_testnet else INDEXER_ENDPOINT_MAINNET

# Get dydx and telegram settings from config
DYDX_ADDRESS = app_config().dydx_chain_address
SECRET_PHRASE = app_config().dydx_secret_phrase
MNEMONIC = SECRET_PHRASE
TELEGRAM_TOKEN = app_config().telegram.token
TELEGRAM_CHAT_ID = app_config().telegram.chat_id
