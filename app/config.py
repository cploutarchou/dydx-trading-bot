from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import yaml


@dataclass
class IndexerEndpoint:
    testnet: str
    mainnet: str


@dataclass
class BotSettings:
    abortAllPositions: bool = False
    findCointegratedPairs: bool = False
    manageExits: bool = False
    placeTrades: bool = False
    resolutionTimeframe: str = "1HOUR"
    strategy: str = "cointegration"
    statsWindow: int = 21
    maxHalfLife: int = 24
    ZScoreThreshold: float = 1.5
    usdPerTrade: float = 10.0
    usdMinCollateral: float = 100.0
    closeAtZscoreCross: bool = True
    indexer_endpoint: IndexerEndpoint = field(
        default_factory=lambda: IndexerEndpoint(testnet="", mainnet="")
    )
    # WalletSettings is optional in the YAML; if present add parsing logic later

    @classmethod
    def from_env(cls) -> "BotSettings":
        """Load bot settings from environment variables with defaults."""
        import os

        return cls(
            abortAllPositions=cls._parse_bool(
                os.getenv("BOT_ABORT_ALL_POSITIONS", "false")
            ),
            findCointegratedPairs=cls._parse_bool(
                os.getenv("BOT_FIND_COINTEGRATED_PAIRS", "true")
            ),
            manageExits=cls._parse_bool(os.getenv("BOT_MANAGE_EXITS", "true")),
            placeTrades=cls._parse_bool(os.getenv("BOT_PLACE_TRADES", "true")),
            resolutionTimeframe=os.getenv("BOT_RESOLUTION_TIMEFRAME", "1HOUR"),
            strategy=os.getenv("BOT_STRATEGY", "cointegration"),
            statsWindow=int(os.getenv("BOT_STATS_WINDOW", "21")),
            maxHalfLife=int(os.getenv("BOT_MAX_HALF_LIFE", "24")),
            ZScoreThreshold=float(os.getenv("BOT_ZSCORE_THRESHOLD", "1.5")),
            usdPerTrade=float(os.getenv("BOT_USD_PER_TRADE", "10.0")),
            usdMinCollateral=float(os.getenv("BOT_USDC_MIN_COLLATERAL", "100.0")),
            closeAtZscoreCross=cls._parse_bool(
                os.getenv("BOT_CLOSE_AT_ZSCORE_CROSS", "true")
            ),
            indexer_endpoint=IndexerEndpoint(
                testnet=os.getenv(
                    "INDEXER_TESTNET", "https://indexer.v4testnet.dydx.exchange"
                ),
                mainnet=os.getenv("INDEXER_MAINNET", "https://indexer.dydx.trade"),
            ),
        )

    @staticmethod
    def _parse_bool(value: str) -> bool:
        """Parse string to boolean."""
        return value.lower() in ("true", "1", "yes", "on")


@dataclass
class EthereumSettings:
    Address: str = ""
    PrivateKey: str = ""


@dataclass
class WalletSettings:
    EthereumSettings: EthereumSettings = field(
        default_factory=lambda: EthereumSettings()
    )


@dataclass
class TelegramSettings:
    token: str = ""
    chat_id: str = ""


@dataclass
class DYDXTestnetSettings:
    dydx_chain_address: str = ""
    dydx_chain_secret: str = ""


@dataclass
class DYDXMainnetSettings:
    dydx_chain_address: str = ""
    dydx_chain_secret: str = ""


@dataclass
class LokiSettings:
    enabled: bool = False
    url: str = ""
    username: str = ""
    password: str = ""
    tenant_id: Optional[str] = None
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class LoggingSettings:
    level: str = "INFO"
    loki: LokiSettings = field(default_factory=LokiSettings)


