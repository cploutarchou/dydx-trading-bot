import asyncio
import logging
import signal
import sys
import time

from config import config
from constants import ABORT_ALL_POSITIONS, FIND_COINTEGRATED, MANAGE_EXITS, PLACE_TRADES
from func_cointegration import store_cointegration_results
from func_connections import connect_dydx
from func_entry_pairs import open_positions
from func_exit_pairs import manage_trade_exits
from func_messaging import send_message
from func_private import abort_all_positions
from func_public import construct_market_prices
from logging_setup import setup_logging


# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    logging.info("Received signal %d, shutting down gracefully...", signum)
    sys.exit(0)


# MAIN FUNCTION
async def main():
    # Initialize logging first
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Load and print the configuration
    try:
        current_config = config()
        logger.info("Configuration loaded successfully")
        logger.info("Is Testnet: %s", current_config.is_testnet if current_config else "Unknown")
        logger.info("Bot Strategy: %s", current_config.botSettings.strategy if current_config and current_config.botSettings else "Unknown")
        logger.info("Telegram Chat ID: %s", current_config.telegram.chat_id if current_config and current_config.telegram else "Unknown")
    except Exception as e:
        logger.error("Error loading configuration: %s", e)
        sys.exit(1)
    # Message on start
    send_message("Bot launch successful")

    # Connect to client
    try:
        print("")
        print("Program started...")
        print("Connecting to Client...")
        client = await connect_dydx()
    except Exception as e:
        print("Error connecting to client: ", e)
        send_message(f"Failed to connect to client {e}")
        exit(1)

    # Abort all open positions
    if ABORT_ALL_POSITIONS:
        try:
            print("")
            print("Closing open positions...")
            await abort_all_positions(client)
        except Exception as e:
            print("Error closing all positions: ", e)
            send_message(f"Error closing all positions {e}")
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
            send_message(f"Error constructing market prices {e}")
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
            send_message(f"Error saving cointegrated pairs {e}")
            exit(1)

    # Run as always on
    try:
        while True:
            # Manage existing positions
            if MANAGE_EXITS:
                try:
                    print("")
                    print("Managing exits...")
                    await manage_trade_exits(client)
                    time.sleep(1)
                except Exception as e:
                    print("Error managing exiting positions: ", e)
                    send_message(f"Error managing exiting positions {e}")
                    exit(1)

            # Place trades for opening positions
            if PLACE_TRADES:
                try:
                    print("")
                    print("Finding trading opportunities...")
                    await open_positions(client)
                except Exception as e:
                    print("Error trading pairs: ", e)
                    send_message(f"Error opening trades {e}")
                    exit(1)
    
    except KeyboardInterrupt:
        logger = logging.getLogger(__name__)
        logger.info("Bot stopped by user (Ctrl+C)")
        send_message("Bot stopped by user interrupt")
        sys.exit(0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot interrupted during startup")
        sys.exit(0)
