import logging

from constants import (
    DYDX_ADDRESS,
    INDEXER_ACCOUNT_ENDPOINT,
    INDEXER_ENDPOINT_MAINNET,
    MARKET_DATA_MODE,
    MNEMONIC,
)
from dydx_v4_client import NodeClient, Wallet
from dydx_v4_client.indexer.rest.indexer_client import IndexerClient
from dydx_v4_client.network import TESTNET
from func_public import get_candles_recent

logger = logging.getLogger(__name__)


# Client Class
class Client:
    def __init__(self, indexer, indexer_account, node, wallet):
        self.indexer = indexer
        self.indexer_account = indexer_account
        self.node = node
        self.wallet = wallet


# Connect to DYDX
async def connect_dydx():
    logger.info("Initializing dYdX clients")
    # Determine market data endpoint
    market_data_endpoint = (
        INDEXER_ENDPOINT_MAINNET
        if MARKET_DATA_MODE != "TESTNET"
        else INDEXER_ACCOUNT_ENDPOINT
    )
    logger.debug(
        "Market data endpoint resolved to %s (mode=%s)",
        market_data_endpoint,
        MARKET_DATA_MODE,
    )

    # Indexer = connection we will use to get live mainnet data if using INDEXER_ENDPOINT_MAINNET, else we will use testnet
    try:
        indexer = IndexerClient(host=market_data_endpoint, api_timeout=5)
        logger.info("Initialized indexer client against %s", market_data_endpoint)
    except Exception:
        logger.exception("Failed to initialize indexer client for %s", market_data_endpoint)
        raise

    # Indexer Account = connection we will use to query our testnet trades
    try:
        indexer_account = IndexerClient(host=INDEXER_ACCOUNT_ENDPOINT, api_timeout=5)
        logger.info("Initialized account indexer client against %s", INDEXER_ACCOUNT_ENDPOINT)
    except Exception:
        logger.exception("Failed to initialize account indexer client for %s", INDEXER_ACCOUNT_ENDPOINT)
        raise

    # node = private connection we will use to send orders etc to the testnet or mainnet
    # Always use TESTNET for the connection, regardless of the is_testnet setting
    # The appropriate indexer endpoint will be used based on the is_testnet setting
    try:
        node = await NodeClient.connect(TESTNET.node)
        logger.info("Connected node client to %s", TESTNET.node)
    except Exception:
        logger.exception("Failed to connect node client to %s", TESTNET.node)
        raise

    try:
        wallet = await Wallet.from_mnemonic(node, MNEMONIC, DYDX_ADDRESS)
        logger.info("Loaded wallet for address %s", DYDX_ADDRESS)
    except Exception:
        logger.exception("Failed to derive wallet for address %s", DYDX_ADDRESS)
        raise

    client = Client(indexer, indexer_account, node, wallet)
    await check_juristiction(client, "BTC-USD")
    return client


# Check Juristiction
# DYDX no longer allows trading in certain countries and blocks API access too
# This function serves as a check
async def check_juristiction(client, market):
    logger.info("Checking Jurisdiction for market %s", market)
    try:
        await get_candles_recent(client, market)
        logger.info("Jurisdiction check succeeded for %s", market)
    except Exception as e:
        logger.exception("Jurisdiction check failed for %s", market)
        if "403" in str(e):
            logger.error("FAILED: LOCATION ACCESS LIKELY PROHIBITED")
            logger.error("DYDX likely prohibits use from your country")
            logger.error(
                "Theoretically for learning purposes, a VPN could be used, but we cannot advise this"
            )
        exit(1)
