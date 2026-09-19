"""Private account operations and order management for dYdX."""

import asyncio
import random
from typing import Any, Dict, List, Optional, Tuple, cast

from dydx_v4_client import MAX_CLIENT_ID, OrderFlags
from dydx_v4_client.indexer.rest.constants import OrderType
from dydx_v4_client.node.market import Market
from loguru import logger
from v4_proto.dydxprotocol.clob.order_pb2 import Order

from src.constants import DYDX_ADDRESS, DYDX_API_THROTTLE_SECONDS, SUBACCOUNT_NUMBER
from src.infrastructure import resilience
from src.shared.utils import format_number
from src.trading.arbitrage_observability import increment_metric
from src.trading.arbitrage_runtime_config import is_arbitrage_improvements_enabled
from src.trading.bot_agents_state import clear_tracked_positions
from src.trading.market_data import get_markets

# Upper bound for direct node (cometbft gRPC) calls. These have no internal
# deadline; without one a hung RPC would block the single-threaded trading
# loop indefinitely. Placing is followed by an indexer order-id resolution
# pass, so abandoning a slow response is recoverable.
NODE_CALL_TIMEOUT_SECONDS = 30.0


def _resolve_client_address(client: Any) -> str:
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


def resolve_client_address_or_none(client: Any) -> Optional[str]:
    """Non-raising variant of :func:`_resolve_client_address`.

    Used by callers that can meaningfully degrade when no address is
    resolvable (e.g. the portfolio drawdown peak store keys by address).
    Tolerates clients without a ``wallet`` attribute (test doubles).
    """
    try:
        return _resolve_client_address(client)
    except (RuntimeError, AttributeError):
        return None


def _resolve_subaccount_number() -> int:
    """Resolve the configured dYdX subaccount number for this runtime."""
    return int(SUBACCOUNT_NUMBER)


async def _get_subaccount_with_metrics(client: Any, address: str) -> dict[str, Any]:
    """Fetch subaccount payload and track API/provider metrics."""
    increment_metric("exchange_api_calls_total")
    try:
        return await resilience.call_async(
            "dydx_indexer",
            lambda: client.indexer_account.account.get_subaccount(
                address, _resolve_subaccount_number()
            ),
        )
    except Exception:
        increment_metric("provider_errors_total")
        raise


async def _get_perpetual_markets_with_metrics(
    client: Any, ticker: str
) -> dict[str, Any]:
    """Fetch perpetual market metadata directly from provider with metrics."""
    increment_metric("exchange_api_calls_total")
    try:
        return await resilience.call_async(
            "dydx_indexer",
            lambda: client.indexer.markets.get_perpetual_markets(ticker),
        )
    except Exception:
        increment_metric("provider_errors_total")
        raise


async def _get_order_with_metrics(client: Any, order_id: str) -> dict[str, Any]:
    """Fetch order payload and track API/provider metrics."""
    increment_metric("exchange_api_calls_total")
    try:
        return await resilience.call_async(
            "dydx_indexer",
            lambda: client.indexer_account.account.get_order(order_id),
        )
    except Exception:
        increment_metric("provider_errors_total")
        raise


async def _get_subaccount_orders_with_metrics(
    client: Any, *args: Any, **kwargs: Any
) -> Any:
    """Fetch subaccount orders and track API/provider metrics."""
    increment_metric("exchange_api_calls_total")
    try:
        return await resilience.call_async(
            "dydx_indexer",
            lambda: client.indexer_account.account.get_subaccount_orders(
                *args, **kwargs
            ),
        )
    except Exception:
        increment_metric("provider_errors_total")
        raise


