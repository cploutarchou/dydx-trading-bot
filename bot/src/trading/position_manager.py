"""Position entry and exit management for pairs trading."""

import json
import logging
import time
from pathlib import Path

import pandas as pd
from src.constants import CLOSE_AT_ZSCORE_CROSS, USD_MIN_COLLATERAL, USD_PER_TRADE, ZSCORE_THRESH
from src.trading.bot_agent import BotAgent
from src.trading.analysis.cointegration import calculate_zscore
from src.shared.notifications import TelegramMessenger
from src.trading.account_manager import (
    get_account,
    get_open_positions,
    get_order,
    is_open_positions,
    place_market_order,
)
from src.trading.market_data import get_candles_recent, get_markets
from src.shared.utils import format_number
from src.infrastructure.domain.cointegration_storage import pair_storage

logger = logging.getLogger(__name__)

BOT_AGENTS_PATH = Path(__file__).resolve().parents[2] / "bot_agents.json"

IGNORE_ASSETS = [
    "BTC-USD_x",
    "BTC-USD_y",
]  # Ignore these assets which are not trading on testnet


async def open_positions(client):
    """
    Manage finding triggers for trade entry.

    Load cointegrated pairs and open positions when Z-score threshold is met.
    Store trades for managing later via exit function.
    """

    # Initialize Telegram messenger
    messenger = TelegramMessenger()

    # Load cointegrated pairs using enhanced storage
    pairs = pair_storage.load_pairs()
    logger.info("Loaded %d cointegrated pairs from enhanced storage", len(pairs))

    # Convert to DataFrame for backward compatibility with existing logic
    if pairs:
        df = pd.DataFrame([pair.to_dict() for pair in pairs])
    else:
        logger.warning("No cointegrated pairs found")
        return

    # Get markets from referencing of min order size, tick size etc
    markets = await get_markets(client)

    # Initialize container for BotAgent results
    bot_agents = []

    # Opening JSON file
    try:
        with BOT_AGENTS_PATH.open("r", encoding="utf-8") as open_positions_file:
            open_positions_dict = json.load(open_positions_file)
        for p in open_positions_dict:
            bot_agents.append(p)
    except Exception:
        bot_agents = []
        logger.debug("No existing %s found; starting fresh", BOT_AGENTS_PATH)

    # Find ZScore triggers
    for index, row in df.iterrows():

        # Extract variables
        base_market = row["base_market"]
        quote_market = row["quote_market"]
        hedge_ratio = row["hedge_ratio"]
        half_life = row["half_life"]

        # Continue if ignore asset
        if base_market in IGNORE_ASSETS or quote_market in IGNORE_ASSETS:
            continue

        # Get prices
        try:
            series_1 = await get_candles_recent(client, base_market)
            series_2 = await get_candles_recent(client, quote_market)
        except Exception:
            logger.exception("Failed to fetch candles for %s / %s", base_market, quote_market)
            continue

        # Get ZScore
        if len(series_1) > 0 and len(series_1) == len(series_2):
            spread = series_1 - (hedge_ratio * series_2)
            z_score = calculate_zscore(spread).values.tolist()[-1]

            # Establish if potential trade
            if abs(z_score) >= ZSCORE_THRESH:

                # Ensure like-for-like not already open (diversify trading)
                is_base_open = await is_open_positions(client, base_market)
                is_quote_open = await is_open_positions(client, quote_market)

                # Place trade
                if not is_base_open and not is_quote_open:

                    # Determine side
                    base_side = "BUY" if z_score < 0 else "SELL"
                    quote_side = "BUY" if z_score > 0 else "SELL"

                    # Get acceptable price in string format with correct number of decimals
                    base_price = series_1[-1]
                    quote_price = series_2[-1]
                    accept_base_price = (
                        float(base_price) * 1.01 if z_score < 0 else float(base_price) * 0.99
                    )
                    accept_quote_price = (
                        float(quote_price) * 1.01 if z_score > 0 else float(quote_price) * 0.99
                    )
                    failsafe_base_price = (
                        float(base_price) * 0.05 if z_score < 0 else float(base_price) * 1.7
                    )
                    base_tick_size = markets["markets"][base_market]["tickSize"]
                    quote_tick_size = markets["markets"][quote_market]["tickSize"]

                    # Format prices
                    accept_base_price = format_number(accept_base_price, base_tick_size)
                    accept_quote_price = format_number(accept_quote_price, quote_tick_size)
                    accept_failsafe_base_price = format_number(failsafe_base_price, base_tick_size)

                    # Get size
                    base_quantity = 1 / base_price * USD_PER_TRADE
                    quote_quantity = 1 / quote_price * USD_PER_TRADE
                    base_step_size = markets["markets"][base_market]["stepSize"]
                    quote_step_size = markets["markets"][quote_market]["stepSize"]

                    # Format sizes
                    base_size = format_number(base_quantity, base_step_size)
                    quote_size = format_number(quote_quantity, quote_step_size)

                    # Ensure size (minimum order size greater than $1 according to V4 documentation)
                    base_min_order_size = 1 / float(markets["markets"][base_market]["oraclePrice"])
                    quote_min_order_size = 1 / float(
                        markets["markets"][quote_market]["oraclePrice"]
                    )

                    # Combine checks
                    check_base = float(base_quantity) > base_min_order_size
                    check_quote = float(quote_quantity) > quote_min_order_size

                    # If checks pass, place trades
                    if check_base and check_quote:

                        # Check account balance
                        account = await get_account(client)
                        free_collateral = float(account["freeCollateral"])
                        logger.info(
                            "Free collateral %.2f (min required %.2f)",
                            free_collateral,
                            USD_MIN_COLLATERAL,
                        )

                        # Guard: Ensure collateral
                        if free_collateral < USD_MIN_COLLATERAL:
                            logger.warning(
                                "Insufficient collateral %.2f < %.2f; skipping trade",
                                free_collateral,
                                USD_MIN_COLLATERAL,
                            )
                            break

                        # Create Bot Agent
                        bot_agent = BotAgent(
                            client,
                            market_1=base_market,
                            market_2=quote_market,
                            base_side=base_side,
                            base_size=base_size,
                            base_price=accept_base_price,
                            quote_side=quote_side,
                            quote_size=quote_size,
                            quote_price=accept_quote_price,
                            accept_failsafe_base_price=accept_failsafe_base_price,
                            z_score=z_score,
                            half_life=half_life,
                            hedge_ratio=hedge_ratio,
                        )

                        # Open Trades
                        bot_open_dict = await bot_agent.open_trades()

                        # Guard: Handle failure
                        if bot_open_dict == "failed":
                            logger.warning(
                                "Bot agent failed to open trades for %s / %s",
                                base_market,
                                quote_market,
                            )
                            continue

                        # Handle success in opening trades
                        if (
                            isinstance(bot_open_dict, dict)
                            and bot_open_dict.get("pair_status") == "LIVE"
                        ):
                            # Send trade opened notification before deleting bot_open_dict
                            trade_info = {
                                "pair": f"{base_market} / {quote_market}",
                                "base_market": base_market,
                                "quote_market": quote_market,
                                "base_side": bot_open_dict.get("base_side", "Unknown"),
                                "quote_side": bot_open_dict.get("quote_side", "Unknown"),
                                "base_size": bot_open_dict.get("base_size", 0),
                                "quote_size": bot_open_dict.get("quote_size", 0),
                                "z_score": bot_open_dict.get("z_score", 0),
                                "hedge_ratio": bot_open_dict.get("hedge_ratio", 0),
                                "half_life": bot_open_dict.get("half_life", 0),
                                "market_1_order_id": bot_open_dict.get("market_1_order_id", ""),
                                "market_2_order_id": bot_open_dict.get("market_2_order_id", ""),
                            }
                            messenger.send_trade_opened_message(trade_info)

                            # Append to list of bot agents
                            bot_agents.append(bot_open_dict)
                            del bot_open_dict

                            # Save trade
                            with BOT_AGENTS_PATH.open("w", encoding="utf-8") as f:
                                json.dump(bot_agents, f)

                            # Confirm live status in print
                            logger.info(
                                "Trade status: Live for %s / %s",
                                base_market,
                                quote_market,
                            )

    # Save agents
    logger.info("Manage open trades cycle complete")


