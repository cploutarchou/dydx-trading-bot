"""Bot agent for managing trade execution and monitoring."""

import asyncio
import json
from datetime import datetime, timezone

from loguru import logger
from src.shared.notifications import TelegramMessenger
from src.trading.account_manager import (
    cancel_order,
    check_order_status,
    get_order,
    get_order_fills,
    is_open_positions,
    place_market_order,
)


class BotAgent:
    """
    Agent for managing opening and checking order status.

    Orchestrates the execution of paired trades and monitors their lifecycle.
    """

    # Initialize class
    def __init__(
            self,
            client,
            market_1,
            market_2,
            base_side,
            base_size,
            base_price,
            quote_side,
            quote_size,
            quote_price,
            accept_failsafe_base_price,
            z_score,
            half_life,
            hedge_ratio,
    ):
        """Initialize bot agent with trade parameters."""
        # Initialize class variables
        self.client = client
        self.market_1 = market_1
        self.market_2 = market_2
        self.base_side = base_side
        self.base_size = base_size
        self.base_price = base_price
        self.quote_side = quote_side
        self.quote_size = quote_size
        self.quote_price = quote_price
        self.accept_failsafe_base_price = accept_failsafe_base_price
        self.z_score = z_score
        self.half_life = half_life
        self.hedge_ratio = hedge_ratio

        # Initialize Telegram messenger
        self.messenger = TelegramMessenger()

        # Initialize output variable
        # Pair status options are FAILED, LIVE, CLOSE, ERROR
        self.order_dict = {
            "market_1": market_1,
            "market_2": market_2,
            "hedge_ratio": hedge_ratio,
            "z_score": z_score,
            "half_life": half_life,
            "order_id_m1": "",
            "order_m1_size": base_size,
            "order_m1_side": base_side,
            "order_m1_price": base_price,
            "order_m1_price_source": "accepted_price",
            "order_time_m1": "",
            "order_id_m2": "",
            "order_m2_size": quote_size,
            "order_m2_side": quote_side,
            "order_m2_price": quote_price,
            "order_m2_price_source": "accepted_price",
            "order_time_m2": "",
            "pair_status": "",
            "comments": "",
        }

    @staticmethod
    def _opposite_side(side):
        normalized = str(side).upper()
        if normalized == "BUY":
            return "SELL"
        if normalized == "SELL":
            return "BUY"
        raise ValueError(f"Unsupported order side: {side}")

    @staticmethod
    def _telemetry_fragment(**fields) -> str:
        payload = {k: v for k, v in fields.items()}
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def _normalize_order_status(status) -> str:
        normalized = str(status or "").strip().upper()
        if normalized == "CANCELED":
            return "CANCELLED"
        return normalized

    async def _emergency_close_first_leg(self):
        close_size = self.order_dict.get("order_m1_size") or self.base_size
        close_side = self._opposite_side(self.base_side)
        retries = 3
        last_status = "unknown"
        for attempt in range(1, retries + 1):
            (close_order, order_id) = await place_market_order(
                self.client,
                market=self.market_1,
                side=close_side,
                size=close_size,
                price=self.accept_failsafe_base_price,
                reduce_only=True,
            )
            _ = close_order

            await asyncio.sleep(2)
            order_status_close_order = await check_order_status(self.client, order_id)
            last_status = str(order_status_close_order)

            # Primary success state from indexer order lifecycle.
            if order_status_close_order == "FILLED":
                return order_id

            # Secondary success state: position is already closed despite non-filled status.
            try:
                still_open = await is_open_positions(self.client, self.market_1)
            except Exception as e:
                still_open = True
                logger.warning(
                    "Could not verify emergency closure position state for {}: {}",
                    self.market_1,
                    e,
                )

            if not still_open:
                logger.warning(
                    "Emergency close order for {} returned status {} but position is no longer open; treating as closed",
                    self.market_1,
                    order_status_close_order,
                )
                return order_id

            if attempt < retries:
                logger.warning(
                    "Emergency close retry {}/{} for {} after status {}",
                    attempt,
                    retries,
                    self.market_1,
                    order_status_close_order,
                )
                await asyncio.sleep(1)

        logger.critical("ABORT PROGRAM - Failed to close hedged position")
        logger.critical(
            "Unexpected error closing {} -> status {}",
            self.market_1,
            last_status,
        )

        self.messenger.send_error_message(
            "CRITICAL: Position Closure Failed",
            f"Failed to close hedged position for {self.market_1}. Status: {last_status}. Emergency intervention required!",
            is_critical=True,
            category="execution_emergency_cleanup",
        )

        raise RuntimeError(
            f"Failed emergency closure for {self.market_1}; "
            f"telemetry={self._telemetry_fragment(cleanup_status='failed', close_order_status=last_status, position_open_after_cleanup=True)}"
        )

    async def check_order_status_by_id(self, order_id):
        """Check order status by order ID with retry logic."""
        # Allow time to process
        await asyncio.sleep(2)

        # Check order status
        order_status = self._normalize_order_status(
            await check_order_status(self.client, order_id)
        )

        # Guard: If order cancelled move onto next Pair
        if order_status in {"CANCELLED", "FAILED"}:
            logger.warning("{} vs {} - Order cancelled", self.market_1, self.market_2)
            self.order_dict["pair_status"] = "FAILED"
            return "failed"

        # Guard: only FILLED can proceed as a live paired leg
        if order_status != "FILLED":
            await asyncio.sleep(15)
            order_status = self._normalize_order_status(
                await check_order_status(self.client, order_id)
            )

            # Guard: If order cancelled move onto next Pair
            if order_status in {"CANCELLED", "FAILED"}:
                logger.warning("{} vs {} - Order cancelled", self.market_1, self.market_2)
                self.order_dict["pair_status"] = "FAILED"
                return "failed"

            # Guard: If not filled, cancel order
            if order_status != "FILLED":
                await cancel_order(self.client, order_id)
                self.order_dict["pair_status"] = "ERROR"
                logger.error(
                    "{} vs {} - Order error. Cancellation request sent, verify open orders",
                    self.market_1,
                    self.market_2,
                )
                return "error"

        # Return live
        return "live"

    @staticmethod
    def _first_present(payload, keys):
        for key in keys:
            value = payload.get(key)
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _weighted_average_fill_price(fills):
        total_size = 0.0
        total_notional = 0.0
        for fill in fills:
            if not isinstance(fill, dict):
                continue
            price = BotAgent._first_present(fill, ("price", "fillPrice", "filledPrice"))
            size = BotAgent._first_present(fill, ("size", "fillSize", "filledSize"))
            if price in (None, "") or size in (None, ""):
                continue
            try:
                fill_size = abs(float(size))
                fill_price = float(price)
            except (TypeError, ValueError):
                continue
            total_size += fill_size
            total_notional += fill_price * fill_size
        if total_size <= 0:
            return None
        return str(total_notional / total_size)

    async def _reconcile_filled_order(self, leg_prefix, *, order_id, market):
        """
        Refresh order details from the indexer and prefer actual fill prices.

        The dYdX order record does not always include an average fill price, so
        fills are the primary source. The order record remains a deterministic
        fallback for side/size/market and, if needed, price.
        """
        try:
            order = await get_order(self.client, order_id)
        except Exception as exc:
            logger.warning("Could not reconcile filled order {}: {}", order_id, exc)
            return

        if isinstance(order, dict) and isinstance(order.get("order"), dict):
            order = order["order"]
        if not isinstance(order, dict):
            return

        ticker = self._first_present(order, ("ticker", "market", "symbol"))
        side = self._first_present(order, ("side",))
        size = self._first_present(order, ("size", "totalFilled", "filledSize"))
        order_price = self._first_present(
            order,
            (
                "averageFilledPrice",
                "avgFilledPrice",
                "filledPrice",
                "fillPrice",
                "price",
            ),
        )

        if ticker:
            self.order_dict[f"{leg_prefix}_market"] = ticker
        if side:
            self.order_dict[f"{leg_prefix}_side"] = side
        if size:
            self.order_dict[f"{leg_prefix}_size"] = size
        if order_price:
            self.order_dict[f"{leg_prefix}_price"] = order_price
            self.order_dict[f"{leg_prefix}_price_source"] = "order_record"

        try:
            fills = await get_order_fills(self.client, order_id, market=market)
        except Exception as exc:
            logger.warning("Could not fetch fills for order {}: {}", order_id, exc)
            return

        fill_price = self._weighted_average_fill_price(fills)
        if fill_price is not None:
            self.order_dict[f"{leg_prefix}_price"] = fill_price
            self.order_dict[f"{leg_prefix}_price_source"] = "fills"
            self.order_dict[f"{leg_prefix}_fill_count"] = len(fills)

    async def open_trades(self):
        """
        Open both sides of the paired trade.

        Returns:
            order_dict with trade status and details
        """
        # Print status
        logger.info(
            "{}: Placing first order | side={} size={} price={}",
            self.market_1,
            self.base_side,
            self.base_size,
            self.base_price,
        )

        # Place Base Order
        try:
            (base_order, order_id) = await place_market_order(
                self.client,
                market=self.market_1,
                side=self.base_side,
                size=self.base_size,
                price=self.base_price,
                reduce_only=False,
            )

            # Store the order id
            self.order_dict["order_id_m1"] = order_id
            self.order_dict["order_time_m1"] = datetime.now(timezone.utc).isoformat()
            logger.info("First order for {} sent", self.market_1)
        except Exception as e:
            logger.exception("Error placing first order for {}", self.market_1)
            self.order_dict["pair_status"] = "ERROR"
            self.order_dict["comments"] = f"Market 1 {self.market_1}: , {e}"
            return self.order_dict

        # Ensure order is live before processing
        logger.info("Checking first order status for {}", self.order_dict["order_id_m1"])
        order_status_m1 = await self.check_order_status_by_id(self.order_dict["order_id_m1"])
        logger.info("First order status: {}", order_status_m1)

        # Guard: Abort if order failed
        if order_status_m1 != "live":
            self.order_dict["pair_status"] = "ERROR"
            self.order_dict["comments"] = f"{self.market_1} failed to fill"
            return self.order_dict
        await self._reconcile_filled_order(
            "order_m1",
            order_id=self.order_dict["order_id_m1"],
            market=self.market_1,
        )

        # Print status - opening second order
        logger.info(
            "{}: Placing second order | side={} size={} price={}",
            self.market_2,
            self.quote_side,
            self.quote_size,
            self.quote_price,
        )

        # Place Quote Order
        try:
            (quote_order, order_id) = await place_market_order(
                self.client,
                market=self.market_2,
                side=self.quote_side,
                size=self.quote_size,
                price=self.quote_price,
                reduce_only=False,
            )

            # Store the order id
            self.order_dict["order_id_m2"] = order_id
            self.order_dict["order_time_m2"] = datetime.now(timezone.utc).isoformat()
            logger.info("Second order for {} sent (id={})", self.market_2, order_id)
        except Exception as e:
            logger.exception("Error placing second order for {}", self.market_2)
            self.order_dict["pair_status"] = "ERROR"
            self.order_dict["comments"] = f"Market 2 {self.market_2}: , {e}"
            try:
                await self._emergency_close_first_leg()
            except Exception as close_error:
                self.order_dict["comments"] = (
                    f"Market 2 {self.market_2}: {e}; "
                    f"Close Market 1 {self.market_1}: {close_error}"
                )
                raise RuntimeError(
                    f"Unexpected emergency closure error for {self.market_1}; "
                    f"telemetry={self._telemetry_fragment(cleanup_status='failed', cleanup_error=str(close_error), position_open_after_cleanup='unknown')}"
                ) from close_error
            return self.order_dict

        # Ensure order is live before processing
        logger.info("Checking second order status for {}", self.order_dict["order_id_m2"])
        order_status_m2 = await self.check_order_status_by_id(self.order_dict["order_id_m2"])

        # Guard: Abort if order failed
        if order_status_m2 != "live":
            self.order_dict["pair_status"] = "ERROR"
            self.order_dict["comments"] = f"{self.market_1} failed to fill"

            # Close order 1:
            try:
                await self._emergency_close_first_leg()
            except Exception as e:
                self.order_dict["pair_status"] = "ERROR"
                self.order_dict["comments"] = f"Close Market 1 {self.market_1}: , {e}"
                status_snapshot = locals().get("order_status_close_order", "unknown")
                logger.critical("ABORT PROGRAM - Unexpected error closing {}", self.market_1)
                logger.critical("order_status_close_order={}", status_snapshot)

                # Send Message
                self.messenger.send_error_message(
                    "CRITICAL: Unexpected Closure Error",
                    f"Unexpected error closing {self.market_1}. Exception: {str(e)}. Status: {status_snapshot}. Emergency intervention required!",
                    is_critical=True,
                    category="execution_emergency_cleanup",
                )

                raise RuntimeError(
                    f"Unexpected emergency closure error for {self.market_1}; "
                    f"telemetry={self._telemetry_fragment(cleanup_status='failed', close_order_status=status_snapshot, position_open_after_cleanup=True)}"
                ) from e

            # Return failure state after emergency cleanup
            return self.order_dict
        await self._reconcile_filled_order(
            "order_m2",
            order_id=self.order_dict["order_id_m2"],
            market=self.market_2,
        )

        # Return success result
        logger.info("SUCCESS: LIVE PAIR {} / {}", self.market_1, self.market_2)
        self.order_dict["pair_status"] = "LIVE"
        return self.order_dict
