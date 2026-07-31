"""Private account operations and order management for dYdX."""

import asyncio
import random
from typing import Any, Optional, cast

from dydx_v4_client import MAX_CLIENT_ID, OrderFlags
from dydx_v4_client.indexer.rest.constants import OrderType
from dydx_v4_client.node.market import Market
from loguru import logger
from src.constants import DYDX_ADDRESS, DYDX_API_THROTTLE_SECONDS, SUBACCOUNT_NUMBER
from src.shared.utils import format_number
from src.trading.arbitrage_observability import increment_metric
from src.trading.arbitrage_runtime_config import is_arbitrage_improvements_enabled
from src.trading.bot_agents_state import clear_tracked_positions
from src.trading.market_data import get_markets
from v4_proto.dydxprotocol.clob.order_pb2 import Order


def _resolve_client_address(client) -> str:
    """Resolve the best available wallet address as a concrete string."""
    # Prefer the live wallet address on the client (set when connect_dydx_runtime succeeds)
    if client.wallet is not None:
        addr = str(getattr(client.wallet, "address", "") or "").strip()
        if addr:
            return addr
    # Fall back to the module-level constant (global config, single-instance mode)
    addr = str(DYDX_ADDRESS or "").strip()
    if not addr:
        raise RuntimeError(
            "No dYdX address available: client wallet is unset and DYDX_ADDRESS is empty. "
            "Ensure the instance config contains a valid dydx_chain_address."
        )
    return addr


def _resolve_subaccount_number() -> int:
    """Resolve the configured dYdX subaccount number for this runtime."""
    return int(SUBACCOUNT_NUMBER)


async def _get_subaccount_with_metrics(client, address: str) -> dict[str, Any]:
    """Fetch subaccount payload and track API/provider metrics."""
    increment_metric("exchange_api_calls_total")
    try:
        return await client.indexer_account.account.get_subaccount(
            address, _resolve_subaccount_number()
        )
    except Exception:
        increment_metric("provider_errors_total")
        raise


async def _get_perpetual_markets_with_metrics(client, ticker: str) -> dict[str, Any]:
    """Fetch perpetual market metadata directly from provider with metrics."""
    increment_metric("exchange_api_calls_total")
    try:
        return await client.indexer.markets.get_perpetual_markets(ticker)
    except Exception:
        increment_metric("provider_errors_total")
        raise


async def _get_order_with_metrics(client, order_id: str) -> dict[str, Any]:
    """Fetch order payload and track API/provider metrics."""
    increment_metric("exchange_api_calls_total")
    try:
        return await client.indexer_account.account.get_order(order_id)
    except Exception:
        increment_metric("provider_errors_total")
        raise


async def _get_subaccount_orders_with_metrics(client, *args, **kwargs) -> Any:
    """Fetch subaccount orders and track API/provider metrics."""
    increment_metric("exchange_api_calls_total")
    try:
        return await client.indexer_account.account.get_subaccount_orders(
            *args, **kwargs
        )
    except Exception:
        increment_metric("provider_errors_total")
        raise


async def cancel_order(client, order_id):
    """Cancel an existing open order."""
    order = await get_order(client, order_id)
    ticker = str(order["ticker"])
    if is_arbitrage_improvements_enabled():
        markets_payload = await get_markets(client)
    else:
        markets_payload = await _get_perpetual_markets_with_metrics(client, ticker)
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
        account = await _get_subaccount_with_metrics(client, address)
    except Exception:
        # Fallback to configured DYDX_ADDRESS
        account = await _get_subaccount_with_metrics(client, DYDX_ADDRESS)
    return account["subaccount"]


async def get_open_positions(client):
    """Get all open perpetual positions."""
    # Try client's wallet address first, fall back to configured DYDX_ADDRESS
    address = _resolve_client_address(client)
    try:
        response = await _get_subaccount_with_metrics(client, address)
    except Exception:
        # If primary address fails (likely 404 for fresh account), try configured address
        try:
            response = await _get_subaccount_with_metrics(client, DYDX_ADDRESS)
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
    return await _get_order_with_metrics(client, order_id)


async def get_order_fills(client, order_id, market=None, limit: int = 100):
    """Get recent fills for an order, filtered client-side by order id."""
    address = _resolve_client_address(client)
    fills = await client.indexer_account.account.get_subaccount_fills(
        address,
        _resolve_subaccount_number(),
        ticker=market,
        limit=limit,
    )
    if isinstance(fills, dict):
        fills = fills.get("fills", [])
    if not isinstance(fills, list):
        return []

    order_id_text = str(order_id)
    return [
        fill
        for fill in fills
        if isinstance(fill, dict)
        if str(fill.get("orderId") or fill.get("order_id") or fill.get("orderID") or "")
        == order_id_text
    ]


async def is_open_positions(client, market):
    """Check if there are any open positions for a specific market."""
    # Protect API
    if DYDX_API_THROTTLE_SECONDS > 0:
        await asyncio.sleep(DYDX_API_THROTTLE_SECONDS)

    # Get positions (try wallet address then configured address)
    address = _resolve_client_address(client)
    try:
        response = await _get_subaccount_with_metrics(client, address)
    except Exception:
        try:
            response = await _get_subaccount_with_metrics(client, DYDX_ADDRESS)
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
    order = await _get_order_with_metrics(client, order_id)
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
    if is_arbitrage_improvements_enabled():
        markets_payload = await get_markets(client)
    else:
        markets_payload = await _get_perpetual_markets_with_metrics(client, ticker)
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

    order_lookup_address = _resolve_client_address(client)
    order_id = await _resolve_recent_order_id(
        client=client,
        order_lookup_address=order_lookup_address,
        ticker=ticker,
        market_order_id=market_order_id,
        expected_side=side,
        expected_size=size,
        expected_reduce_only=reduce_only,
    )

    # Print something if error returned
    if "code" in str(order):
        logger.error("Order returned error payload: {}", order)

    # Return result
    return (order, order_id)