async def manage_trade_exits(client):
    """
    Manage exiting open positions based on exit criteria.

    Checks Z-score levels and closes positions when reversion occurs.
    """

    # Initialize Telegram messenger
    messenger = TelegramMessenger()

    # Initialize saving output
    save_output = []

    # Opening a JSON file
    try:
        with BOT_AGENTS_PATH.open("r", encoding="utf-8") as open_positions_file:
            open_positions_dict = json.load(open_positions_file)
        logger.debug("Loaded %d tracked positions", len(open_positions_dict))
    except Exception as e:
        logger.info("No %s found; nothing to close (%s)", BOT_AGENTS_PATH, e)
        return "complete"

    # Guard: Exit if no open positions in file
    if len(open_positions_dict) < 1:
        return "complete"

    # Get all open positions per trading platform
    exchange_pos = await get_open_positions(client)
    logger.debug("Exchange reports %d open positions", len(exchange_pos))

    # Create live position tickers list
    markets_live = list(exchange_pos.keys())

    # Protect API
    time.sleep(0.5)

    # Check all saved positions match order record
    # Exit trade according to any exit trade rules
    for position in open_positions_dict:

        # Initialize is_close trigger
        is_close = False

        # Extract position matching information from file - market 1
        position_market_m1 = position["market_1"]
        position_size_m1 = position["order_m1_size"]
        position_side_m1 = position["order_m1_side"]

        # Extract position matching information from file - market 2
        position_market_m2 = position["market_2"]
        position_size_m2 = position["order_m2_size"]
        position_side_m2 = position["order_m2_side"]

        # Protect API
        time.sleep(0.5)

        # Get order info m1 per exchange
        order_m1 = await get_order(client, position["order_id_m1"])
        order_market_m1 = order_m1["ticker"]
        order_size_m1 = order_m1["size"]
        order_side_m1 = order_m1["side"]

        # Protect API Rate limits
        time.sleep(0.5)

        # Get order info m2 per exchange
        order_m2 = await get_order(client, position["order_id_m2"])
        order_market_m2 = order_m2["ticker"]
        order_size_m2 = order_m2["size"]
        order_side_m2 = order_m2["side"]

        ## New: Ensure sizes match what was sent to the exchange
        # Override size to match what DYDX exchange has
        position_size_m1 = order_m1["size"]
        position_size_m2 = order_m2["size"]

        # Perform matching checks
        check_m1 = (
            position_market_m1 == order_market_m1
            and position_size_m1 == order_size_m1
            and position_side_m1 == order_side_m1
        )
        check_m2 = (
            position_market_m2 == order_market_m2
            and position_size_m2 == order_size_m2
            and position_side_m2 == order_side_m2
        )
        check_live = position_market_m1 in markets_live and position_market_m2 in markets_live

        # Guard: If not all match exit with error
        if not check_m1 or not check_m2 or not check_live:
            logger.error(
                "Position mismatch for %s / %s; local state diverged from exchange",
                position_market_m1,
                position_market_m2,
            )
            logger.error(
                "Program does not recognise some open positions. Manual intervention required."
            )
            logger.error("Exiting program")
            exit(1)

        # Get prices
        series_1 = await get_candles_recent(client, position_market_m1)
        time.sleep(0.2)
        series_2 = await get_candles_recent(client, position_market_m2)
        time.sleep(0.2)

        # Get markets for reference of tick size
        markets = await get_markets(client)

        # Protect API
        time.sleep(0.2)

        # Trigger close based on Z-Score
        if CLOSE_AT_ZSCORE_CROSS:

            # Initialize z_scores
            hedge_ratio = position["hedge_ratio"]
            z_score_traded = position["z_score"]
            if len(series_1) > 0 and len(series_1) == len(series_2):
                spread = series_1 - (hedge_ratio * series_2)
                z_score_current = calculate_zscore(spread).values.tolist()[-1]

            # Determine trigger
            z_score_level_check = abs(z_score_current) >= abs(z_score_traded)
            z_score_cross_check = (z_score_current < 0 < z_score_traded) or (
                z_score_current > 0 > z_score_traded
            )

            # Close trade
            if z_score_level_check and z_score_cross_check:
                # Initiate close trigger
                is_close = True

        # Close positions if triggered
        if is_close:

            # Determine side - m1
            side_m1 = "SELL"
            if position_side_m1 == "SELL":
                side_m1 = "BUY"

            # Determine side - m2
            side_m2 = "SELL"
            if position_side_m2 == "SELL":
                side_m2 = "BUY"

            # Get and format Price
            price_m1 = float(series_1[-1])
            price_m2 = float(series_2[-1])
            accept_price_m1 = price_m1 * 1.05 if side_m1 == "BUY" else price_m1 * 0.95
            accept_price_m2 = price_m2 * 1.05 if side_m2 == "BUY" else price_m2 * 0.95
            tick_size_m1 = markets["markets"][position_market_m1]["tickSize"]
            tick_size_m2 = markets["markets"][position_market_m2]["tickSize"]
            accept_price_m1 = format_number(accept_price_m1, tick_size_m1)
            accept_price_m2 = format_number(accept_price_m2, tick_size_m2)

            # Close positions
            try:

                # Close position for market 1
                logger.info(
                    "Closing position for %s (subaccount inferred)",
                    position_market_m1,
                )

                (close_order_m1, order_id) = await place_market_order(
                    client,
                    market=position_market_m1,
                    side=side_m1,
                    size=position_size_m1,
                    price=accept_price_m1,
                    reduce_only=True,
                )

                logger.debug("Close order m1 id: %s", close_order_m1.get("id"))

                # Protect API
                time.sleep(1)

                # Close position for market 2
                logger.info(
                    "Closing position for %s (subaccount inferred)",
                    position_market_m2,
                )

                (close_order_m2, order_id) = await place_market_order(
                    client,
                    market=position_market_m2,
                    side=side_m2,
                    size=position_size_m2,
                    price=accept_price_m2,
                    reduce_only=True,
                )

                logger.debug("Close order m2 id: %s", close_order_m2.get("id"))

                # Send trade closed notification
                trade_info = {
                    "pair": f"{position_market_m1} / {position_market_m2}",
                    "base_market": position_market_m1,
                    "quote_market": position_market_m2,
                    "base_side": side_m1,
                    "quote_side": side_m2,
                    "base_size": position_size_m1,
                    "quote_size": position_size_m2,
                    "z_score": z_score_current,
                    "close_order_m1_id": close_order_m1.get("id", "") if close_order_m1 else "",
                    "close_order_m2_id": close_order_m2.get("id", "") if close_order_m2 else "",
                }
                messenger.send_trade_closed_message(trade_info, "Z-score reversion")

            except Exception:
                logger.exception(
                    "Exit failed for %s with %s",
                    position_market_m1,
                    position_market_m2,
                )
                save_output.append(position)

        # Keep record if items and save
        else:
            save_output.append(position)

    # Save remaining items
    logger.info("%d items remaining; persisting bot_agents.json", len(save_output))
    with BOT_AGENTS_PATH.open("w", encoding="utf-8") as f:
        json.dump(save_output, f)
