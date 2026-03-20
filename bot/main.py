# ⚠️ CRITICAL: Load environment variables FIRST, before any other imports
# This ensures DB_* and REDIS_* environment variables are available to config loader
from dotenv import load_dotenv

load_dotenv()

import asyncio
import logging
import signal
import sys
import time

# Suppress dYdX client's Node URL warning that gets printed to stderr during initialization
# This warning is harmless - the library automatically handles URL stripping
_original_stderr = sys.stderr


class _FilteredStderr:
    """Filter out specific warnings from dYdX client"""

    def __init__(self, stderr):
        self.stderr = stderr

    def write(self, message):
        if "Node URL should not contain http(s)://" not in message:
            self.stderr.write(message)
            self.stderr.flush()

    def flush(self):
        self.stderr.flush()

    def __getattr__(self, name):
        return getattr(self.stderr, name)


sys.stderr = _FilteredStderr(_original_stderr)

from config.config import config as load_config
from src.constants import ABORT_ALL_POSITIONS, FIND_COINTEGRATED, MANAGE_EXITS, PLACE_TRADES
from src.trading.analysis.cointegration import store_cointegration_results
from src.trading.dydx_client import connect_dydx
from src.trading.position_manager import open_positions, manage_trade_exits
from src.shared.notifications import TelegramMessenger
from src.trading.account_manager import abort_all_positions
from src.trading.market_data import construct_market_prices
from src.shared.logging_setup import setup_logging


# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    # Use print instead of logging to avoid Loki connection issues during shutdown
    print(f"Received signal {signum}, shutting down gracefully...")
    sys.exit(0)


# MAIN FUNCTION
async def main():
    global _original_stderr
    # Restore stderr now that logging is ready (dYdX imports are done)
    sys.stderr = _original_stderr

    # Initialize logging first
    setup_logging()
    logger = logging.getLogger(__name__)

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Load and print the configuration
    try:
        current_config = load_config()
        logger.info("Configuration loaded successfully")
        logger.info("Is Testnet: %s", current_config.is_testnet if current_config else "Unknown")
        logger.info(
            "Bot Strategy: %s",
            (
                current_config.botSettings.strategy
                if current_config and current_config.botSettings
                else "Unknown"
            ),
        )
        logger.info(
            "Telegram Chat ID: %s",
            (
                current_config.telegram.chat_id
                if current_config and current_config.telegram
                else "Unknown"
            ),
        )
    except Exception as e:
        logger.error("Error loading configuration: %s", e)
        sys.exit(1)
    # Initialize Telegram messenger
    telegram_messenger = TelegramMessenger()

    # Send a startup message with configuration details
    config_dict = {
        "environment": current_config.environment if current_config else "development",
        "is_testnet": current_config.is_testnet if current_config else False,
        "strategy": (
            current_config.botSettings.strategy
            if current_config and current_config.botSettings
            else "Unknown"
        ),
        "usd_per_trade": (
            current_config.botSettings.usdPerTrade
            if current_config and current_config.botSettings
            else 0
        ),
        "abort_all_positions": ABORT_ALL_POSITIONS,
        "find_cointegrated": FIND_COINTEGRATED,
        "manage_exits": MANAGE_EXITS,
        "place_trades": PLACE_TRADES,
    }
    telegram_messenger.send_startup_message(config_dict)

    # Connect to a client
    try:
        print("")
        print("Program started...")
        print("Connecting to Client...")
        client = await connect_dydx()
    except Exception as e:
        print("Error connecting to client: ", e)
        telegram_messenger.send_error_message(
            "Connection Failed",
            f"Failed to connect to dYdX client: {str(e)}",
            is_critical=True,
        )
        exit(1)

    # Abort all open positions
    if ABORT_ALL_POSITIONS:
        try:
            print("")
            print("Closing open positions...")
            await abort_all_positions(client)
        except Exception as e:
            print("Error closing all positions: ", e)
            telegram_messenger.send_error_message(
                "Position Closure Failed",
                f"Error closing all positions: {str(e)}",
                is_critical=True,
            )
            exit(1)

    # Find Cointegrated Pairs
    if FIND_COINTEGRATED:
        # Construct Market Prices
        try:
            print("")
            print("Fetching token market prices, please allow around 5 minutes...")
            df_market_prices = await construct_market_prices(client)
            print(df_market_prices)
        except Exception as e:
            print("Error constructing market prices: ", e)
            telegram_messenger.send_error_message(
                "Market Data Error",
                f"Error constructing market prices: {str(e)}",
                is_critical=True,
            )
            exit(1)

        # Store Cointegrated Pairs
        try:
            print("")
            print("Storing cointegrated pairs...")
            stores_result = store_cointegration_results(df_market_prices)
            if stores_result != "saved":
                print("Error saving cointegrated pairs")
                exit(1)
        except Exception as e:
            print("Error saving cointegrated pairs: ", e)
            telegram_messenger.send_error_message(
                "Cointegration Analysis Failed",
                f"Error saving cointegrated pairs: {str(e)}",
                is_critical=True,
            )
            exit(1)

    # Run as always on
    try:
        while True:
            # Manage existing positions
            if MANAGE_EXITS:
                try:
                    # print("")
                    # print("Managing exits...")
                    await manage_trade_exits(client)
                    time.sleep(1)
                except Exception as e:
                    print("Error managing exiting positions: ", e)
                    telegram_messenger.send_error_message(
                        "Exit Management Error",
                        f"Error managing exiting positions: {str(e)}",
                        is_critical=False,
                    )
                    exit(1)

            # Place trades for opening positions
            if PLACE_TRADES:
                try:
                    print("")
                    print("Finding trading opportunities...")
                    await open_positions(client)
                except Exception as e:
                    print("Error trading pairs: ", e)
                    telegram_messenger.send_error_message(
                        "Trade Entry Error",
                        f"Error opening trades: {str(e)}",
                        is_critical=False,
                    )
                    exit(1)

    except KeyboardInterrupt:
        logger = logging.getLogger(__name__)
        logger.info("Bot stopped by user (Ctrl+C)")
        telegram_messenger.send_shutdown_message("User interrupt (Ctrl+C)")
        sys.exit(0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot interrupted during startup")
        sys.exit(0)
