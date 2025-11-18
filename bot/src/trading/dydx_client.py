"""dYdX network client connection management."""
import logging

from src.constants import (
    DYDX_ADDRESS,
    INDEXER_ACCOUNT_ENDPOINT,
    INDEXER_ENDPOINT_MAINNET,
    MARKET_DATA_MODE,
    MNEMONIC,
)
from dydx_v4_client.indexer.rest.indexer_client import IndexerClient
from dydx_v4_client.network import TESTNET
from dydx_v4_client.node.client import NodeClient
from dydx_v4_client.wallet import Wallet
from src.trading.market_data import get_candles_recent

logger = logging.getLogger(__name__)


class Client:
    """dYdX client wrapper encapsulating indexer, account indexer, node, and wallet."""

    def __init__(self, indexer, indexer_account, node, wallet):
        """Initialize client with connection objects."""
        self.indexer = indexer
        self.indexer_account = indexer_account
        self.node = node
        self.wallet = wallet


async def connect_dydx():
    """
    Connect to dYdX network and initialize all necessary clients.

    Returns:
        Client: Initialized client with all connections

    Raises:
        Exception: If any connection fails
    """
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
        logger.info("Initialized indexer client against %s",
                    market_data_endpoint)
    except Exception:
        logger.exception(
            "Failed to initialize indexer client for %s", market_data_endpoint
        )
        raise

    # Indexer Account = connection we will use to query our testnet trades
    try:
        indexer_account = IndexerClient(
            host=INDEXER_ACCOUNT_ENDPOINT, api_timeout=5)
        logger.info(
            "Initialized account indexer client against %s", INDEXER_ACCOUNT_ENDPOINT
        )
    except Exception:
        logger.exception(
            "Failed to initialize account indexer client for %s",
            INDEXER_ACCOUNT_ENDPOINT,
        )
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

    # For backtesting, we don't need a real wallet since we're simulating trades
    wallet = None
    if MNEMONIC and DYDX_ADDRESS and not DYDX_ADDRESS.startswith('${'):
        try:
            wallet = await Wallet.from_mnemonic(node, MNEMONIC, DYDX_ADDRESS)
            logger.info("Loaded wallet for address %s", DYDX_ADDRESS)
        except Exception:
            logger.warning(
                "Failed to derive wallet for address %s. Continuing without wallet (backtesting mode).",
                DYDX_ADDRESS)
            # Don't raise - continue with None wallet for backtesting
    else:
        logger.info(
            "Wallet creation skipped (backtesting mode or missing config)")

    client = Client(indexer, indexer_account, node, wallet)
    await check_jurisdiction(client, "BTC-USD")
    return client


async def check_jurisdiction(client, market):
    """
    Check if market trading is allowed from current location.

    DYDX no longer allows trading in certain countries and blocks API access too.
    This function serves as a geographic access check.

    Args:
        client: dYdX client
        market: Market symbol to test

    Raises:
        SystemExit: If jurisdiction check fails (access prohibited)
    """
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