@dataclass
class BacktestSettings:
    # Historical data settings
    candleResolution: str = "1HOUR"
    maxHistoryDays: int = 90

    # Simulation parameters
    startingBalance: float = 1000.0
    transactionFee: float = 0.0005  # 0.05% per trade (dYdX maker fee)
    slippage: float = 0.001  # 0.1% estimated slippage

    # Analysis settings
    benchmarkSymbol: str = "BTC-USD"
    riskFreeRate: float = 0.02  # Annual risk-free rate (2%)

    @classmethod
    def from_env(cls) -> "BacktestSettings":
        """Load backtest settings from environment variables with defaults."""
        import os

        return cls(
            candleResolution=os.getenv("BACKTEST_CANDLE_RESOLUTION", "1HOUR"),
            maxHistoryDays=int(os.getenv("BACKTEST_MAX_HISTORY_DAYS", "90")),
            startingBalance=float(os.getenv("BACKTEST_STARTING_BALANCE", "1000.0")),
            transactionFee=float(os.getenv("BACKTEST_TRANSACTION_FEE", "0.0005")),
            slippage=float(os.getenv("BACKTEST_SLIPPAGE", "0.001")),
            benchmarkSymbol=os.getenv("BACKTEST_BENCHMARK_SYMBOL", "BTC-USD"),
            riskFreeRate=float(os.getenv("BACKTEST_RISK_FREE_RATE", "0.02")),
        )


@dataclass
class DatabaseSettings:
    type: str = "sqlite"  # sqlite or postgresql
    name: str = "dydx_backtest.db"
    user: str = "postgres"
    password: str = ""
    host: str = "localhost"
    port: str = "5432"
    pool_size: int = 5
    max_overflow: int = 10
    timeout: int = 30


@dataclass
class RedisSettings:
    enabled: bool = True
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ssl: bool = False
    timeout: int = 5
    cache_ttl_seconds: int = 86400  # 24 hours
    max_connections: int = 10


