"""
Instance-aware main.py - Modified to support API-controlled bot instances
"""

# ⚠️ CRITICAL: Load environment variables FIRST, before any other imports
from src.shared.env_loader import load_repo_env

load_repo_env(__file__)

import argparse
import asyncio
import inspect
import os
import signal
import sys
from typing import Any, Optional

# Import configuration and bot functions
from config.config import config
from loguru import logger
from src.shared.logging_setup import setup_logging
from src.shared.notifications import TelegramMessenger
from src.trading.account_manager import abort_all_positions
from src.trading.analysis.cointegration import store_cointegration_results
from src.trading.dydx_client import connect_dydx_runtime
from src.trading.market_data import construct_market_prices
from src.trading.position_manager import manage_trade_exits, open_positions


class BotInstance:
    """Individual bot instance with isolated state and configuration"""

    def __init__(self, instance_id: str, config_file: Optional[str] = None):
        self.instance_id = instance_id
        self.config_file = config_file
        self.logger: Optional[Any] = None
        self.client = None
        self.messenger = None
        self.running = False
        self.config = None

        # Instance-specific file paths
        self.bot_agents_file = os.getenv(
            "BOT_AGENTS_FILE",
            f"bot_states/bot_agents_{instance_id}.json",
        )
        self.pairs_file = os.getenv(
            "BOT_PAIRS_FILE",
            f"bot_states/cointegrated_pairs_{instance_id}.json",
        )

        # Replace placeholders in file paths
        self.bot_agents_file = self.bot_agents_file.replace(
            "{instance_id}", instance_id
        )
        self.pairs_file = self.pairs_file.replace("{instance_id}", instance_id)

    @staticmethod
    def _describe_exception(exc: BaseException) -> str:
        """Render stable operator-facing exception details."""
        message = str(exc).strip()
        if message:
            return message
        return f"{type(exc).__name__} (no detail provided)"

    def _log_exception(self, message: str, exc: BaseException):
        """Log traceback when supported while remaining friendly to lightweight test doubles."""
        error_detail = self._describe_exception(exc)
        if self.logger is None:
            return
        normalized_message = message.replace("%s", "{}")
        if hasattr(self.logger, "exception"):
            self.logger.exception(normalized_message, error_detail)
        else:
            self.logger.error(normalized_message.format(error_detail))

    def setup_logging(self):
        """Setup instance-specific logging"""
        setup_logging()
        self.logger = logger.bind(
            instance_id=self.instance_id, component="bot_instance"
        )
        self.logger.info(f"Bot instance {self.instance_id} initializing...")

    def load_config(self):
        """Load instance-specific configuration"""
        try:
            # Attempt to load instance-specific YAML config file first
            if self.config_file and os.path.exists(self.config_file):
                import yaml

                if self.logger:
                    self.logger.info(f"Loading instance config from {self.config_file}")
                with open(self.config_file, "r") as f:
                    config_data = yaml.safe_load(f)
                    if config_data:
                        # Config loaded from file; build minimal DydxConfig from YAML
                        from config.config import (
                            BacktestSettings,
                            BotSettings,
                            DydxConfig,
                            DYDXMainnetSettings,
                            DYDXTestnetSettings,
                            LoggingSettings,
                            LokiSettings,
                            TelegramSettings,
                        )

                        self.config = DydxConfig(
                            is_testnet=config_data.get("is_testnet", True),
                            environment=config_data.get("environment", "development"),
                            telegram=TelegramSettings(
                                token=config_data.get("telegram", {}).get("token", ""),
                                chat_id=config_data.get("telegram", {}).get(
                                    "chat_id", ""
                                ),
                            ),
                            botSettings=BotSettings(
                                is_testnet=config_data.get("is_testnet", True),
                                subaccountNumber=int(
                                    config_data.get("botSettings", {}).get(
                                        "subaccountNumber", 0
                                    )
                                ),
                                capitalAllocationUsd=float(
                                    config_data.get("botSettings", {}).get(
                                        "capitalAllocationUsd", 0.0
                                    )
                                ),
                                abortAllPositions=config_data.get(
                                    "botSettings", {}
                                ).get("abortAllPositions", False),
                                findCointegratedPairs=config_data.get(
                                    "botSettings", {}
                                ).get("findCointegratedPairs", False),
                                manageExits=config_data.get("botSettings", {}).get(
                                    "manageExits", False
                                ),
                                placeTrades=config_data.get("botSettings", {}).get(
                                    "placeTrades", False
                                ),
                                resolutionTimeframe=config_data.get(
                                    "botSettings", {}
                                ).get("resolutionTimeframe", "1HOUR"),
                                strategy=config_data.get("botSettings", {}).get(
                                    "strategy", "cointegration"
                                ),
                                statsWindow=int(
                                    config_data.get("botSettings", {}).get(
                                        "statsWindow", 21
                                    )
                                ),
                                maxHalfLife=int(
                                    config_data.get("botSettings", {}).get(
                                        "maxHalfLife", 24
                                    )
                                ),
                                ZScoreThreshold=float(
                                    config_data.get("botSettings", {}).get(
                                        "ZScoreThreshold", 1.5
                                    )
                                ),
                                usdPerTrade=float(
                                    config_data.get("botSettings", {}).get(
                                        "usdPerTrade", 10.0
                                    )
                                ),
                                usdMinCollateral=float(
                                    config_data.get("botSettings", {}).get(
                                        "usdMinCollateral", 100.0
                                    )
                                ),
                                closeAtZscoreCross=config_data.get(
                                    "botSettings", {}
                                ).get("closeAtZscoreCross", True),
                                maxPositions=int(
                                    config_data.get("botSettings", {}).get(
                                        "maxPositions", 5
                                    )
                                ),
                                maxDrawdownPct=float(
                                    config_data.get("botSettings", {}).get(
                                        "maxDrawdownPct", 15.0
                                    )
                                ),
                                stopLossPct=float(
                                    config_data.get("botSettings", {}).get(
                                        "stopLossPct", 2.0
                                    )
                                ),
                                takeProfitPct=float(
                                    config_data.get("botSettings", {}).get(
                                        "takeProfitPct", 5.0
                                    )
                                ),
                                trailingStopPct=float(
                                    config_data.get("botSettings", {}).get(
                                        "trailingStopPct", 1.0
                                    )
                                ),
                                rebalanceIntervalHours=int(
                                    config_data.get("botSettings", {}).get(
                                        "rebalanceIntervalHours", 24
                                    )
                                ),
                                positionTimeoutHours=int(
                                    config_data.get("botSettings", {}).get(
                                        "positionTimeoutHours", 72
                                    )
                                ),
                                selectedMarkets=[
                                    str(market).strip()
                                    for market in config_data.get(
                                        "botSettings", {}
                                    ).get("selectedMarkets", [])
                                    if str(market).strip()
                                ],
                            ),
                            dydx_testnet=DYDXTestnetSettings(
                                dydx_chain_address=config_data.get(
                                    "dydx_testnet", {}
                                ).get("dydx_chain_address", ""),
                                dydx_chain_secret=config_data.get(
                                    "dydx_testnet", {}
                                ).get("dydx_chain_secret", ""),
                            ),
                            dydx_mainnet=DYDXMainnetSettings(
                                dydx_chain_address=config_data.get(
                                    "dydx_mainnet", {}
                                ).get("dydx_chain_address", ""),
                                dydx_chain_secret=config_data.get(
                                    "dydx_mainnet", {}
                                ).get("dydx_chain_secret", ""),
                            ),
                            logging=LoggingSettings(
                                level=config_data.get("logging", {}).get(
                                    "level", "INFO"
                                ),
                                loki=LokiSettings(
                                    enabled=config_data.get("logging", {})
                                    .get("loki", {})
                                    .get("enabled", False),
                                    url=config_data.get("logging", {})
                                    .get("loki", {})
                                    .get("url", ""),
                                    username=config_data.get("logging", {})
                                    .get("loki", {})
                                    .get("username", ""),
                                    password=config_data.get("logging", {})
                                    .get("loki", {})
                                    .get("password", ""),
                                    labels=config_data.get("logging", {})
                                    .get("loki", {})
                                    .get("labels", {}),
                                ),
                            ),
                            backtesting=BacktestSettings(
                                candleResolution=config_data.get("backtesting", {}).get(
                                    "candleResolution", "1HOUR"
                                ),
                                maxHistoryDays=int(
                                    config_data.get("backtesting", {}).get(
                                        "maxHistoryDays", 90
                                    )
                                ),
                                startingBalance=float(
                                    config_data.get("backtesting", {}).get(
                                        "startingBalance", 1000.0
                                    )
                                ),
                                transactionFee=float(
                                    config_data.get("backtesting", {}).get(
                                        "transactionFee", 0.0005
                                    )
                                ),
                                slippage=float(
                                    config_data.get("backtesting", {}).get(
                                        "slippage", 0.001
                                    )
                                ),
                                benchmarkSymbol=config_data.get("backtesting", {}).get(
                                    "benchmarkSymbol", "BTC-USD"
                                ),
                                riskFreeRate=float(
                                    config_data.get("backtesting", {}).get(
                                        "riskFreeRate", 0.02
                                    )
                                ),
                            ),
                        )
                        if self.logger:
                            self.logger.info(
                                f"Configuration loaded for instance {self.instance_id}"
                            )
                            self.logger.info(
                                f"Network: {'TESTNET' if self.config.is_testnet else 'MAINNET'}"
                            )
                            self.logger.info(
                                f"Strategy: {self.config.botSettings.strategy}"
                            )
                        return

            # Fallback to environment-based config
            self.config = config()

            if self.config is None:
                raise RuntimeError("Failed to load configuration")

            if self.logger:
                self.logger.info(
                    f"Configuration loaded for instance {self.instance_id}"
                )
                self.logger.info(
                    f"Network: {'TESTNET' if self.config.is_testnet else 'MAINNET'}"
                )
                self.logger.info(f"Strategy: {self.config.botSettings.strategy}")
        except Exception as e:
            if self.logger:
                self._log_exception("Failed to load config: {}", e)
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

            # Initialize Telegram messenger with instance-specific credentials
            telegram_token = ""
            telegram_chat_id = ""
            if self.config and self.config.telegram:
                telegram_token = self.config.telegram.token or ""
                telegram_chat_id = self.config.telegram.chat_id or ""

            self.messenger = TelegramMessenger(
                bot_token=telegram_token,
                chat_id=telegram_chat_id,
                instance_id=self.instance_id,
                environment=self.config.environment if self.config else "development",
            )

            # Send startup message
            account_address = (
                self.config.dydx_testnet.dydx_chain_address
                if self.config.is_testnet
                else self.config.dydx_mainnet.dydx_chain_address
            )
            config_dict = {
                "instance_id": self.instance_id,
                "environment": self.config.environment,
                "is_testnet": self.config.is_testnet,
                "strategy": self.config.botSettings.strategy,
                "account_address": account_address,
                "usd_per_trade": self.config.botSettings.usdPerTrade,
                "zscore_threshold": self.config.botSettings.ZScoreThreshold,
            }
            self.messenger.send_startup_message(config_dict)

            # Connect to dYdX client using per-instance credentials
            self.logger.info("Connecting to dYdX client...")
            if self.config.is_testnet and self.config.dydx_testnet:
                instance_address = self.config.dydx_testnet.dydx_chain_address
                instance_mnemonic = self.config.dydx_testnet.dydx_chain_secret
            else:
                instance_address = (
                    self.config.dydx_mainnet.dydx_chain_address
                    if self.config.dydx_mainnet
                    else ""
                )
                instance_mnemonic = (
                    self.config.dydx_mainnet.dydx_chain_secret
                    if self.config.dydx_mainnet
                    else ""
                )
            if not instance_address:
                raise RuntimeError(
                    f"No dYdX chain address configured for instance {self.instance_id}"
                )
            self.client = await connect_dydx_runtime(
                address=instance_address,
                mnemonic=instance_mnemonic,
                is_testnet=self.config.is_testnet,
            )
            self.logger.info("Successfully connected to dYdX as {}", instance_address)

        except Exception as e:
            error_detail = self._describe_exception(e)
            if self.logger:
                self._log_exception("Failed to initialize bot instance: {}", e)
            if self.messenger:
                self.messenger.send_error_message(
                    "Initialization Failed",
                    f"Bot instance {self.instance_id} failed to initialize: {error_detail}",
                    is_critical=True,
                    category="lifecycle_init",
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
                selected_markets = getattr(bot_settings, "selectedMarkets", [])
                instance_resolution = getattr(bot_settings, "resolutionTimeframe", None)
                signature = inspect.signature(construct_market_prices)
                kwargs = {}
                if "selected_markets" in signature.parameters:
                    kwargs["selected_markets"] = selected_markets
                if "resolution" in signature.parameters and instance_resolution:
                    kwargs["resolution"] = instance_resolution
                    self.logger.info(
                        f"Using strategy resolution for cointegration: {instance_resolution}"
                    )
                df_market_prices = await construct_market_prices(self.client, **kwargs)

                # Store results in instance-specific file
                stores_result = store_cointegration_results(df_market_prices)
                save_succeeded = stores_result == "saved" or stores_result is True
                if isinstance(stores_result, dict):
                    save_succeeded = bool(stores_result.get("success"))
                if not save_succeeded:
                    error_detail = ""
                    if isinstance(stores_result, dict) and stores_result.get("error"):
                        error_detail = f": {stores_result['error']}"
                    raise RuntimeError(
                        f"Failed to save cointegration results{error_detail}"
                    )

                self.logger.info("Cointegration analysis completed")

        except Exception as e:
            error_detail = self._describe_exception(e)
            self._log_exception("Error in initial setup: {}", e)
            self.messenger.send_error_message(
                "Setup Failed",
                f"Bot instance {self.instance_id} setup failed: {error_detail}",
                is_critical=True,
                category="lifecycle_setup",
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
                        error_detail = self._describe_exception(e)
                        self._log_exception("Error managing exits: {}", e)
                        self.messenger.send_error_message(
                            "Exit Management Error",
                            f"Instance {self.instance_id}: {error_detail}",
                            is_critical=False,
                            category="execution_exit",
                        )

                # Place new trades
                if bot_settings.placeTrades:
                    try:
                        self.logger.debug("Finding trading opportunities...")
                        await open_positions(self.client)
                    except Exception as e:
                        error_detail = self._describe_exception(e)
                        self._log_exception("Error opening positions: {}", e)
                        self.messenger.send_error_message(
                            "Trade Entry Error",
                            f"Instance {self.instance_id}: {error_detail}",
                            is_critical=False,
                            category="execution_entry",
                        )

                # Sleep between iterations
                await asyncio.sleep(5)  # 5 second cycle

        except KeyboardInterrupt:
            self.logger.info(f"Bot instance {self.instance_id} stopped by user")
            self.messenger.send_shutdown_message(
                f"User interrupt (instance {self.instance_id})"
            )
        except Exception as e:
            error_detail = self._describe_exception(e)
            self._log_exception("Critical error in trading loop: {}", e)
            self.messenger.send_error_message(
                "Trading Loop Error",
                f"Instance {self.instance_id}: {error_detail}",
                is_critical=True,
                category="runtime_loop",
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
                if hasattr(self.logger, "exception"):
                    self.logger.exception(
                        "Bot instance {} failed: {}",
                        self.instance_id,
                        self._describe_exception(e),
                    )
                else:
                    self.logger.error(
                        f"Bot instance {self.instance_id} failed: {self._describe_exception(e)}"
                    )
        raise

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
