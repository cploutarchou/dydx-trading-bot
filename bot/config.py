from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

testnet_url = "https://indexer.v4testnet.dydx.exchange"
mainnet_url = "https://indexer.dydx.trade"


@dataclass
class IndexerEndpoint:
    testnet: str
    mainnet: str


@dataclass
class BotSettings:
    is_testnet: bool = False
    indexer_endpoint: str = testnet_url  # Will be set dynamically based on is_testnet
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

    @classmethod
    def from_env(cls) -> "BotSettings":
        """Load bot settings from environment variables with defaults."""
        import os

        is_testnet = os.getenv("IS_TESTNET", "true").lower() == "true"
        indexer_endpoint = testnet_url if is_testnet else mainnet_url

        return cls(
            is_testnet=is_testnet,
            indexer_endpoint=indexer_endpoint,
            abortAllPositions=os.getenv("BOT_ABORT_ALL_POSITIONS", "false").lower()
            == "true",
            findCointegratedPairs=os.getenv(
                "BOT_FIND_COINTEGRATED_PAIRS", "false"
            ).lower()
            == "true",
            manageExits=os.getenv("BOT_MANAGE_EXITS", "false").lower() == "true",
            placeTrades=os.getenv("BOT_PLACE_TRADES", "false").lower() == "true",
            resolutionTimeframe=os.getenv("BOT_RESOLUTION_TIMEFRAME", "1HOUR"),
            strategy=os.getenv("BOT_STRATEGY", "cointegration"),
            statsWindow=int(os.getenv("BOT_STATS_WINDOW", "21")),
            maxHalfLife=int(os.getenv("BOT_MAX_HALF_LIFE", "24")),
            ZScoreThreshold=float(os.getenv("BOT_ZSCORE_THRESHOLD", "1.5")),
            usdPerTrade=float(os.getenv("BOT_USD_PER_TRADE", "10.0")),
            usdMinCollateral=float(os.getenv("BOT_USD_MIN_COLLATERAL", "100.0")),
            closeAtZscoreCross=os.getenv("BOT_CLOSE_AT_ZSCORE_CROSS", "true").lower()
            == "true",
        )


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
        """Load configuration from environment variables with optional YAML fallback."""
        import os

        from dotenv import load_dotenv

        # Load environment variables from .env file
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        try:
            # Load configuration primarily from environment variables

            # Load configuration from environment variables
            is_testnet = os.getenv("IS_TESTNET", "true").lower() == "true"
            environment = os.getenv("ENVIRONMENT", "development")
            is_testnet = os.getenv("IS_TESTNET", "true").lower() == "true"
            environment = os.getenv("ENVIRONMENT", "development")

            # Load all settings from environment variables
            bot_settings = BotSettings.from_env()
            backtest_settings = BacktestSettings.from_env()

            # Load Telegram settings from environment
            telegram_settings = TelegramSettings(
                token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
                chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            )

            # Load dYdX credentials from environment
            dydx_testnet = DYDXTestnetSettings(
                dydx_chain_address=os.getenv("DYDX_TESTNET_ADDRESS", ""),
                dydx_chain_secret=os.getenv("DYDX_TESTNET_MNEMONIC", ""),
            )

            dydx_mainnet = DYDXMainnetSettings(
                dydx_chain_address=os.getenv("DYDX_MAINNET_ADDRESS", ""),
                dydx_chain_secret=os.getenv("DYDX_MAINNET_MNEMONIC", ""),
            )

            # Load other settings from environment
            logging_settings = self._build_logging_settings_from_env()
            database_settings = self._build_database_settings_from_env()
            redis_settings = self._build_redis_settings_from_env()

            # Create DydxConfig instance
            self._config = DydxConfig(
                is_testnet=is_testnet,
                environment=environment,
                telegram=telegram_settings,
                botSettings=bot_settings,
                dydx_testnet=dydx_testnet,
                dydx_mainnet=dydx_mainnet,
                logging=logging_settings,
                backtesting=backtest_settings,
                database=database_settings,
                redis=redis_settings,
            )
        except Exception as e:
            raise ValueError(
                f"Error loading configuration from environment variables: {e}"
            )

    def _build_logging_settings_from_env(self) -> LoggingSettings:
        """Build logging settings from environment variables."""
        import os

        loki_settings = LokiSettings(
            enabled=os.getenv("LOKI_ENABLED", "false").lower() == "true",
            url=os.getenv("LOKI_URL", ""),
            username=os.getenv("LOKI_USERNAME", ""),
            password=os.getenv("LOKI_PASSWORD", ""),
            tenant_id=os.getenv("LOKI_TENANT_ID"),
            labels=self._parse_loki_labels(os.getenv("LOKI_LABELS", "{}")),
        )

        return LoggingSettings(
            level=os.getenv("LOG_LEVEL", "INFO"),
            loki=loki_settings,
        )

    def _parse_loki_labels(self, labels_str: str) -> Dict[str, str]:
        """Parse Loki labels from JSON string."""
        try:
            import json

            labels = json.loads(labels_str)
            return {str(k): str(v) for k, v in labels.items()}
        except Exception:
            return {}

    def _build_database_settings_from_env(self) -> DatabaseSettings:
        """Build database settings from environment variables."""
        import os

        return DatabaseSettings(
            type=os.getenv("DB_TYPE", "sqlite"),
            name=os.getenv("DB_NAME", "trading_bot.db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
        )

    def _build_redis_settings_from_env(self) -> RedisSettings:
        """Build Redis settings from environment variables."""
        import os

        return RedisSettings(
            enabled=os.getenv("REDIS_ENABLED", "false").lower() == "true",
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD", ""),
            ssl=os.getenv("REDIS_SSL", "false").lower() == "true",
            timeout=int(os.getenv("REDIS_TIMEOUT", "5")),
        )

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