def _normalize_orders_payload(raw_orders: Any) -> list[dict[str, Any]]:
    """Normalize indexer order payloads to a homogeneous list of dicts."""
    if isinstance(raw_orders, dict):
        raw_orders = raw_orders.get("orders", [])
    if not isinstance(raw_orders, list):
        return []
    return [order for order in raw_orders if isinstance(order, dict)]


def _safe_int(value: Any, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _resolve_order_from_snapshot(
    orders: list[dict[str, Any]],
    *,
    market_order_id,
    expected_side: str,
    expected_size: Any,
    expected_reduce_only: bool,
    allow_fallback: bool = False,
) -> Optional[str]:
    """Resolve placed order ID from a recent indexer snapshot."""
    expected_client_id = int(market_order_id.client_id)
    expected_clob_pair_id = int(market_order_id.clob_pair_id)

    # Primary deterministic match: clientId + clobPairId.
    for order in orders:
        client_id = _safe_int(order.get("clientId"))
        clob_pair_id = _safe_int(order.get("clobPairId"))
        if client_id == expected_client_id and clob_pair_id == expected_clob_pair_id:
            return str(order.get("id", "")) or None

    if not allow_fallback:
        return None

    # Fallback: latest order with same pair + side + reduceOnly + compatible size.
    normalized_side = str(expected_side or "").upper()
    normalized_reduce_only = bool(expected_reduce_only)
    expected_size_value = abs(_safe_float(expected_size, 0.0))

    candidates = []
    for order in orders:
        clob_pair_id = _safe_int(order.get("clobPairId"))
        if clob_pair_id != expected_clob_pair_id:
            continue

        order_side = str(order.get("side", "")).upper()
        if order_side and normalized_side and order_side != normalized_side:
            continue

        order_reduce_only = bool(order.get("reduceOnly", False))
        if order_reduce_only != normalized_reduce_only:
            continue

        order_size = abs(_safe_float(order.get("size"), 0.0))
        if expected_size_value > 0 and order_size > 0:
            # Accept tiny rounding differences.
            if abs(order_size - expected_size_value) > max(
                1e-9, expected_size_value * 1e-6
            ):
                continue

        candidates.append(order)

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: _safe_int(item.get("createdAtHeight"), default=0),
        reverse=True,
    )
    return str(candidates[0].get("id", "")) or None


async def _resolve_recent_order_id(
    *,
    client,
    order_lookup_address: str,
    ticker: str,
    market_order_id,
    expected_side: str,
    expected_size: Any,
    expected_reduce_only: bool,
    max_attempts: int = 5,
    initial_delay_seconds: float = 1.2,
    retry_delay_seconds: float = 0.75,
) -> str:
    """Retry indexer lookups to resolve recently placed order ID."""
    latest_snapshot: list[dict[str, Any]] = []

    for attempt in range(1, max_attempts + 1):
        delay = (
            initial_delay_seconds
            if attempt == 1
            else min(2.5, retry_delay_seconds * attempt)
        )
        await asyncio.sleep(delay)

        try:
            raw_orders = await _get_subaccount_orders_with_metrics(
                client,
                order_lookup_address,
                _resolve_subaccount_number(),
                ticker,
                return_latest_orders="true",
            )
        except Exception as exc:
            logger.warning(
                "Order lookup attempt {}/{} failed for {}: {}",
                attempt,
                max_attempts,
                ticker,
                exc,
            )
            continue

        orders = _normalize_orders_payload(raw_orders)
        if orders:
            latest_snapshot = orders

        order_id = _resolve_order_from_snapshot(
            orders,
            market_order_id=market_order_id,
            expected_side=expected_side,
            expected_size=expected_size,
            expected_reduce_only=expected_reduce_only,
            allow_fallback=(attempt == max_attempts),
        )
        if order_id:
            return order_id

        logger.warning(
            "Order lookup attempt {}/{} for {} found {} orders but no deterministic match yet",
            attempt,
            max_attempts,
            ticker,
            len(orders),
        )

    if latest_snapshot:
        sorted_orders = sorted(
            latest_snapshot,
            key=lambda item: _safe_int(item.get("createdAtHeight"), default=0),
            reverse=True,
        )
        logger.error(
            "Unable to detect latest order; most recent entry: {}", sorted_orders[0]
        )
    else:
        logger.error(
            "Unable to detect latest order; indexer returned no orders for {}", ticker
        )

    logger.error("Please verify the order status on the dashboard")
    raise RuntimeError(
        "Unable to detect latest exchange order id after placement "
        "(indexer lookup lag or payload mismatch)"
    )


async def cancel_all_orders(client):
    """Cancel all open orders."""
    try:
        order_lookup_address = _resolve_client_address(client)
        orders = await _get_subaccount_orders_with_metrics(
            client, order_lookup_address, _resolve_subaccount_number(), status="OPEN"
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
            order, order_id = await place_market_order(
                client, market, side, pos["sumOpen"], accept_price, True
            )

            # Append the result
            close_orders.append(order)

            # Protect API
            if DYDX_API_THROTTLE_SECONDS > 0:
                await asyncio.sleep(DYDX_API_THROTTLE_SECONDS)

    await clear_tracked_positions()

    # Return closed orders
    return close_orders
