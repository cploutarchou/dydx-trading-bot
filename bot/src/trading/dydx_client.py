"""dYdX network client connection management."""

import os
from datetime import datetime, timedelta, timezone

from dydx_v4_client.indexer.rest.indexer_client import IndexerClient
from dydx_v4_client.network import make_mainnet, make_testnet
from dydx_v4_client.node.client import NodeClient
from dydx_v4_client.wallet import Wallet
from loguru import logger

from src.constants import (
    DYDX_ADDRESS,
    INDEXER_ENDPOINT_TESTNET,
    INDEXER_ENDPOINT_MAINNET,
    MARKET_DATA_MODE,
    MNEMONIC,
)
from src.trading.market_data import get_candles_recent

_JURISDICTION_CHECK_TTL = timedelta(minutes=10)
_jurisdiction_success_cache: dict[str, datetime] = {}


def _is_placeholder_value(value: str) -> bool:
    """Return True when value is empty or clearly a template placeholder."""
    if not value:
        return True
    v = value.strip().lower()
    placeholder_tokens = (
        "your_",
        "_here",
        "example",
        "changeme",
        "change-me",
        "placeholder",
        "${",
    )
    return any(token in v for token in placeholder_tokens)


class Client:
    """dYdX client wrapper encapsulating indexer, account indexer, node, and wallet."""

    def __init__(self, indexer, indexer_account, node, wallet):
        """Initialize client with connection objects."""
        self.indexer = indexer
        self.indexer_account = indexer_account
        self.node = node
        self.wallet = wallet


def _resolve_runtime_network(is_testnet: bool):
    """Build the dYdX network configuration for the requested environment."""
    if is_testnet:
        return make_testnet(
            rest_indexer=INDEXER_ENDPOINT_TESTNET,
            websocket_indexer="wss://indexer.v4testnet.dydx.exchange/v4/ws",
            node_url=os.getenv("DYDX_TESTNET_NODE_URL", "test-dydx-grpc.kingnodes.com"),
        )

    node_url = os.getenv("DYDX_MAINNET_NODE_URL", "").strip()
    if not node_url:
        raise RuntimeError("DYDX_MAINNET_NODE_URL is required for mainnet runtime checks")

    return make_mainnet(
        rest_indexer=INDEXER_ENDPOINT_MAINNET,
        websocket_indexer="wss://indexer.dydx.trade/v4/ws",
        node_url=node_url,
    )


async def connect_dydx():
    """
    Connect to dYdX network and initialize all necessary clients.

    Returns:
        Client: Initialized client with all connections

    Raises:
        Exception: If any connection fails
    """
    return await connect_dydx_runtime(
        address=DYDX_ADDRESS,
        mnemonic=MNEMONIC,
        is_testnet=(MARKET_DATA_MODE == "TESTNET"),
    )


async def connect_dydx_runtime(address: str, mnemonic: str, is_testnet: bool) -> Client:
    """
    Connect to dYdX using explicit runtime credentials and environment selection.

    This is used both for managed runtime instances and readiness checks.
    """
    logger.info(
        "Initializing dYdX clients for runtime environment={}",
        "testnet" if is_testnet else "mainnet",
    )

    market_data_endpoint = INDEXER_ENDPOINT_TESTNET if is_testnet else INDEXER_ENDPOINT_MAINNET
    account_indexer_endpoint = market_data_endpoint
    logger.debug(
        "Market data endpoint resolved to {} (environment={})",
        market_data_endpoint,
        "TESTNET" if is_testnet else "MAINNET",
    )

    try:
        indexer = IndexerClient(host=market_data_endpoint, api_timeout=5)
        logger.info("Initialized indexer client against {}", market_data_endpoint)
    except Exception:
        logger.exception("Failed to initialize indexer client for {}", market_data_endpoint)
        raise

    try:
        indexer_account = IndexerClient(host=account_indexer_endpoint, api_timeout=5)
        logger.info(
            "Initialized account indexer client against {}", account_indexer_endpoint
        )
    except Exception:
        logger.exception(
            "Failed to initialize account indexer client for {}",
            account_indexer_endpoint,
        )
        raise

    network_config = _resolve_runtime_network(is_testnet)
    try:
        node = await NodeClient.connect(network_config.node)
        logger.info(
            "Connected node client to {} network config",
            "testnet" if is_testnet else "mainnet",
        )
    except Exception:
        logger.exception(
            "Failed to connect node client to {} network config",
            "testnet" if is_testnet else "mainnet",
        )
        raise

    wallet = None
    if not _is_placeholder_value(mnemonic) and not _is_placeholder_value(address):
        try:
            wallet = await Wallet.from_mnemonic(node, mnemonic, address)
            logger.info("Loaded wallet for address {}", address)
        except Exception:
            logger.warning(
                "Failed to derive wallet for address {}. Continuing without wallet.",
                address,
            )
    else:
        logger.info("Wallet creation skipped (missing runtime credential material)")

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
        RuntimeError: If jurisdiction check fails (access prohibited)
    """
    now = datetime.now(timezone.utc)
    last_success = _jurisdiction_success_cache.get(market)
    if last_success is not None and (now - last_success) < _JURISDICTION_CHECK_TTL:
        logger.debug(
            "Skipping jurisdiction re-check for {} (last success at {})",
            market,
            last_success.isoformat(),
        )
        return

    logger.info("Checking Jurisdiction for market {}", market)
    try:
        await get_candles_recent(client, market)
        _jurisdiction_success_cache[market] = now
        logger.info("Jurisdiction check succeeded for {}", market)
    except Exception as e:
        logger.exception("Jurisdiction check failed for {}", market)
        if "403" in str(e):
            logger.error("FAILED: LOCATION ACCESS LIKELY PROHIBITED")
            logger.error("DYDX likely prohibits use from your country")
            logger.error(
                "Theoretically for learning purposes, a VPN could be used, but we cannot advise this"
            )
        raise RuntimeError(
            f"Jurisdiction check failed for {market}; access may be restricted"
        ) from e
