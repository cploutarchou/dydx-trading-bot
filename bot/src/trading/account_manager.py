"""Private account operations and order management for dYdX."""

import asyncio
import json
import os
import random
from pathlib import Path
from typing import Any, cast

from dydx_v4_client import MAX_CLIENT_ID, OrderFlags
from dydx_v4_client.indexer.rest.constants import OrderType
from dydx_v4_client.node.market import Market
from loguru import logger
from v4_proto.dydxprotocol.clob.order_pb2 import Order

from src.constants import DYDX_ADDRESS, SUBACCOUNT_NUMBER
from src.shared.utils import format_number
from src.trading.market_data import get_markets


def _resolve_bot_agents_path() -> Path:
    """Resolve per-instance bot agents path from environment."""
    configured_path = os.getenv("BOT_AGENTS_FILE", "bot_agents.json")
    instance_id = os.getenv("BOT_INSTANCE_ID", "default")
    resolved = configured_path.replace("{instance_id}", instance_id)
    path = Path(resolved)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    return path


BOT_AGENTS_PATH = _resolve_bot_agents_path()


def _resolve_client_address(client) -> str:
    """Resolve the best available wallet address as a concrete string."""
    return str(getattr(client.wallet, "address", DYDX_ADDRESS) or DYDX_ADDRESS)


def _resolve_subaccount_number() -> int:
    """Resolve the configured dYdX subaccount number for this runtime."""
    return int(SUBACCOUNT_NUMBER)


async def cancel_order(client, order_id):
    """Cancel an existing open order."""
    order = await get_order(client, order_id)
    ticker = str(order["ticker"])
    markets_payload = await client.indexer.markets.get_perpetual_markets(ticker)
    market_payload = cast(dict[str, Any], markets_payload["markets"][ticker])
    market = Market(market_payload)
    # Use the client's wallet address when available to derive client id
    address = _resolve_client_address(client)
    market_order_id = market.order_id(
        address,
        _resolve_subaccount_number(),
        random.randint(0, MAX_CLIENT_ID),
        OrderFlags.SHORT_TERM,
    )
    market_order_id.client_id = int(order["clientId"])
    market_order_id.clob_pair_id = int(order["clobPairId"])
    current_block = await client.node.latest_block_height()
    good_til_block = current_block + 1 + 10
    cancel = await client.node.cancel_order(
        client.wallet, market_order_id, good_til_block=good_til_block
    )
    logger.info("Cancel order response: {}", cancel)
    logger.warning(
        "Attempted to cancel order for {}; please verify cancellation on the dashboard",
        ticker,
    )


async def get_account(client):
    """Get current account information."""
    # Try client's wallet address first, fall back to configured DYDX_ADDRESS
    address = _resolve_client_address(client)
    try:
        account = await client.indexer_account.account.get_subaccount(
            address, _resolve_subaccount_number()
        )
    except Exception:
        # Fallback to configured DYDX_ADDRESS
        account = await client.indexer_account.account.get_subaccount(
            DYDX_ADDRESS, _resolve_subaccount_number()
        )
    return account["subaccount"]


async def get_open_positions(client):
    """Get all open perpetual positions."""
    # Try client's wallet address first, fall back to configured DYDX_ADDRESS
    address = _resolve_client_address(client)
    try:
        response = await client.indexer_account.account.get_subaccount(
            address, _resolve_subaccount_number()
        )
    except Exception:
        # If primary address fails (likely 404 for fresh account), try configured address
        try:
            response = await client.indexer_account.account.get_subaccount(
                DYDX_ADDRESS, _resolve_subaccount_number()
            )
        except Exception as e2:
            # Both addresses failed - likely fresh testnet account with no trading history
            import httpx

            if isinstance(e2, httpx.HTTPStatusError) and e2.response.status_code == 404:
                logger.debug("No subaccount found (404) - likely fresh testnet account")
                return {}
            raise e2
    return response["subaccount"]["openPerpetualPositions"]


async def get_order(client, order_id):
    """Get details of a specific order."""
    return await client.indexer_account.account.get_order(order_id)


async def is_open_positions(client, market):
    """Check if there are any open positions for a specific market."""
    # Protect API
    await asyncio.sleep(0.2)

    # Get positions (try wallet address then configured address)
    address = _resolve_client_address(client)
    try:
        response = await client.indexer_account.account.get_subaccount(
            address, _resolve_subaccount_number()
        )
    except Exception:
        try:
            response = await client.indexer_account.account.get_subaccount(
                DYDX_ADDRESS, _resolve_subaccount_number()
            )
        except Exception as e:
            # Both addresses failed - likely fresh testnet account
            import httpx

            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                logger.debug(
                    "No subaccount found (404) for market {} - likely fresh testnet account",
                    market,
                )
                return False
            raise e

    open_positions = response["subaccount"]["openPerpetualPositions"]

    # Determine if open
    if len(open_positions) > 0:
        for token in open_positions.keys():
            if token == market:
                return True

    # Return False
    return False


async def check_order_status(client, order_id):
    """Check the current status of an order."""
    order = await client.indexer_account.account.get_order(order_id)
    if order["status"]:
        return order["status"]
    return "FAILED"


