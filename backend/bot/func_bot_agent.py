import logging
import time
from datetime import datetime

from func_messaging import TelegramMessenger
from func_private import cancel_order, check_order_status, place_market_order

logger = logging.getLogger(__name__)


# Class: Agent for managing opening and checking trades
class BotAgent:
    """
    Primary function of BotAgent handles opening and checking order status
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

        # Initialze output variable
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
            "order_time_m1": "",
            "order_id_m2": "",
            "order_m2_size": quote_size,
            "order_m2_side": quote_side,
            "order_time_m2": "",
            "pair_status": "",
            "comments": "",
        }

    # Check order status by id
    async def check_order_status_by_id(self, order_id):

        # Allow time to process
        time.sleep(2)

        # Check order status
        order_status = await check_order_status(self.client, order_id)

        # Guard: If order cancelled move onto next Pair
        if order_status == "CANCELED":
            logger.warning("%s vs %s - Order cancelled", self.market_1, self.market_2)
            self.order_dict["pair_status"] = "FAILED"
            return "failed"

        # Guard: If order not filled wait until order expiration
        if order_status != "FAILED":
            time.sleep(15)
            order_status = await check_order_status(self.client, order_id)

            # Guard: If order cancelled move onto next Pair
            if order_status == "CANCELED":
                logger.warning(
                    "%s vs %s - Order cancelled", self.market_1, self.market_2
                )
                self.order_dict["pair_status"] = "FAILED"
                return "failed"

            # Guard: If not filled, cancel order
            if order_status != "FILLED":
                await cancel_order(self.client, order_id)
                self.order_dict["pair_status"] = "ERROR"
                logger.error(
                    "%s vs %s - Order error. Cancellation request sent, verify open orders",
                    self.market_1,
                    self.market_2,
                )
                return "error"

        # Return live
        return "live"

    # Open trades
    async def open_trades(self):

        # Print status
        logger.info(
            "%s: Placing first order | side=%s size=%s price=%s",
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
            self.order_dict["order_time_m1"] = datetime.now().isoformat()
            logger.info("First order for %s sent", self.market_1)
        except Exception as e:
            logger.exception("Error placing first order for %s", self.market_1)
            self.order_dict["pair_status"] = "ERROR"
            self.order_dict["comments"] = f"Market 1 {self.market_1}: , {e}"
            return self.order_dict

        # Ensure order is live before processing
        logger.info(
            "Checking first order status for %s", self.order_dict["order_id_m1"]
        )
        order_status_m1 = await self.check_order_status_by_id(
            self.order_dict["order_id_m1"]
        )
        logger.info("First order status: %s", order_status_m1)

        # Guard: Aborder if order failed
        if order_status_m1 != "live":
            self.order_dict["pair_status"] = "ERROR"
            self.order_dict["comments"] = f"{self.market_1} failed to fill"
            return self.order_dict

        # Print status - opening second order
        logger.info(
            "%s: Placing second order | side=%s size=%s price=%s",
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
            self.order_dict["order_time_m2"] = datetime.now().isoformat()
            logger.info("Second order for %s sent (id=%s)", self.market_2, order_id)
        except Exception as e:
            logger.exception("Error placing second order for %s", self.market_2)
            self.order_dict["pair_status"] = "ERROR"
            self.order_dict["comments"] = f"Market 2 {self.market_2}: , {e}"
            return self.order_dict

        # Ensure order is live before processing
        logger.info(
            "Checking second order status for %s", self.order_dict["order_id_m2"]
        )
        order_status_m2 = await self.check_order_status_by_id(
            self.order_dict["order_id_m2"]
        )

        # Guard: Aborder if order failed
        if order_status_m2 != "live":
            self.order_dict["pair_status"] = "ERROR"
            self.order_dict["comments"] = f"{self.market_1} failed to fill"

            # Close order 1:
            try:
                (close_order, order_id) = await place_market_order(
                    self.client,
                    market=self.market_1,
                    side=self.quote_side,
                    size=self.base_size,
                    price=self.accept_failsafe_base_price,
                    reduce_only=True,
                )

                # Ensure order is live before proceeding
                time.sleep(2)
                order_status_close_order = await check_order_status(
                    self.client, order_id
                )
                if order_status_close_order != "FILLED":
                    logger.critical("ABORT PROGRAM - Failed to close hedged position")
                    logger.critical(
                        "Unexpected error closing %s -> status %s",
                        self.market_1,
                        order_status_close_order,
                    )

                    # Send Message
                    self.messenger.send_error_message(
                        "CRITICAL: Position Closure Failed",
                        f"Failed to close hedged position for {self.market_1}. Status: {order_status_close_order}. Emergency intervention required!",
                        is_critical=True
                    )

                    # ABORT
                    exit(1)
            except Exception as e:
                self.order_dict["pair_status"] = "ERROR"
                self.order_dict["comments"] = f"Close Market 1 {self.market_1}: , {e}"
                status_snapshot = locals().get("order_status_close_order", "unknown")
                logger.critical(
                    "ABORT PROGRAM - Unexpected error closing %s", self.market_1
                )
                logger.critical("order_status_close_order=%s", status_snapshot)

                # Send Message
                self.messenger.send_error_message(
                    "CRITICAL: Unexpected Closure Error",
                    f"Unexpected error closing {self.market_1}. Exception: {str(e)}. Status: {status_snapshot}. Emergency intervention required!",
                    is_critical=True
                )

                # ABORT
                exit(1)

        # Return success result
        else:
            logger.info("SUCCESS: LIVE PAIR %s / %s", self.market_1, self.market_2)
            self.order_dict["pair_status"] = "LIVE"
            return self.order_dict