async def cancel_order(client: Any, order_id: str) -> None:
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
    current_block = await asyncio.wait_for(
        client.node.latest_block_height(), timeout=NODE_CALL_TIMEOUT_SECONDS
    )
    good_til_block = current_block + 1 + 10
    cancel = await asyncio.wait_for(
        client.node.cancel_order(
            client.wallet, market_order_id, good_til_block=good_til_block
        ),
        timeout=NODE_CALL_TIMEOUT_SECONDS,
    )
    logger.info("Cancel order response: {}", cancel)
    logger.warning(
        "Attempted to cancel order for {}; please verify cancellation on the dashboard",
        ticker,
    )


# Order statuses that mean the order can no longer fill. Anything else
# (OPEN, PENDING, UNTRIGGERED, UNKNOWN from an unreadable payload) keeps the
# verification loop retrying — fail-closed for live orders.
_CANCEL_TERMINAL_STATUSES = {
    "FILLED",
    "CANCELED",
    "CANCELLED",
    "BEST_EFFORT_CANCELED",
    "IB_CANCELED",
    "REJECTED",
    "EXPIRED",
}


async def cancel_order_verified(client: Any, order_id: str, attempts: int = 3) -> str:
    """Cancel an order and VERIFY it can no longer fill.

    A submitted cancel can fail silently (node rejection, good-til-block
    already lapsed): without a status re-read the order stays live and can
    fill later, untracked. Re-reads the order after each cancel attempt and
    retries while the status is not terminal. Returns the final status.
    """
    status = str(await check_order_status(client, order_id) or "").strip().upper()
    for attempt in range(1, attempts + 1):
        if status in _CANCEL_TERMINAL_STATUSES:
            return status
        logger.warning(
            "Verified cancel attempt {}/{} for order {} (status={})",
            attempt,
            attempts,
            order_id,
            status or "unknown",
        )
        await cancel_order(client, order_id)
        await asyncio.sleep(1.0)
        status = str(await check_order_status(client, order_id) or "").strip().upper()
    return status


async def get_account(client: Any) -> Any:
    """Get current account information."""
    # _resolve_client_address already falls back to the configured address
    # when the client has no wallet; a second cross-address retry here would
    # silently return ANOTHER account's equity/positions whenever the two
    # addresses differ, so failures propagate (fail-closed) instead.
    address = _resolve_client_address(client)
    account = await _get_subaccount_with_metrics(client, address)
    return account["subaccount"]


async def get_open_positions(client: Any) -> Any:
    """Get all open perpetual positions."""
    address = _resolve_client_address(client)
    try:
        response = await _get_subaccount_with_metrics(client, address)
    except Exception as e:
        # A missing subaccount (404) genuinely means no positions; any other
        # failure must propagate so risk/exit decisions fail closed.
        import httpx

        if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
            logger.debug("No subaccount found (404) - likely fresh testnet account")
            return {}
        raise
    return response["subaccount"]["openPerpetualPositions"]


def _unwrap_order_payload(payload: Any) -> dict[str, Any]:
    """Normalize an indexer order payload.

    The dYdX v4 indexer GET /v4/orders/{id} response wraps the order record in
    an ``"order"`` key; some older code paths return the flat record. Accept
    both so downstream field access cannot raise KeyError on the nested shape.
    """
    if isinstance(payload, dict) and isinstance(payload.get("order"), dict):
        return cast(dict[str, Any], payload["order"])
    return cast(dict[str, Any], payload)


async def get_order(client: Any, order_id: str) -> dict[str, Any]:
    """Get details of a specific order (unwrapped to a flat order record)."""
    return _unwrap_order_payload(await _get_order_with_metrics(client, order_id))


