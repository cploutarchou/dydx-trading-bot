"""
Instance-aware main.py - Modified to support API-controlled bot instances
"""

# ⚠️ CRITICAL: Load environment variables FIRST, before any other imports
from dotenv import load_dotenv

load_dotenv()

import argparse
import asyncio
import logging
import os
import signal
import sys
from typing import Optional

# Import configuration and bot functions
from config.config import config
from src.shared.logging_setup import setup_logging
from src.shared.notifications import TelegramMessenger
from src.trading.account_manager import abort_all_positions
from src.trading.analysis.cointegration import store_cointegration_results
from src.trading.dydx_client import connect_dydx
from src.trading.market_data import construct_market_prices
from src.trading.position_manager import manage_trade_exits, open_positions


class BotInstance:
    """Individual bot instance with isolated state and configuration"""

    def __init__(self, instance_id: str, config_file: Optional[str] = None):
        self.instance_id = instance_id
        self.config_file = config_file
        self.logger: Optional[logging.Logger] = None
        self.client = None
        self.messenger = None
        self.running = False
        self.config = None

        # Instance-specific file paths
        self.bot_agents_file = os.getenv("BOT_AGENTS_FILE", f"bot_agents_{instance_id}.json")
        self.pairs_file = os.getenv("BOT_PAIRS_FILE", f"cointegrated_pairs_{instance_id}.json")

        # Replace placeholders in file paths
        self.bot_agents_file = self.bot_agents_file.replace("{instance_id}", instance_id)
        self.pairs_file = self.pairs_file.replace("{instance_id}", instance_id)

    def setup_logging(self):
        """Setup instance-specific logging"""
        setup_logging()
        self.logger = logging.getLogger(f"bot.{self.instance_id}")
        self.logger.info(f"Bot instance {self.instance_id} initializing...")

    def load_config(self):
        """Load instance-specific configuration"""
        try:
            # Attempt to load instance-specific YAML config file first
            if self.config_file and os.path.exists(self.config_file):
                import yaml
                if self.logger:
                    self.logger.info(f"Loading instance config from {self.config_file}")
                with open(self.config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                    if config_data:
                        # Config loaded from file; build minimal DydxConfig from YAML
                        from config.config import DydxConfig, BotSettings, TelegramSettings, DYDXTestnetSettings, DYDXMainnetSettings, LoggingSettings, BacktestSettings, DatabaseSettings, RedisSettings, LokiSettings

                        self.config = DydxConfig(
                            is_testnet=config_data.get("is_testnet", True),
                            environment=config_data.get("environment", "development"),
                            telegram=TelegramSettings(
                                token=config_data.get("telegram", {}).get("token", ""),
                                chat_id=config_data.get("telegram", {}).get("chat_id", ""),
                            ),
                            botSettings=BotSettings(
                                is_testnet=config_data.get("is_testnet", True),
                                abortAllPositions=config_data.get("botSettings", {}).get("abortAllPositions", False),
                                findCointegratedPairs=config_data.get("botSettings", {}).get("findCointegratedPairs", False),
                                manageExits=config_data.get("botSettings", {}).get("manageExits", False),
                                placeTrades=config_data.get("botSettings", {}).get("placeTrades", False),
                                resolutionTimeframe=config_data.get("botSettings", {}).get("resolutionTimeframe", "1HOUR"),
                                strategy=config_data.get("botSettings", {}).get("strategy", "cointegration"),
                                statsWindow=int(config_data.get("botSettings", {}).get("statsWindow", 21)),
                                maxHalfLife=int(config_data.get("botSettings", {}).get("maxHalfLife", 24)),
                                ZScoreThreshold=float(config_data.get("botSettings", {}).get("ZScoreThreshold", 1.5)),
                                usdPerTrade=float(config_data.get("botSettings", {}).get("usdPerTrade", 10.0)),
                                usdMinCollateral=float(config_data.get("botSettings", {}).get("usdMinCollateral", 100.0)),
                                closeAtZscoreCross=config_data.get("botSettings", {}).get("closeAtZscoreCross", True),
                            ),
                            dydx_testnet=DYDXTestnetSettings(
                                dydx_chain_address=config_data.get("dydx_testnet", {}).get("dydx_chain_address", ""),
                                dydx_chain_secret=config_data.get("dydx_testnet", {}).get("dydx_chain_secret", ""),
                            ),
                            dydx_mainnet=DYDXMainnetSettings(
                                dydx_chain_address=config_data.get("dydx_mainnet", {}).get("dydx_chain_address", ""),
                                dydx_chain_secret=config_data.get("dydx_mainnet", {}).get("dydx_chain_secret", ""),
                            ),
                            logging=LoggingSettings(
                                level=config_data.get("logging", {}).get("level", "INFO"),
                                loki=LokiSettings(
                                    enabled=config_data.get("logging", {}).get("loki", {}).get("enabled", False),
                                    url=config_data.get("logging", {}).get("loki", {}).get("url", ""),
                                    username=config_data.get("logging", {}).get("loki", {}).get("username", ""),
                                    password=config_data.get("logging", {}).get("loki", {}).get("password", ""),
                                    labels=config_data.get("logging", {}).get("loki", {}).get("labels", {}),
                                ),
                            ),
                        )
                        if self.logger:
                            self.logger.info(f"Configuration loaded for instance {self.instance_id}")
                            self.logger.info(f"Network: {'TESTNET' if self.config.is_testnet else 'MAINNET'}")
                            self.logger.info(f"Strategy: {self.config.botSettings.strategy}")
                        return

            # Fallback to environment-based config
            self.config = config()

            if self.config is None:
                raise RuntimeError("Failed to load configuration")

            if self.logger:
                self.logger.info(f"Configuration loaded for instance {self.instance_id}")
                self.logger.info(f"Network: {'TESTNET' if self.config.is_testnet else 'MAINNET'}")
                self.logger.info(f"Strategy: {self.config.botSettings.strategy}")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to load config: {e}")
            raise

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            self.logger.info(
                f"Received signal {signum}, shutting down instance {self.instance_id}..."
            )
            self.running = False
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def initialize(self):
        """Initialize bot instance"""
        try:
            self.setup_logging()
            self.load_config()
            self.setup_signal_handlers()

            # Initialize Telegram messenger with instance info
            self.messenger = TelegramMessenger()

            # Send startup message
            config_dict = {
                "instance_id": self.instance_id,
                "environment": self.config.environment,
                "is_testnet": self.config.is_testnet,
                "strategy": self.config.botSettings.strategy,
                "usd_per_trade": self.config.botSettings.usdPerTrade,
                "zscore_threshold": self.config.botSettings.ZScoreThreshold,
            }
            self.messenger.send_startup_message(config_dict)

            # Connect to dYdX client
            self.logger.info("Connecting to dYdX client...")
            self.client = await connect_dydx()
            self.logger.info("Successfully connected to dYdX")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to initialize bot instance: {e}")
            if self.messenger:
                self.messenger.send_error_message(
                    "Initialization Failed",
                    f"Bot instance {self.instance_id} failed to initialize: {str(e)}",
                    is_critical=True,
                )
            raise

    async def run_initial_setup(self):
        """Run initial setup tasks (positions, cointegration analysis)"""
        try:
            # Get bot settings
            bot_settings = self.config.botSettings

            # Abort all open positions if requested
            if bot_settings.abortAllPositions:
                self.logger.info("Closing open positions...")
                await abort_all_positions(self.client)
                self.logger.info("All positions closed")

            # Find cointegrated pairs if requested
            if bot_settings.findCointegratedPairs:
                self.logger.info("Starting cointegration analysis...")
                df_market_prices = await construct_market_prices(self.client)

                # Store results in instance-specific file
                stores_result = store_cointegration_results(df_market_prices)
                if stores_result != "saved":
                    raise RuntimeError("Failed to save cointegration results")

                self.logger.info("Cointegration analysis completed")

        except Exception as e:
            self.logger.error(f"Error in initial setup: {e}")
            self.messenger.send_error_message(
                "Setup Failed",
                f"Bot instance {self.instance_id} setup failed: {str(e)}",
                is_critical=True,
            )
            raise

    async def trading_loop(self):
        """Main trading loop"""
        self.running = True
        self.logger.info(f"Starting trading loop for instance {self.instance_id}")

        try:
            while self.running:
                bot_settings = self.config.botSettings

                # Manage existing positions
                if bot_settings.manageExits:
                    try:
                        self.logger.debug("Managing exits...")
                        await manage_trade_exits(self.client)
                        await asyncio.sleep(1)
                    except Exception as e:
                        self.logger.error(f"Error managing exits: {e}")
                        self.messenger.send_error_message(
                            "Exit Management Error",
                            f"Instance {self.instance_id}: {str(e)}",
                            is_critical=False,
                        )

                # Place new trades
                if bot_settings.placeTrades:
                    try:
                        self.logger.debug("Finding trading opportunities...")
                        await open_positions(self.client)
                    except Exception as e:
                        self.logger.error(f"Error opening positions: {e}")
                        self.messenger.send_error_message(
                            "Trade Entry Error",
                            f"Instance {self.instance_id}: {str(e)}",
                            is_critical=False,
                        )

                # Sleep between iterations
                await asyncio.sleep(5)  # 5 second cycle

        except KeyboardInterrupt:
            self.logger.info(f"Bot instance {self.instance_id} stopped by user")
            self.messenger.send_shutdown_message(f"User interrupt (instance {self.instance_id})")
        except Exception as e:
            self.logger.error(f"Critical error in trading loop: {e}")
            self.messenger.send_error_message(
                "Trading Loop Error", f"Instance {self.instance_id}: {str(e)}", is_critical=True
            )
            raise
        finally:
            self.running = False

    async def run(self):
        """Run the complete bot instance"""
        try:
            await self.initialize()
            await self.run_initial_setup()
            await self.trading_loop()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bot instance {self.instance_id} failed: {e}")
            sys.exit(1)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="dYdX Trading Bot Instance")
    parser.add_argument("--instance-id", required=True, help="Unique instance ID for this bot")
    parser.add_argument("--config", help="Path to instance-specific config file")
    return parser.parse_args()


async def main():
    """Main entry point for bot instance"""
    try:
        args = parse_arguments()

        # Create and run bot instance
        bot = BotInstance(instance_id=args.instance_id, config_file=args.config)

        await bot.run()

    except KeyboardInterrupt:
        print("Bot instance interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"Bot instance failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
