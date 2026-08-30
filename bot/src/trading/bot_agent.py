"""Bot agent for managing trade execution and monitoring."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from loguru import logger

from src.shared.notifications import TelegramMessenger
from src.trading.account_manager import (
    cancel_order,
    cancel_order_verified,
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
        client: Any,
        market_1: str,
        market_2: str,
        base_side: str,
        base_size: str,
        base_price: str,
        quote_side: str,
        quote_size: str,
        quote_price: str,
        accept_failsafe_base_price: str,
        z_score: float,
        half_life: float,
        hedge_ratio: float,
        intercept: float = 0.0,
    ) -> None:
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
        self.intercept = intercept

        # Initialize Telegram messenger
        self.messenger = TelegramMessenger()

        # Initialize output variable
        # Pair status options are FAILED, LIVE, CLOSE, ERROR
        self.order_dict: Dict[str, Any] = {
            "market_1": market_1,
            "market_2": market_2,
            "hedge_ratio": hedge_ratio,
            "intercept": intercept,
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
    def _opposite_side(side: str) -> str:
        normalized = str(side).upper()
        if normalized == "BUY":
            return "SELL"
        if normalized == "SELL":
            return "BUY"
        raise ValueError(f"Unsupported order side: {side}")

    @staticmethod
    def _telemetry_fragment(**fields: Any) -> str:
        payload = {k: v for k, v in fields.items()}
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def _normalize_order_status(status: Any) -> str:
        normalized = str(status or "").strip().upper()
        if normalized in {"CANCELED", "BEST_EFFORT_CANCELED", "IB_CANCELED"}:
            # BEST_EFFORT_CANCELED is how dYdX short-term market orders end
            # after their good-til-block expiry — including after PARTIAL
            # fills, so callers must verify fills on this state.
            return "CANCELLED"
        return normalized

    async def _emergency_close_leg(
        self,
        *,
        market: str,
        side: str,
        size: str,
        price: str,
    ) -> str:
        """Reduce-only close one leg, retrying until filled or verified flat.

        Reduce-only orders cannot increase exposure: if the leg never filled
        the close is rejected (or no-ops) and the position check ends the
        retry loop, so this is safe to call on unknown-outcome orders.
        """
        close_side = self._opposite_side(side)
        retries = 3
        last_status = "unknown"
        order_id: str = ""
        for attempt in range(1, retries + 1):
            close_order, order_id = await place_market_order(
                self.client,
                market=market,
                side=close_side,
                size=size,
                price=price,
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
                still_open = await is_open_positions(self.client, market)
            except Exception as e:
                still_open = True
                logger.warning(
                    "Could not verify emergency closure position state for {}: {}",
                    market,
                    e,
                )

            if not still_open:
                logger.warning(
                    "Emergency close order for {} returned status {} but position is no longer open; treating as closed",
                    market,
                    order_status_close_order,
                )
                return order_id

            if attempt < retries:
                logger.warning(
                    "Emergency close retry {}/{} for {} after status {}",
                    attempt,
                    retries,
                    market,
                    order_status_close_order,
                )
                await asyncio.sleep(1)

        logger.critical("ABORT PROGRAM - Failed to close hedged position")
        logger.critical(
            "Unexpected error closing {} -> status {}",
            market,
            last_status,
        )

        self.messenger.send_error_message(
            "CRITICAL: Position Closure Failed",
            f"Failed to close hedged position for {market}. Status: {last_status}. Emergency intervention required!",
            is_critical=True,
            category="execution_emergency_cleanup",
        )

        raise RuntimeError(
            f"Failed emergency closure for {market}; "
            f"telemetry={self._telemetry_fragment(cleanup_status='failed', close_order_status=last_status, position_open_after_cleanup=True)}"
        )

    async def _emergency_close_first_leg(self) -> str:
        return await self._emergency_close_leg(
            market=self.market_1,
            side=self.base_side,
            size=self.order_dict.get("order_m1_size") or self.base_size,
            price=self.accept_failsafe_base_price,
        )

    async def _filled_size(self, order_id: str, market: str) -> Optional[float]:
        """Sum filled size for an order from indexer fills.

        Returns None when the fills query itself fails (unknown), which
        callers must treat conservatively as "possibly filled".
        """
        try:
            fills = await get_order_fills(self.client, order_id, market=market)
        except Exception as exc:
            logger.warning(
                "Could not fetch fills for order {} on {}: {}",
                order_id,
                market,
                exc,
            )
            return None
        total = 0.0
        for fill in fills:
            if not isinstance(fill, dict):
                continue
            size = self._first_present(fill, ("size", "fillSize", "filledSize"))
            if size in (None, ""):
                continue
            try:
                total += abs(float(size))
            except (TypeError, ValueError):
                continue
        return total

    async def _verify_no_partial_fill(self, order_id: str, market: str) -> bool:
        """False when the order has (or may have) a live partial-fill residual."""
        filled = await self._filled_size(order_id, market)
        if filled is None:
            return False
        return filled <= 0

    async def check_order_status_by_id(
        self, order_id: str, market: Optional[str] = None
    ) -> str:
        """Check order status by order ID with retry logic.

        ``market`` identifies the leg the order belongs to (used for
        partial-fill verification); it defaults to the first leg for
        backward compatibility with existing callers.
        """
        leg_market = market or self.market_1

        # Allow time to process
        await asyncio.sleep(2)

        # Check order status
        order_status = self._normalize_order_status(
            await check_order_status(self.client, order_id)
        )

        # Guard: If order cancelled move onto next Pair
        if order_status in {"CANCELLED", "FAILED"}:
            logger.warning("{} vs {} - Order cancelled", self.market_1, self.market_2)
            if not await self._verify_no_partial_fill(order_id, leg_market):
                self.order_dict["pair_status"] = "PARTIAL"
                return "partial"
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
                logger.warning(
                    "{} vs {} - Order cancelled", self.market_1, self.market_2
                )
                if not await self._verify_no_partial_fill(order_id, leg_market):
                    self.order_dict["pair_status"] = "PARTIAL"
                    return "partial"
                self.order_dict["pair_status"] = "FAILED"
                return "failed"

            # Guard: If not filled, cancel order and verify it cannot fill
            if order_status != "FILLED":
                final_cancel_status = await cancel_order_verified(self.client, order_id)
                if final_cancel_status not in {
                    "FILLED",
                    "CANCELED",
                    "CANCELLED",
                    "BEST_EFFORT_CANCELED",
                    "IB_CANCELED",
                    "REJECTED",
                    "EXPIRED",
                }:
                    logger.critical(
                        "Order {} may still be live after cancel (status={})",
                        order_id,
                        final_cancel_status or "unknown",
                    )
                self.order_dict["pair_status"] = "ERROR"
                logger.error(
                    "{} vs {} - Order error. Cancellation request sent, verify open orders",
                    self.market_1,
                    self.market_2,
                )
                if not await self._verify_no_partial_fill(order_id, leg_market):
                    self.order_dict["pair_status"] = "PARTIAL"
                    return "partial"
                return "error"

        # Return live
        return "live"

    @staticmethod
    def _first_present(payload: Dict[str, Any], keys: Sequence[str]) -> Any:
        for key in keys:
            value = payload.get(key)
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _weighted_average_fill_price(fills: List[Any]) -> Optional[str]:
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

    async def _reconcile_filled_order(
        self, leg_prefix: str, *, order_id: str, market: str
    ) -> None:
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

    async def _cleanup_after_unfilled_or_unknown_leg1(self, reason: str) -> None:
        """Fail-closed cleanup when leg 1's outcome is not a clean full fill.

        Covers: partial fills (BEST_EFFORT_CANCELED etc.), unknown outcomes
        (status-check exceptions, abandoned placements). The reduce-only
        close is harmless when nothing filled and flattens whatever did.
        """
        self.order_dict["pair_status"] = "ERROR"
        self.order_dict["comments"] = f"{self.market_1}: {reason}"
        try:
            await self._emergency_close_first_leg()
        except Exception as close_error:
            self.order_dict["comments"] = (
                f"{self.market_1}: {reason}; close failed: {close_error}"
            )
            raise RuntimeError(
                f"Unexpected emergency closure error for {self.market_1}; "
                f"telemetry={self._telemetry_fragment(cleanup_status='failed', cleanup_error=str(close_error), position_open_after_cleanup='unknown')}"
            ) from close_error

    async def open_trades(self) -> Dict[str, Any]:
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
            base_order, order_id = await place_market_order(
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
            # The placement outcome is UNKNOWN — the tx may have landed. A
            # reduce-only close flattens it if it did and no-ops if it did
            # not, so clean up rather than assuming nothing filled.
            logger.exception("Error placing first order for {}", self.market_1)
            await self._cleanup_after_unfilled_or_unknown_leg1(f"placement error: {e}")
            return self.order_dict

        # Ensure order is live before processing
        logger.info(
            "Checking first order status for {}", self.order_dict["order_id_m1"]
        )
        try:
            order_status_m1 = await self.check_order_status_by_id(
                self.order_dict["order_id_m1"], market=self.market_1
            )
        except Exception as e:
            # Leg 1 may already be FILLED — an exception here must never
            # bypass cleanup (that would leave an untracked naked position).
            logger.exception(
                "Status check failed for first order {} on {}",
                self.order_dict["order_id_m1"],
                self.market_1,
            )
            await self._cleanup_after_unfilled_or_unknown_leg1(
                f"status check error: {e}"
            )
            return self.order_dict
        logger.info("First order status: {}", order_status_m1)

        # Guard: Abort if order failed; a partial fill must be closed out.
        if order_status_m1 == "partial":
            await self._cleanup_after_unfilled_or_unknown_leg1("partial fill")
            return self.order_dict
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
            quote_order, order_id = await place_market_order(
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
        logger.info(
            "Checking second order status for {}", self.order_dict["order_id_m2"]
        )
        try:
            order_status_m2 = await self.check_order_status_by_id(
                self.order_dict["order_id_m2"], market=self.market_2
            )
        except Exception as e:
            # Leg 1 is FILLED and leg 2's state is unknown: close both legs
            # reduce-only so no residual exposure survives either outcome.
            logger.exception(
                "Status check failed for second order {} on {}",
                self.order_dict["order_id_m2"],
                self.market_2,
            )
            errors: list[str] = []
            try:
                await self._emergency_close_leg(
                    market=self.market_2,
                    side=self.quote_side,
                    size=self.quote_size,
                    price=self.accept_failsafe_base_price,
                )
            except Exception as leg2_error:
                errors.append(f"leg2 {self.market_2}: {leg2_error}")
            try:
                await self._emergency_close_first_leg()
            except Exception as leg1_error:
                errors.append(f"leg1 {self.market_1}: {leg1_error}")
            if errors:
                self.order_dict["pair_status"] = "ERROR"
                self.order_dict["comments"] = (
                    f"status check error: {e}; close failures: {'; '.join(errors)}"
                )
                raise RuntimeError(
                    f"Emergency closure errors after second-order status failure; "
                    f"telemetry={self._telemetry_fragment(cleanup_status='failed', cleanup_errors=errors, position_open_after_cleanup='unknown')}"
                ) from e
            self.order_dict["pair_status"] = "ERROR"
            self.order_dict["comments"] = (
                f"Market 2 {self.market_2}: status check error: {e}"
            )
            return self.order_dict

        # Guard: Abort if order failed; close any partial residual plus leg 1.
        if order_status_m2 == "partial":
            self.order_dict["pair_status"] = "ERROR"
            self.order_dict["comments"] = f"{self.market_2} partially filled"
            errors = []
            try:
                await self._emergency_close_leg(
                    market=self.market_2,
                    side=self.quote_side,
                    size=self.quote_size,
                    price=self.accept_failsafe_base_price,
                )
            except Exception as leg2_error:
                errors.append(f"leg2 {self.market_2}: {leg2_error}")
            try:
                await self._emergency_close_first_leg()
            except Exception as leg1_error:
                errors.append(f"leg1 {self.market_1}: {leg1_error}")
            if errors:
                self.order_dict["comments"] += f"; close failures: {'; '.join(errors)}"
                raise RuntimeError(
                    f"Emergency closure errors after partial second-leg fill; "
                    f"telemetry={self._telemetry_fragment(cleanup_status='failed', cleanup_errors=errors, position_open_after_cleanup='unknown')}"
                )
            return self.order_dict

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
                logger.critical(
                    "ABORT PROGRAM - Unexpected error closing {}", self.market_1
                )
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