async def get_order_fills(
    client: Any,
    order_id: str,
    market: Optional[str] = None,
    limit: int = 100,
    max_pages: int = 5,
) -> List[Any]:
    """Get fills for an order, filtered client-side by order id.

    Paginates backwards via created_before_or_at (up to max_pages pages) so a
    busy subaccount's recent fills do not hide an older order's fills — the
    previous single-page read capped at 100 fills, which truncated VWAP and
    partial-fill verification on active accounts.
    """
    address = _resolve_client_address(client)
    collected: List[Any] = []
    seen_fill_ids: set[str] = set()
    cursor: Optional[str] = None

    for _page in range(max(1, max_pages)):
        cursor_kwargs: Dict[str, Any] = {}
        if cursor:
            cursor_kwargs["created_before_or_at"] = cursor
        fills = await client.indexer_account.account.get_subaccount_fills(
            address,
            _resolve_subaccount_number(),
            ticker=market,
            limit=limit,
            **cursor_kwargs,
        )
        if isinstance(fills, dict):
            fills = fills.get("fills", [])
        if not isinstance(fills, list) or not fills:
            break

        # The next (older) page starts at the OLDEST fill of this page. Using
        # the minimum timestamp (not a position) keeps this correct whatever
        # order the indexer returns. The bound is inclusive, which re-delivers
        # the boundary fill; ids de-duplicate it. Indexer timestamps share one
        # ISO-8601 UTC format, so they order lexicographically.
        page_cursor: Optional[str] = None
        new_fills = 0
        for fill in fills:
            if not isinstance(fill, dict):
                continue
            created_at = str(fill.get("createdAt") or fill.get("created_at") or "")
            if created_at and (page_cursor is None or created_at < page_cursor):
                page_cursor = created_at
            fill_id = str(fill.get("id") or fill.get("uuid") or "")
            if fill_id and fill_id in seen_fill_ids:
                continue
            if fill_id:
                seen_fill_ids.add(fill_id)
            collected.append(fill)
            new_fills += 1
        if len(fills) < limit:
            break
        if new_fills == 0 or page_cursor is None or page_cursor == cursor:
            # No progress is possible (no timestamps, or a full page sharing
            # one timestamp): stop instead of re-reading the same window.
            break
        cursor = page_cursor

    order_id_text = str(order_id)
    return [
        fill
        for fill in collected
        if str(fill.get("orderId") or fill.get("order_id") or fill.get("orderID") or "")
        == order_id_text
    ]


async def is_open_positions(client: Any, market: str) -> bool:
    """Check if there are any open positions for a specific market."""
    # Protect API
    if DYDX_API_THROTTLE_SECONDS > 0:
        await asyncio.sleep(DYDX_API_THROTTLE_SECONDS)

    # Get positions (fail-closed: no cross-address fallback — see get_account)
    address = _resolve_client_address(client)
    try:
        response = await _get_subaccount_with_metrics(client, address)
    except Exception as e:
        import httpx

        if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
            logger.debug(
                "No subaccount found (404) for market {} - likely fresh testnet account",
                market,
            )
            return False
        raise

    open_positions = response["subaccount"]["openPerpetualPositions"]

    # Determine if open
    if len(open_positions) > 0:
        for token in open_positions.keys():
            if token == market:
                return True

    # Return False
    return False


async def check_order_status(client: Any, order_id: str) -> str:
    """Check the current status of an order."""
    order = _unwrap_order_payload(await _get_order_with_metrics(client, order_id))
    status = order.get("status") if isinstance(order, dict) else None
    if status:
        # Typed local binds the Any payload value to the -> str contract.
        status_str: str = str(status)
        return status_str
    # A missing/unreadable status is NOT evidence of failure — reporting
    # FAILED here would let callers skip hedging a leg that actually filled.
    # UNKNOWN routes callers into their cancel-then-verify-fills path instead.
    return "UNKNOWN"