async def place_market_order(client, market, side, size, price, reduce_only):
    """
    Place a market order.

    Args:
        client: dYdX client
        market: Market symbol (e.g., "BTC-USD")
        side: "BUY" or "SELL"
        size: Order size
        price: Price level
        reduce_only: Whether this is a reduce-only order

    Returns:
        Tuple of (order, order_id)
    """
    # Initialize
    ticker = str(market)
    current_block = await client.node.latest_block_height()
    markets_payload = await client.indexer.markets.get_perpetual_markets(ticker)
    market_payload = cast(dict[str, Any], markets_payload["markets"][ticker])
    market = Market(market_payload)
    address = _resolve_client_address(client)
    market_order_id = market.order_id(
        address,
        _resolve_subaccount_number(),
        random.randint(0, MAX_CLIENT_ID),
        OrderFlags.SHORT_TERM,
    )
    good_til_block = current_block + 1 + 10

    # Set Time In Force
    time_in_force = Order.TIME_IN_FORCE_UNSPECIFIED

    # Place Market Order
    order = await client.node.place_order(
        client.wallet,
        market.order(
            market_order_id,
            order_type=OrderType.MARKET,  # type: ignore[arg-type]
            side=Order.Side.SIDE_BUY if side == "BUY" else Order.Side.SIDE_SELL,
            size=float(size),
            price=float(price),  # type: ignore[arg-type]
            time_in_force=time_in_force,
            reduce_only=reduce_only,
            good_til_block=good_til_block,
        ),
    )

    # Get Recent Orders
    # We do this as in the current V4 version at the time of developing this,
    # the order response does not return the order number
    await asyncio.sleep(1.5)
    order_lookup_address = _resolve_client_address(client)
    orders = await client.indexer_account.account.get_subaccount_orders(
        order_lookup_address,
        _resolve_subaccount_number(),
        ticker,
        return_latest_orders="true",
    )

    # Get latest order id
    order_id = ""
    for order in orders:
        client_id = int(order["clientId"])
        clob_pair_id = int(order["clobPairId"])
        order["createdAtHeight"] = int(order["createdAtHeight"])
        if client_id == market_order_id.client_id and clob_pair_id == market_order_id.clob_pair_id:
            order_id = order["id"]
            break

    # Ensure latest order
    if order_id == "":
        sorted_orders = sorted(orders, key=lambda x: x["createdAtHeight"], reverse=True)
        logger.error("Unable to detect latest order; most recent entry: {}", sorted_orders[0])
        logger.error("Please verify the order status on the dashboard")
        raise RuntimeError("Unable to detect latest exchange order id after placement")

    # Print something if error returned
    if "code" in str(order):
        logger.error("Order returned error payload: {}", order)

    # Return result
    return (order, order_id)


async def cancel_all_orders(client):
    """Cancel all open orders."""
    try:
        order_lookup_address = _resolve_client_address(client)
        orders = await client.indexer_account.account.get_subaccount_orders(
            order_lookup_address, _resolve_subaccount_number(), status="OPEN"
        )
    except Exception as e:
        # If the account doesn't exist on the indexer (404) treat as no open orders
        logger.warning("Could not fetch open orders: {}", e)
        return []

    if len(orders) > 0:
        for order in orders:
            await cancel_order(client, order["id"])
            logger.warning(
                "Open order {} may persist; verify cancellation on the dashboard",
                order["id"],
            )
        raise RuntimeError(
            "Cancellation requests submitted for open orders; verify dashboard before continuing"
        )


async def abort_all_positions(client):
    """
    Close all open positions by placing offsetting reduce-only orders.

    This is used for emergency shutdown or mode switch.
    """
    # Cancel all orders
    await cancel_all_orders(client)

    # Protect API
    await asyncio.sleep(0.5)

    # Get markets for reference of tick size
    markets = await get_markets(client)

    # Protect API
    await asyncio.sleep(0.5)

    # Get all open positions
    try:
        positions = await get_open_positions(client)
    except Exception as e:
        # If the indexer returns 404 or similar, assume no positions for this test account
        logger.warning("Could not fetch open positions: {}", e)
        return []

    # Handle open positions
    close_orders = []
    if len(positions) > 0:

        # Loop through each position
        for item in positions.keys():

            # Get Position
            pos = positions[item]

            # Determine Market
            market = pos["market"]

            # Determine Side
            side = "BUY"
            if pos["side"] == "LONG":
                side = "SELL"

            # Get Price
            price = float(pos["entryPrice"])
            accept_price = (
                price * 1.7 if side == "BUY" else price * 0.3
            )  # Helps towards ensuring order will be filled
            tick_size = markets["markets"][market]["tickSize"]
            accept_price = format_number(accept_price, tick_size)

            # Place order to close
            (order, order_id) = await place_market_order(
                client, market, side, pos["sumOpen"], accept_price, True
            )

            # Append the result
            close_orders.append(order)

            # Protect API
            await asyncio.sleep(0.2)

        # Override json file with empty list
        bot_agents = []
        with BOT_AGENTS_PATH.open("w", encoding="utf-8") as f:
            json.dump(bot_agents, f)

        # Return closed orders
        return close_orders
