import json
import logging
import random
import time

from constants import DYDX_ADDRESS
from dydx_v4_client import MAX_CLIENT_ID, OrderFlags
from dydx_v4_client.indexer.rest.constants import OrderType
from dydx_v4_client.node.market import Market
from .func_public import get_markets
from .func_utils import format_number
from v4_proto.dydxprotocol.clob.order_pb2 import Order

logger = logging.getLogger(__name__)


# Cancel Order
async def cancel_order(client, order_id):
    order = await get_order(client, order_id)
    market = Market(
        (await client.indexer.markets.get_perpetual_markets(order["ticker"]))[
            "markets"
        ][order["ticker"]]
    )
    # Use the client's wallet address when available to derive client id
    address = getattr(client.wallet, "address", DYDX_ADDRESS)
    market_order_id = market.order_id(
        address, 0, random.randint(0, MAX_CLIENT_ID), OrderFlags.SHORT_TERM
    )
    market_order_id.client_id = int(order["clientId"])
    market_order_id.clob_pair_id = int(order["clobPairId"])
    current_block = await client.node.latest_block_height()
    good_til_block = current_block + 1 + 10
    cancel = await client.node.cancel_order(
        client.wallet, market_order_id, good_til_block=good_til_block
    )
    logger.info("Cancel order response: %s", cancel)
    logger.warning(
        "Attempted to cancel order for %s; please verify cancellation on the dashboard",
        order["ticker"],
    )


# Get Account
async def get_account(client):
    # Try client's wallet address first, fall back to configured DYDX_ADDRESS
    address = getattr(client.wallet, "address", DYDX_ADDRESS)
    try:
        account = await client.indexer_account.account.get_subaccount(address, 0)
    except Exception:
        # Fallback to configured DYDX_ADDRESS
        account = await client.indexer_account.account.get_subaccount(DYDX_ADDRESS, 0)
    return account["subaccount"]


# Get Open Positions
async def get_open_positions(client):
    # Try client's wallet address first, fall back to configured DYDX_ADDRESS
    address = getattr(client.wallet, "address", DYDX_ADDRESS)
    try:
        response = await client.indexer_account.account.get_subaccount(address, 0)
    except Exception:
        # If primary address fails (likely 404 for fresh account), try configured address
        try:
            response = await client.indexer_account.account.get_subaccount(
                DYDX_ADDRESS, 0
            )
        except Exception as e2:
            # Both addresses failed - likely fresh testnet account with no trading history
            import httpx

            if isinstance(e2, httpx.HTTPStatusError) and e2.response.status_code == 404:
                logger.debug(
                    "No subaccount found (404) - likely fresh testnet account")
                return {}
            raise e2
    return response["subaccount"]["openPerpetualPositions"]


# Get Existing Order
async def get_order(client, order_id):
    return await client.indexer_account.account.get_order(order_id)


# Get existing open positions
async def is_open_positions(client, market):
    # Protect API
    time.sleep(0.2)

    # Get positions (try wallet address then configured address)
    address = getattr(client.wallet, "address", DYDX_ADDRESS)
    try:
        response = await client.indexer_account.account.get_subaccount(address, 0)
    except Exception:
        try:
            response = await client.indexer_account.account.get_subaccount(
                DYDX_ADDRESS, 0
            )
        except Exception as e:
            # Both addresses failed - likely fresh testnet account
            import httpx

            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                logger.debug(
                    "No subaccount found (404) for market %s - likely fresh testnet account",
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


# Check order status
async def check_order_status(client, order_id):
    order = await client.indexer_account.account.get_order(order_id)
    if order["status"]:
        return order["status"]
    return "FAILED"


# Place market order
async def place_market_order(client, market, side, size, price, reduce_only):
    # Initialize
    ticker = market
    current_block = await client.node.latest_block_height()
    market = Market(
        (await client.indexer.markets.get_perpetual_markets(market))["markets"][market]
    )
    address = getattr(client.wallet, "address", DYDX_ADDRESS)
    market_order_id = market.order_id(
        address, 0, random.randint(0, MAX_CLIENT_ID), OrderFlags.SHORT_TERM
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
    # We do this as in the current V4 version at the time of developing this, the order response does not return the order number
    time.sleep(1.5)
    orders = await client.indexer_account.account.get_subaccount_orders(
        DYDX_ADDRESS,
        0,
        ticker,
        return_latest_orders="true",
    )

    # Get latest order id
    order_id = ""
    for order in orders:
        client_id = int(order["clientId"])
        clob_pair_id = int(order["clobPairId"])
        order["createdAtHeight"] = int(order["createdAtHeight"])
        if (
                client_id == market_order_id.client_id
                and clob_pair_id == market_order_id.clob_pair_id
        ):
            order_id = order["id"]
            break

    # Ensure latest order
    if order_id == "":
        sorted_orders = sorted(
            orders, key=lambda x: x["createdAtHeight"], reverse=True)
        logger.error(
            "Unable to detect latest order; most recent entry: %s", sorted_orders[0]
        )
        logger.error("Please verify the order status on the dashboard")
        exit(1)

    # Print something if error returned
    if "code" in str(order):
        logger.error("Order returned error payload: %s", order)

    # Return result
    return (order, order_id)


# Get Open Orders
async def cancel_all_orders(client):
    try:
        orders = await client.indexer_account.account.get_subaccount_orders(
            DYDX_ADDRESS, 0, status="OPEN"
        )
    except Exception as e:
        # If the account doesn't exist on the indexer (404) treat as no open orders
        logger.warning("Could not fetch open orders: %s", e)
        return []

    if len(orders) > 0:
        for order in orders:
            await cancel_order(client, order["id"])
            logger.warning(
                "Open order %s may persist; verify cancellation on the dashboard",
                order["id"],
            )
            exit(1)


# Abort all open positions
async def abort_all_positions(client):
    # Cancel all orders
    await cancel_all_orders(client)

    # Protect API
    time.sleep(0.5)

    # Get markets for reference of tick size
    markets = await get_markets(client)

    # Protect API
    time.sleep(0.5)

    # Get all open positions
    try:
        positions = await get_open_positions(client)
    except Exception as e:
        # If the indexer returns 404 or similar, assume no positions for this test account
        logger.warning("Could not fetch open positions: %s", e)
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
            time.sleep(0.2)

        # Override json file with empty list
        bot_agents = []
        with open("../bot_agents.json", "w") as f:
            json.dump(bot_agents, f)

        # Return closed orders
        return close_orders
