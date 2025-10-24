import json
import logging

import pandas as pd
from constants import USD_MIN_COLLATERAL, USD_PER_TRADE, ZSCORE_THRESH
from func_bot_agent import BotAgent
from func_cointegration import calculate_zscore
from func_messaging import TelegramMessenger
from func_private import get_account, is_open_positions
from func_public import get_candles_recent, get_markets
from func_utils import format_number
from models.pair_storage import pair_storage

logger = logging.getLogger(__name__)

IGNORE_ASSETS = [
    "BTC-USD_x",
    "BTC-USD_y",
]  # Ignore these assets which are not trading on testnet


# Open positions
async def open_positions(client):
    """
    Manage finding triggers for trade entry
    Store trades for managing later on on exit function
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
        open_positions_file = open("bot_agents.json")
        open_positions_dict = json.load(open_positions_file)
        for p in open_positions_dict:
            bot_agents.append(p)
    except Exception:
        bot_agents = []
        logger.debug("No existing bot_agents.json found; starting fresh")

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
            logger.exception(
                "Failed to fetch candles for %s / %s", base_market, quote_market
            )
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
                        float(base_price) * 1.01
                        if z_score < 0
                        else float(base_price) * 0.99
                    )
                    accept_quote_price = (
                        float(quote_price) * 1.01
                        if z_score > 0
                        else float(quote_price) * 0.99
                    )
                    failsafe_base_price = (
                        float(base_price) * 0.05
                        if z_score < 0
                        else float(base_price) * 1.7
                    )
                    base_tick_size = markets["markets"][base_market]["tickSize"]
                    quote_tick_size = markets["markets"][quote_market]["tickSize"]

                    # Format prices
                    accept_base_price = format_number(accept_base_price, base_tick_size)
                    accept_quote_price = format_number(
                        accept_quote_price, quote_tick_size
                    )
                    accept_failsafe_base_price = format_number(
                        failsafe_base_price, base_tick_size
                    )

                    # Get size
                    base_quantity = 1 / base_price * USD_PER_TRADE
                    quote_quantity = 1 / quote_price * USD_PER_TRADE
                    base_step_size = markets["markets"][base_market]["stepSize"]
                    quote_step_size = markets["markets"][quote_market]["stepSize"]

                    # Format sizes
                    base_size = format_number(base_quantity, base_step_size)
                    quote_size = format_number(quote_quantity, quote_step_size)

                    # Ensure size (minimum order size greater than $1 according to V4 documentation)
                    base_min_order_size = 1 / float(
                        markets["markets"][base_market]["oraclePrice"]
                    )
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
                                "market_2_order_id": bot_open_dict.get("market_2_order_id", "")
                            }
                            messenger.send_trade_opened_message(trade_info)

                            # Append to list of bot agents
                            bot_agents.append(bot_open_dict)
                            del bot_open_dict

                            # Save trade
                            with open("bot_agents.json", "w") as f:
                                json.dump(bot_agents, f)

                            # Confirm live status in print
                            logger.info(
                                "Trade status: Live for %s / %s",
                                base_market,
                                quote_market,
                            )

    # Save agents
    logger.info("Manage open trades cycle complete")
    # if len(bot_agents) > 0:
    #   with open("bot_agents.json", "w") as f:
    #     json.dump(bot_agents, f)
