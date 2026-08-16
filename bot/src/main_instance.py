"""Instance runtime entrypoint used by `BotInstanceManager` worker processes."""

# ⚠️ CRITICAL: Load environment variables FIRST, before any other imports
from src.shared.env_loader import load_repo_env

load_repo_env(__file__)

import argparse
import asyncio
import hashlib
import inspect
import json
import os
import signal
from typing import Any, Awaitable, Dict, Optional, TypeVar, overload, cast

from loguru import logger

# Import configuration and bot functions
from config.config import config
from src.infrastructure.database import db
from src.infrastructure.persistence.repository import UnitOfWork
from src.shared.credentials_cipher import open_config_secrets
from src.shared.logging_setup import setup_logging
from src.shared.notifications import TelegramMessenger
from src.shared.live_risk_controls import assert_supported_live_risk_controls
from src.trading.account_manager import abort_all_positions
from src.trading.analysis.cointegration import store_cointegration_results
from src.trading.dydx_client import connect_dydx_runtime
from src.trading.market_data import construct_market_prices
from src.trading.position_manager import manage_trade_exits, open_positions

_T = TypeVar("_T")


class BotInstance:
    """Individual bot instance with isolated state and configuration"""

    def __init__(self, instance_id: str, config_file: Optional[str] = None):
        self.instance_id = instance_id
        self.deprecated_config_file = config_file
        self._deprecated_config_file_warning_emitted = False
        self.logger: Optional[Any] = None
        self.client: Optional[Any] = None
        self.messenger: Optional[TelegramMessenger] = None
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

    def _require_logger(self) -> Any:
        if self.logger is None:
            raise RuntimeError("Logger is not initialized")
        return self.logger

    def _require_config(self) -> Any:
        if self.config is None:
            raise RuntimeError("Configuration is not initialized")
        return self.config

    def _require_messenger(self) -> TelegramMessenger:
        if self.messenger is None:
            raise RuntimeError("Messenger is not initialized")
        return self.messenger

    @overload
    async def _maybe_await(self, value: Awaitable[_T]) -> _T: ...

    @overload
    async def _maybe_await(self, value: _T) -> _T: ...

    async def _maybe_await(self, value: Awaitable[_T] | _T) -> _T:
        """Await values only when they are awaitable (supports sync/async callables)."""
        if inspect.isawaitable(value):
            return await cast(Awaitable[_T], value)
        return value

    def setup_logging(self):
        """Setup instance-specific logging"""
        setup_logging()
        self.logger = logger.bind(
            instance_id=self.instance_id, component="bot_instance"
        )
        self._require_logger().info(f"Bot instance {self.instance_id} initializing...")

    @staticmethod
    def _canonical_runtime_config_data(config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Strip non-runtime metadata so hash comparisons are stable."""
        payload = dict(config_data or {})
        payload.pop("_config_meta", None)
        payload.pop("config_meta", None)
        payload.pop("runtime_state", None)
        return payload

    def _runtime_config_hash(self, config_data: Dict[str, Any]) -> str:
        canonical = self._canonical_runtime_config_data(config_data)
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _warn_on_config_metadata_hash_mismatch(
        self, db_payload: Optional[Dict[str, Any]]
    ) -> None:
        if self.logger is None:
            return
        if not db_payload:
            return

        db_meta = db_payload.get("_config_meta") or db_payload.get("config_meta")
        if isinstance(db_meta, dict):
            expected_hash = str(db_meta.get("payload_hash") or "").strip()
            if expected_hash:
                actual_hash = self._runtime_config_hash(db_payload)
                if expected_hash != actual_hash:
                    self.logger.warning(
                        "Runtime config metadata hash mismatch instance_id={} "
                        "expected_hash={} actual_hash={}",
                        self.instance_id,
                        expected_hash,
                        actual_hash,
                    )

    def _warn_if_deprecated_config_file_supplied(self) -> None:
        if not self.deprecated_config_file:
            return
        if self._deprecated_config_file_warning_emitted:
            return
        self._deprecated_config_file_warning_emitted = True
        if self.logger is not None:
            self.logger.warning(
                "Ignoring deprecated runtime config file path for {}; "
                "DB-backed bot_instances.config is required",
                self.instance_id,
            )

    def _load_config_data_from_db(self) -> Optional[Dict[str, Any]]:
        session = None
        try:
            session = db.get_session()
            uow = UnitOfWork(session)
            bot = uow.bots.get_by_instance_id(self.instance_id)
            if bot is None:
                return None
            payload = dict(getattr(bot, "config", None) or {})
            if not payload:
                return None
            config_meta = getattr(bot, "config_meta", None)
            if isinstance(config_meta, dict) and config_meta:
                payload["_config_meta"] = dict(config_meta)
            # Decrypt sealed credential/telegram envelopes so the runtime worker
            # receives plaintext secrets. If this raises (e.g. missing/mismatched
            # key), the surrounding handler logs and returns None so the worker
            # fails loudly instead of signing with empty credentials.
            return open_config_secrets(payload)
        except Exception as exc:
            if self.logger is not None:
                self.logger.warning(
                    "Failed to load instance config from database for {}: {}",
                    self.instance_id,
                    self._describe_exception(exc),
                )
            return None
        finally:
            if session is not None:
                session.close()

    @staticmethod
    def _coerce_bool(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @staticmethod
    def _required_mapping(payload: Dict[str, Any], key: str) -> Dict[str, Any]:
        value = payload.get(key)
        if not isinstance(value, dict) or not value:
            raise ValueError(f"DB runtime config is missing required '{key}' object")
        return value

    @staticmethod
    def _required_text(payload: Dict[str, Any], key: str) -> str:
        value = str(payload.get(key) or "").strip()
        if not value:
            raise ValueError(f"DB runtime config is missing required '{key}' value")
        return value

    def _normalize_db_runtime_payload(
        self, config_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert persisted DB config into the runtime DydxConfig input shape."""
        payload = self._canonical_runtime_config_data(config_data)
        if "botSettings" in payload:
            bot_settings = self._required_mapping(payload, "botSettings")
            if "is_testnet" not in payload:
                raise ValueError(
                    "DB runtime config is missing required 'is_testnet' value"
                )
            is_testnet = self._coerce_bool(payload.get("is_testnet"), default=True)
            network_key = "dydx_testnet" if is_testnet else "dydx_mainnet"
            network_payload = self._required_mapping(payload, network_key)
            self._required_text(network_payload, "dydx_chain_address")
            self._required_text(network_payload, "dydx_chain_secret")
            if "subaccountNumber" not in bot_settings:
                raise ValueError(
                    "DB runtime config is missing required "
                    "'botSettings.subaccountNumber' value"
                )
            if not str(bot_settings.get("strategy") or "").strip():
                raise ValueError(
                    "DB runtime config is missing required 'botSettings.strategy' value"
                )
            return payload

        runtime_defaults = config()
        if runtime_defaults is None:
            raise RuntimeError("Failed to resolve runtime configuration defaults")

        credentials = self._required_mapping(payload, "credentials")
        trading = self._required_mapping(payload, "trading_params")
        assert_supported_live_risk_controls(trading)
        if "is_testnet" not in trading:
            raise ValueError(
                "DB runtime config is missing required 'trading_params.is_testnet' value"
            )
        if "subaccount_number" not in trading:
            raise ValueError(
                "DB runtime config is missing required 'trading_params.subaccount_number' value"
            )
        if not str(trading.get("strategy") or "").strip():
            raise ValueError(
                "DB runtime config is missing required 'trading_params.strategy' value"
            )

        address = self._required_text(credentials, "address")
        mnemonic = self._required_text(credentials, "mnemonic")
        is_testnet = self._coerce_bool(trading.get("is_testnet"), default=True)

        telegram_payload = payload.get("telegram")
        telegram = telegram_payload if isinstance(telegram_payload, dict) else {}
        backtesting_payload = payload.get("backtesting_params")
        backtesting = (
            backtesting_payload if isinstance(backtesting_payload, dict) else {}
        )
        selected_markets = trading.get("selected_markets")
        if not isinstance(selected_markets, list):
            selected_markets = trading.get("selectedMarkets", [])

        loki_defaults = runtime_defaults.logging.loki

        return {
            "is_testnet": is_testnet,
            "environment": runtime_defaults.environment,
            "telegram": {
                "token": telegram.get("token") or runtime_defaults.telegram.token,
                "chat_id": telegram.get("chat_id") or runtime_defaults.telegram.chat_id,
            },
            "botSettings": {
                "subaccountNumber": trading.get("subaccount_number", 0),
                "capitalAllocationUsd": trading.get("capital_allocation_usd", 0.0),
                "abortAllPositions": trading.get("abort_all_positions", False),
                "findCointegratedPairs": trading.get("find_cointegrated_pairs", False),
                "manageExits": trading.get("manage_exits", False),
                "placeTrades": trading.get("place_trades", False),
                "resolutionTimeframe": trading.get("resolution_timeframe", "1HOUR"),
                "strategy": trading.get("strategy", "cointegration"),
                "statsWindow": trading.get("stats_window", 21),
                "maxHalfLife": trading.get("max_half_life", 24),
                "ZScoreThreshold": trading.get("zscore_threshold", 1.5),
                "usdPerTrade": trading.get("usd_per_trade", 10.0),
                "usdMinCollateral": trading.get("usd_min_collateral", 100.0),
                "closeAtZscoreCross": trading.get("close_at_zscore_cross", True),
                "maxPositions": trading.get("max_positions", 5),
                "maxDrawdownPct": trading.get("max_drawdown_pct", 0.0),
                "stopLossPct": trading.get("stop_loss_pct", 2.0),
                "takeProfitPct": trading.get("take_profit_pct", 5.0),
                "trailingStopPct": trading.get("trailing_stop_pct", 0.0),
                "rebalanceIntervalHours": trading.get("rebalance_interval_hours", 24),
                "positionTimeoutHours": trading.get("position_timeout_hours", 72),
                "selectedMarkets": selected_markets,
            },
            "backtesting": {
                "candleResolution": backtesting.get(
                    "candle_resolution",
                    runtime_defaults.backtesting.candleResolution,
                ),
                "maxHistoryDays": backtesting.get(
                    "max_history_days", runtime_defaults.backtesting.maxHistoryDays
                ),
                "startingBalance": backtesting.get(
                    "starting_balance", runtime_defaults.backtesting.startingBalance
                ),
                "transactionFee": backtesting.get(
                    "transaction_fee", runtime_defaults.backtesting.transactionFee
                ),
                "slippage": backtesting.get(
                    "slippage", runtime_defaults.backtesting.slippage
                ),
                "benchmarkSymbol": backtesting.get(
                    "benchmark_symbol",
                    runtime_defaults.backtesting.benchmarkSymbol,
                ),
                "riskFreeRate": backtesting.get(
                    "risk_free_rate", runtime_defaults.backtesting.riskFreeRate
                ),
            },
            "dydx_testnet": {
                "dydx_chain_address": address if is_testnet else "",
                "dydx_chain_secret": mnemonic if is_testnet else "",
            },
            "dydx_mainnet": {
                "dydx_chain_address": "" if is_testnet else address,
                "dydx_chain_secret": "" if is_testnet else mnemonic,
            },
            "logging": {
                "level": runtime_defaults.logging.level,
                "loki": {
                    "enabled": loki_defaults.enabled,
                    "url": loki_defaults.url,
                    "username": loki_defaults.username,
                    "password": loki_defaults.password,
                    "labels": {
                        **(loki_defaults.labels or {}),
                        "instance": self.instance_id,
                    },
                },
            },
        }

    def _build_runtime_config(self, config_data: Dict[str, Any]) -> Any:
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

        dydx_config_factory = cast(Any, DydxConfig)
        telegram_settings_factory = cast(Any, TelegramSettings)
        bot_settings_factory = cast(Any, BotSettings)
        dydx_testnet_settings_factory = cast(Any, DYDXTestnetSettings)
        dydx_mainnet_settings_factory = cast(Any, DYDXMainnetSettings)
        logging_settings_factory = cast(Any, LoggingSettings)
        loki_settings_factory = cast(Any, LokiSettings)
        backtest_settings_factory = cast(Any, BacktestSettings)
        config_data = self._normalize_db_runtime_payload(config_data)

        return dydx_config_factory(
            is_testnet=config_data.get("is_testnet", True),
            environment=config_data.get("environment", "development"),
            telegram=telegram_settings_factory(
                token=config_data.get("telegram", {}).get("token", ""),
                chat_id=config_data.get("telegram", {}).get("chat_id", ""),
            ),
            botSettings=bot_settings_factory(
                is_testnet=config_data.get("is_testnet", True),
                subaccountNumber=int(
                    config_data.get("botSettings", {}).get("subaccountNumber", 0)
                ),
                capitalAllocationUsd=float(
                    config_data.get("botSettings", {}).get("capitalAllocationUsd", 0.0)
                ),
                abortAllPositions=config_data.get("botSettings", {}).get(
                    "abortAllPositions", False
                ),
                findCointegratedPairs=config_data.get("botSettings", {}).get(
                    "findCointegratedPairs", False
                ),
                manageExits=config_data.get("botSettings", {}).get(
                    "manageExits", False
                ),
                placeTrades=config_data.get("botSettings", {}).get(
                    "placeTrades", False
                ),
                resolutionTimeframe=config_data.get("botSettings", {}).get(
                    "resolutionTimeframe", "1HOUR"
                ),
                strategy=config_data.get("botSettings", {}).get(
                    "strategy", "cointegration"
                ),
                statsWindow=int(
                    config_data.get("botSettings", {}).get("statsWindow", 21)
                ),
                maxHalfLife=int(
                    config_data.get("botSettings", {}).get("maxHalfLife", 24)
                ),
                ZScoreThreshold=float(
                    config_data.get("botSettings", {}).get("ZScoreThreshold", 1.5)
                ),
                usdPerTrade=float(
                    config_data.get("botSettings", {}).get("usdPerTrade", 10.0)
                ),
                usdMinCollateral=float(
                    config_data.get("botSettings", {}).get("usdMinCollateral", 100.0)
                ),
                closeAtZscoreCross=config_data.get("botSettings", {}).get(
                    "closeAtZscoreCross", True
                ),
                maxPositions=int(
                    config_data.get("botSettings", {}).get("maxPositions", 5)
                ),
                maxDrawdownPct=float(
                    config_data.get("botSettings", {}).get("maxDrawdownPct", 15.0)
                ),
                stopLossPct=float(
                    config_data.get("botSettings", {}).get("stopLossPct", 2.0)
                ),
                takeProfitPct=float(
                    config_data.get("botSettings", {}).get("takeProfitPct", 5.0)
                ),
                trailingStopPct=float(
                    config_data.get("botSettings", {}).get("trailingStopPct", 1.0)
                ),
                rebalanceIntervalHours=int(
                    config_data.get("botSettings", {}).get("rebalanceIntervalHours", 24)
                ),
                positionTimeoutHours=int(
                    config_data.get("botSettings", {}).get("positionTimeoutHours", 72)
                ),
                selectedMarkets=[
                    str(market).strip()
                    for market in config_data.get("botSettings", {}).get(
                        "selectedMarkets", []
                    )
                    if str(market).strip()
                ],
            ),
            dydx_testnet=dydx_testnet_settings_factory(
                dydx_chain_address=config_data.get("dydx_testnet", {}).get(
                    "dydx_chain_address", ""
                ),
                dydx_chain_secret=config_data.get("dydx_testnet", {}).get(
                    "dydx_chain_secret", ""
                ),
            ),
            dydx_mainnet=dydx_mainnet_settings_factory(
                dydx_chain_address=config_data.get("dydx_mainnet", {}).get(
                    "dydx_chain_address", ""
                ),
                dydx_chain_secret=config_data.get("dydx_mainnet", {}).get(
                    "dydx_chain_secret", ""
                ),
            ),
            logging=logging_settings_factory(
                level=config_data.get("logging", {}).get("level", "INFO"),
                loki=loki_settings_factory(
                    enabled=config_data.get("logging", {})
                    .get("loki", {})
                    .get("enabled", False),
                    url=config_data.get("logging", {}).get("loki", {}).get("url", ""),
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
            backtesting=backtest_settings_factory(
                candleResolution=config_data.get("backtesting", {}).get(
                    "candleResolution", "1HOUR"
                ),
                maxHistoryDays=int(
                    config_data.get("backtesting", {}).get("maxHistoryDays", 90)
                ),
                startingBalance=float(
                    config_data.get("backtesting", {}).get("startingBalance", 1000.0)
                ),
                transactionFee=float(
                    config_data.get("backtesting", {}).get("transactionFee", 0.0005)
                ),
                slippage=float(
                    config_data.get("backtesting", {}).get("slippage", 0.001)
                ),
                benchmarkSymbol=config_data.get("backtesting", {}).get(
                    "benchmarkSymbol", "BTC-USD"
                ),
                riskFreeRate=float(
                    config_data.get("backtesting", {}).get("riskFreeRate", 0.02)
                ),
            ),
        )

    def load_config(self):
        """Load instance-specific configuration"""
        try:
            self._warn_if_deprecated_config_file_supplied()
            db_payload = self._load_config_data_from_db()
            if not db_payload:
                raise RuntimeError(
                    "DB-backed runtime config is required but missing for "
                    f"instance {self.instance_id}"
                )

            self._warn_on_config_metadata_hash_mismatch(db_payload)
            self.config = self._build_runtime_config(db_payload)
            if self.logger is not None:
                self.logger.info(
                    "Runtime config loaded from database for {}", self.instance_id
                )

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
            self._require_logger().info(
                f"Received signal {signum}, shutting down instance {self.instance_id}..."
            )
            self.running = False
            raise GracefulShutdownException("Shutdown signal received")

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def initialize(self):
        """Initialize bot instance"""
        try:
            self.setup_logging()
            self.load_config()
            self.setup_signal_handlers()

            runtime_logger = self._require_logger()
            runtime_config = self._require_config()

            # Initialize Telegram messenger with instance-specific credentials
            telegram_token = ""
            telegram_chat_id = ""
            if runtime_config.telegram:
                telegram_token = runtime_config.telegram.token or ""
                telegram_chat_id = runtime_config.telegram.chat_id or ""

            self.messenger = TelegramMessenger(
                bot_token=telegram_token,
                chat_id=telegram_chat_id,
                instance_id=self.instance_id,
                environment=runtime_config.environment,
            )

            # Send startup message
            account_address = (
                runtime_config.dydx_testnet.dydx_chain_address
                if runtime_config.is_testnet
                else runtime_config.dydx_mainnet.dydx_chain_address
            )
            config_dict = {
                "instance_id": self.instance_id,
                "environment": runtime_config.environment,
                "is_testnet": runtime_config.is_testnet,
                "strategy": runtime_config.botSettings.strategy,
                "account_address": account_address,
                "usd_per_trade": runtime_config.botSettings.usdPerTrade,
                "zscore_threshold": runtime_config.botSettings.ZScoreThreshold,
            }
            self._require_messenger().send_startup_message(config_dict)

            # Connect to dYdX client using per-instance credentials
            runtime_logger.info("Connecting to dYdX client...")
            if runtime_config.is_testnet and runtime_config.dydx_testnet:
                instance_address = runtime_config.dydx_testnet.dydx_chain_address
                instance_mnemonic = runtime_config.dydx_testnet.dydx_chain_secret
            else:
                instance_address = (
                    runtime_config.dydx_mainnet.dydx_chain_address
                    if runtime_config.dydx_mainnet
                    else ""
                )
                instance_mnemonic = (
                    runtime_config.dydx_mainnet.dydx_chain_secret
                    if runtime_config.dydx_mainnet
                    else ""
                )
            if not instance_address:
                raise RuntimeError(
                    f"No dYdX chain address configured for instance {self.instance_id}"
                )
            self.client = await connect_dydx_runtime(
                address=instance_address,
                mnemonic=instance_mnemonic,
                is_testnet=runtime_config.is_testnet,
            )
            runtime_logger.info(
                "Successfully connected to dYdX as {}", instance_address
            )

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
        runtime_messenger: TelegramMessenger | None = None
        try:
            runtime_logger = self._require_logger()
            runtime_config = self._require_config()
            runtime_messenger = self._require_messenger()
            # Get bot settings
            bot_settings = runtime_config.botSettings

            # Abort all open positions if requested
            if bot_settings.abortAllPositions:
                runtime_logger.info("Closing open positions...")
                await self._maybe_await(abort_all_positions(self.client))
                runtime_logger.info("All positions closed")

            # Find cointegrated pairs if requested
            if bot_settings.findCointegratedPairs:
                runtime_logger.info("Starting cointegration analysis...")
                selected_markets = getattr(bot_settings, "selectedMarkets", [])
                instance_resolution = getattr(bot_settings, "resolutionTimeframe", None)
                signature = inspect.signature(construct_market_prices)
                kwargs = {}
                if "selected_markets" in signature.parameters:
                    kwargs["selected_markets"] = selected_markets
                if "resolution" in signature.parameters and instance_resolution:
                    kwargs["resolution"] = instance_resolution
                    runtime_logger.info(
                        f"Using strategy resolution for cointegration: {instance_resolution}"
                    )
                df_market_prices = await self._maybe_await(
                    construct_market_prices(self.client, **kwargs)
                )

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

                runtime_logger.info("Cointegration analysis completed")

        except Exception as e:
            error_detail = self._describe_exception(e)
            self._log_exception("Error in initial setup: {}", e)
            if runtime_messenger is not None:
                runtime_messenger.send_error_message(
                    "Setup Failed",
                    f"Bot instance {self.instance_id} setup failed: {error_detail}",
                    is_critical=True,
                    category="lifecycle_setup",
                )
            raise

    async def trading_loop(self):
        """Main trading loop"""
        self.running = True
        runtime_logger = self._require_logger()
        runtime_config = self._require_config()
        runtime_messenger = self._require_messenger()
        runtime_logger.info(f"Starting trading loop for instance {self.instance_id}")

        try:
            while self.running:
                bot_settings = runtime_config.botSettings

                # Manage existing positions
                if bot_settings.manageExits:
                    try:
                        runtime_logger.debug("Managing exits...")
                        await self._maybe_await(manage_trade_exits(self.client))
                        await asyncio.sleep(1)
                    except Exception as e:
                        error_detail = self._describe_exception(e)
                        self._log_exception("Error managing exits: {}", e)
                        runtime_messenger.send_error_message(
                            "Exit Management Error",
                            f"Instance {self.instance_id}: {error_detail}",
                            is_critical=False,
                            category="execution_exit",
                        )

                # Place new trades
                if bot_settings.placeTrades:
                    try:
                        runtime_logger.debug("Finding trading opportunities...")
                        await self._maybe_await(open_positions(self.client))
                    except Exception as e:
                        error_detail = self._describe_exception(e)
                        self._log_exception("Error opening positions: {}", e)
                        runtime_messenger.send_error_message(
                            "Trade Entry Error",
                            f"Instance {self.instance_id}: {error_detail}",
                            is_critical=False,
                            category="execution_entry",
                        )

                # Sleep between iterations
                await asyncio.sleep(5)  # 5 second cycle

        except (KeyboardInterrupt, GracefulShutdownException):
            runtime_logger.info(f"Bot instance {self.instance_id} stopped by user")
            runtime_messenger.send_shutdown_message(
                f"User interrupt (instance {self.instance_id})"
            )
        except Exception as e:
            error_detail = self._describe_exception(e)
            self._log_exception("Critical error in trading loop: {}", e)
            runtime_messenger.send_error_message(
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
        except GracefulShutdownException:
            # Handle graceful shutdown from signal handlers
            if self.logger:
                self.logger.info(
                    "Bot instance {} gracefully shutting down", self.instance_id
                )
            raise
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


def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments for worker instance execution."""
    parser = argparse.ArgumentParser(description="Run a single bot instance worker")
    parser.add_argument(
        "--instance-id",
        dest="instance_id",
        required=True,
        help="Unique instance id assigned by BotInstanceManager",
    )
    parser.add_argument(
        "--config",
        dest="config",
        default=None,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


async def main():
    """Main entry point for bot instance"""
    try:
        args = parse_arguments()

        # Create and run bot instance
        bot = BotInstance(instance_id=args.instance_id, config_file=args.config)

        await bot.run()

    except (KeyboardInterrupt, GracefulShutdownException):
        print("Bot instance interrupted")
        # Let the application exit naturally without sys.exit()
        return
    except Exception as e:
        print(f"Bot instance failed: {e}")
        # Re-raise for proper error propagation instead of sys.exit(1)
        raise


class GracefulShutdownException(Exception):
    """Exception raised for graceful shutdown requests."""

    pass


if __name__ == "__main__":
    asyncio.run(main())