@dataclass
class DydxConfig:
    is_testnet: bool = False
    environment: str = "development"
    telegram: TelegramSettings = field(default_factory=TelegramSettings)
    botSettings: BotSettings = field(default_factory=BotSettings)
    dydx_testnet: DYDXTestnetSettings = field(default_factory=DYDXTestnetSettings)
    dydx_mainnet: DYDXMainnetSettings = field(default_factory=DYDXMainnetSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    backtesting: BacktestSettings = field(default_factory=BacktestSettings)
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    redis: RedisSettings = field(default_factory=RedisSettings)


class ConfigurationManager:
    _instance: Optional["ConfigurationManager"] = None
    _config: Optional[DydxConfig] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigurationManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_config(cls) -> Optional[DydxConfig]:
        """Get the configuration instance. Loads it if not already loaded."""
        if cls._instance is None or cls._instance._config is None:
            cls._instance = ConfigurationManager()
            cls._instance.load_config()
        return cls._instance._config

    def load_config(self, config_path: Optional[str | Path] = None) -> None:
        """Load configuration from the YAML file and environment variables."""
        if config_path is None:
            # Default to looking for config.yaml in the same directory as this file
            app_config_path = Path(__file__).parent / "config.yaml"
            scripts_config_path = (
                Path(__file__).parent.parent / "scripts" / "config.yaml"
            )

            # Try app directory first, then scripts directory
            if app_config_path.exists():
                config_path = app_config_path
            elif scripts_config_path.exists():
                config_path = scripts_config_path
            else:
                config_path = app_config_path  # Default to app path for error message

        # Normalize to Path
        config_path = Path(config_path)

        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)

            # Handle different config structures (with or without 'dydx' top-level key)
            if "dydx" in data:
                dydx_data = data["dydx"]
                dydx_chain_address = dydx_data.get("dydx_chain_address", "")
                dydx_secret_phrase = dydx_data.get("dydx_secret_phrase", "")
                is_testnet = dydx_data.get("is_testnet", False)
            else:
                dydx_chain_address = data.get("dydx_chain_address", "")
                dydx_secret_phrase = data.get("dydx_secret_phrase", "")
                is_testnet = data.get("is_testnet", False)

            # Parse nested structures
            indexer = data.get("botSettings", {}).get("indexer_endpoint", {})
            indexer_endpoint = IndexerEndpoint(**indexer) if indexer else None

            # Load BotSettings from environment variables first, then fallback to YAML
            try:
                bot_settings = BotSettings.from_env()
                # Override with YAML values if present (for backward compatibility)
                if "botSettings" in data:
                    yaml_bot_settings = data["botSettings"]
                    if not indexer:  # Use YAML indexer if env vars not set
                        bot_settings.indexer_endpoint = IndexerEndpoint(
                            testnet=yaml_bot_settings.get("indexer_endpoint", {}).get(
                                "testnet", bot_settings.indexer_endpoint.testnet
                            ),
                            mainnet=yaml_bot_settings.get("indexer_endpoint", {}).get(
                                "mainnet", bot_settings.indexer_endpoint.mainnet
                            ),
                        )
            except Exception:
                # Fallback to YAML-only parsing if env loading fails
                bot_settings = BotSettings(
                    **{
                        **data.get("botSettings", {}),
                        "indexer_endpoint": indexer_endpoint
                        or IndexerEndpoint(testnet="", mainnet=""),
                    }
                )

            telegram_settings = TelegramSettings(**data.get("telegram", {}))

            # Load BacktestSettings from environment variables first, then fallback to YAML
            try:
                backtest_settings = BacktestSettings.from_env()
                # Override with YAML values if present (for backward compatibility)
                if "backtesting" in data:
                    yaml_backtest = data["backtesting"]
                    # Update with YAML values if they differ from defaults
                    for key, value in yaml_backtest.items():
                        if hasattr(backtest_settings, key):
                            setattr(backtest_settings, key, value)
            except Exception:
                # Fallback to YAML-only parsing if env loading fails
                backtest_settings = BacktestSettings(**data.get("backtesting", {}))

            # Build DYDX network settings. Support either a top-level `dydx` block
            # or explicit `dydx_testnet`/`dydx_mainnet` keys.
            if "dydx" in data:
                dydx_testnet = DYDXTestnetSettings(
                    dydx_chain_address=dydx_chain_address,
                    dydx_chain_secret=dydx_secret_phrase,
                )
                dydx_mainnet = DYDXMainnetSettings(
                    dydx_chain_address=dydx_chain_address,
                    dydx_chain_secret=dydx_secret_phrase,
                )
            else:
                # Expect explicit sub-keys when no top-level `dydx` block
                dt = data.get("dydx_testnet", {})
                dm = data.get("dydx_mainnet", {})
                dydx_testnet = DYDXTestnetSettings(**dt)
                dydx_mainnet = DYDXMainnetSettings(**dm)

            logging_settings = self._build_logging_settings(data)

            # Parse database and redis settings from YAML
            database_settings = DatabaseSettings(**(data.get("database", {})))
            redis_settings = RedisSettings(**(data.get("redis", {})))

            # Create DydxConfig instance
            self._config = DydxConfig(
                is_testnet=is_testnet,
                environment=data.get("environment", "development"),
                telegram=telegram_settings,
                botSettings=bot_settings,
                dydx_testnet=dydx_testnet,
                dydx_mainnet=dydx_mainnet,
                logging=logging_settings,
                backtesting=backtest_settings,
                database=database_settings,
                redis=redis_settings,
            )
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found at: {config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML configuration: {e}")
        except KeyError as e:
            raise KeyError(f"Missing required configuration key: {e}")

    def _build_logging_settings(self, data: dict) -> LoggingSettings:
        logging_data = data.get("logging")
        if logging_data is None:
            return LoggingSettings()

        loki_data = logging_data.get("loki", {}) or {}

        # Ensure labels are stored as a dictionary of strings
        raw_labels = loki_data.get("labels") or {}
        labels: Dict[str, str] = {
            str(key): str(value) for key, value in raw_labels.items()
        }

        loki_settings = LokiSettings(
            enabled=bool(loki_data.get("enabled", False)),
            url=str(loki_data.get("url", "")),
            username=str(loki_data.get("username", "")),
            password=str(loki_data.get("password", "")),
            tenant_id=loki_data.get("tenant_id"),
            labels=labels,
        )

        return LoggingSettings(
            level=str(logging_data.get("level", "INFO")),
            loki=loki_settings,
        )


# Create a global instance for easy access
config = ConfigurationManager.get_config