async def place_market_order(
    client: Any,
    market: str,
    side: str,
    size: Any,
    price: Any,
    reduce_only: bool,
) -> Tuple[Any, str]:
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
    # Bounded node calls: a hung RPC must not stall the trading loop forever.
    current_block = await asyncio.wait_for(
        client.node.latest_block_height(), timeout=NODE_CALL_TIMEOUT_SECONDS
    )
    if is_arbitrage_improvements_enabled():
        markets_payload = await get_markets(client)
    else:
        markets_payload = await _get_perpetual_markets_with_metrics(client, ticker)
    market_payload = cast(dict[str, Any], markets_payload["markets"][ticker])
    market_obj = Market(market_payload)
    address = _resolve_client_address(client)
    market_order_id = market_obj.order_id(
        address,
        _resolve_subaccount_number(),
        random.randint(0, MAX_CLIENT_ID),
        OrderFlags.SHORT_TERM,
    )
    good_til_block = current_block + 1 + 10

    # Set Time In Force
    time_in_force = Order.TIME_IN_FORCE_UNSPECIFIED

    # Place Market Order
    order = await asyncio.wait_for(
        client.node.place_order(
            client.wallet,
            market_obj.order(
                market_order_id,
                order_type=OrderType.MARKET,
                side=Order.Side.SIDE_BUY if side == "BUY" else Order.Side.SIDE_SELL,
                size=float(size),
                price=float(price),
                time_in_force=time_in_force,
                reduce_only=reduce_only,
                good_til_block=good_til_block,
            ),
        ),
        timeout=NODE_CALL_TIMEOUT_SECONDS,
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
    market_order_id: Any,
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
    client: Any,
    order_lookup_address: str,
    ticker: str,
    market_order_id: Any,
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


async def cancel_all_orders(
    client: Any, markets: Optional[List[str]] = None
) -> Optional[List[Any]]:
    """Cancel all open orders, optionally scoped to specific markets.

    Returns the list of cancelled order ids (empty when none were open).
    Raises after best-effort cancellation when any individual cancel fails or
    the open-orders fetch fails for a non-404 reason, so callers can alert —
    unknown live orders must never be treated as cancelled.

    ``markets`` scopes both the order lookup and the cancels: on a shared
    subaccount an instance must not cancel other instances' orders.
    """
    # ``None`` means whole subaccount; an empty collection means "scope to
    # nothing" and must never widen to every market.
    market_filter = (
        {str(m).strip() for m in markets if str(m).strip()}
        if markets is not None
        else None
    )
    if market_filter is not None and not market_filter:
        return []
    try:
        order_lookup_address = _resolve_client_address(client)
        raw_orders = await _get_subaccount_orders_with_metrics(
            client,
            order_lookup_address,
            _resolve_subaccount_number(),
            status="OPEN",
        )
    except Exception as e:
        # A missing subaccount (404) genuinely means no open orders; any other
        # failure must fail closed — proceeding with unknown live orders would
        # let them fill during/after an emergency abort.
        import httpx

        if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
            logger.warning("No subaccount on indexer (404); assuming no open orders")
            return []
        logger.error("Could not fetch open orders during cancel-all: {}", e)
        raise

    # The indexer returns {"orders": [...]}; normalize before iterating so the
    # loop sees order dicts, not the payload's keys.
    orders = _normalize_orders_payload(raw_orders)
    if market_filter is not None:
        orders = [
            order
            for order in orders
            if str(order.get("ticker") or "").strip() in market_filter
        ]
    if not orders:
        return []

    cancelled: List[str] = []
    failures: List[str] = []
    for order in orders:
        order_id = str(order.get("id", ""))
        try:
            final_status = await cancel_order_verified(client, order_id)
            if final_status in _CANCEL_TERMINAL_STATUSES:
                cancelled.append(order_id)
            else:
                # The cancel was submitted but the order still reports a
                # fillable state — treat as failed so the caller alerts.
                failures.append(order_id or "<unknown-id>")
                logger.error(
                    "Order {} still reports status {} after verified cancels",
                    order_id,
                    final_status or "unknown",
                )
        except Exception as e:
            failures.append(order_id or "<unknown-id>")
            logger.error("Failed to cancel open order {}: {}", order_id or "?", e)

    if failures:
        raise RuntimeError(
            "cancel-all: cancellation failed for order id(s) "
            f"{', '.join(failures)}; manual verification required before continuing"
        )
    return cancelled


async def abort_all_positions(
    client: Any, markets: Optional[List[str]] = None
) -> List[Any]:
    """
    Close open positions by placing offsetting reduce-only orders.

    This is used for emergency shutdown or mode switch. Fail-closed design:
    positions are always flattened best-effort (a failed cancel or a single
    failed close must not skip the remaining closes) and any failure is
    re-raised afterwards so the caller aborts with a CRITICAL signal instead
    of silently continuing. Tracked state is cleared unless the account could
    not be confirmed flat (position fetch failed or a close order failed); in
    that case it is kept so the possible exposure is not forgotten.

    ``markets`` scopes the abort to this instance's tracked markets: orders
    are cancelled and positions closed only on those markets, so on a shared
    subaccount one instance's abort does not flatten other instances'
    positions. ``None`` (default) keeps the legacy whole-subaccount kill
    switch semantics; an empty collection scopes the abort to nothing.
    """
    cleanup_errors: List[str] = []
    market_scope: Optional[set[str]] = (
        {str(m).strip() for m in markets if str(m).strip()}
        if markets is not None
        else None
    )
    if market_scope is not None and not market_scope:
        # An instance that tracks no markets has nothing to abort. Falling
        # through with an empty scope used to widen to the whole subaccount.
        logger.info("Scoped abort with no tracked markets; nothing to cancel or close")
        return []

    # Cancel open orders (best-effort; failures surface after flattening)
    try:
        await cancel_all_orders(client, markets=markets)
    except Exception as e:
        cleanup_errors.append(f"cancel_all_orders: {e}")
        logger.critical("cancel-all failed during abort; continuing to flatten: {}", e)

    # Protect API
    await asyncio.sleep(0.5)

    # Get markets metadata for reference of tick size (the ``markets``
    # parameter holds the market-scope list; keep the names distinct).
    markets_meta = await get_markets(client)

    # Protect API
    await asyncio.sleep(0.5)

    # Get all open positions
    exposure_unknown = False
    try:
        positions = await get_open_positions(client)
    except Exception as e:
        # get_open_positions already maps a missing subaccount (404) to "no
        # positions"; anything reaching here is unknown exposure and must fail
        # closed instead of being treated as a flat account.
        positions = {}
        exposure_unknown = True
        cleanup_errors.append(f"get_open_positions: {e}")
        logger.critical(
            "Could not fetch open positions during abort; exposure unknown: {}", e
        )

    # Handle open positions
    close_orders = []
    if len(positions) > 0:

        # Loop through each position; isolate failures so every position gets
        # a close attempt.
        for item in positions.keys():

            # Get Position
            pos = positions[item]

            if market_scope is not None and str(item).strip() not in market_scope:
                logger.info(
                    "Skipping {} during scoped abort (not tracked by this instance)",
                    item,
                )
                continue

            try:
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
                tick_size = markets_meta["markets"][market]["tickSize"]
                accept_price_formatted = format_number(accept_price, tick_size)

                # Place order to close
                order, order_id = await place_market_order(
                    client, market, side, pos["sumOpen"], accept_price_formatted, True
                )

                # Append the result
                close_orders.append(order)
            except Exception as e:
                exposure_unknown = True
                cleanup_errors.append(f"close {pos.get('market', item)}: {e}")
                logger.critical(
                    "Failed to place close order for {} during abort: {}",
                    pos.get("market", item),
                    e,
                )

            # Protect API
            if DYDX_API_THROTTLE_SECONDS > 0:
                await asyncio.sleep(DYDX_API_THROTTLE_SECONDS)

    if exposure_unknown:
        # Positions may still be open; keep the tracked state so the next start
        # and the operator still know about the possible exposure.
        logger.critical(
            "Keeping tracked positions: abort could not confirm the account is flat"
        )
    else:
        await clear_tracked_positions()

    if cleanup_errors:
        raise RuntimeError(
            "abort_all_positions completed best-effort cleanup with failures: "
            + "; ".join(cleanup_errors)
        )

    # Return closed orders
    return close_orders
