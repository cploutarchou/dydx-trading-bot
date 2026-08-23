from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from src.shared.env_loader import load_repo_env

testnet_url = "https://indexer.v4testnet.dydx.exchange"
mainnet_url = "https://indexer.dydx.trade"


def _get_env(*names: str, default: str = "") -> str:
    import os

    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return default


def _get_env_int(*names: str, default: int) -> int:
    for name in names:
        value = _get_env(name)
        if value == "":
            continue
        try:
            return int(value)
        except ValueError:
            continue
    return default


def _get_env_float(*names: str, default: float) -> float:
    for name in names:
        value = _get_env(name)
        if value == "":
            continue
        try:
            return float(value)
        except ValueError:
            continue
    return default


def _get_env_bool(*names: str, default: bool) -> bool:
    raw = _get_env(*names, default="")
    if raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _split_endpoint_url(raw: str, default_scheme: str) -> tuple[str, str, str]:
    value = str(raw or "").strip()
    if value == "":
        return "", "", ""
    if "://" not in value:
        value = f"{default_scheme}://{value}"
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    port = str(parsed.port or "")
    scheme = parsed.scheme or default_scheme
    return host, port, scheme


@dataclass
class IndexerEndpoint:
    testnet: str
    mainnet: str


@dataclass
class BotSettings:
    is_testnet: bool = False
    indexer_endpoint: str = testnet_url  # Will be set dynamically based on is_testnet
    subaccountNumber: int = 0
    capitalAllocationUsd: float = 0.0
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
    maxPositions: int = 5
    maxDrawdownPct: float = 0.0
    stopLossPct: float = 2.0
    takeProfitPct: float = 5.0
    trailingStopPct: float = 0.0
    rebalanceIntervalHours: int = 24
    positionTimeoutHours: int = 72
    selectedMarkets: List[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "BotSettings":
        """Load bot settings from environment variables with defaults."""
        import os

        is_testnet = os.getenv("IS_TESTNET", "true").lower() == "true"
        indexer_endpoint = testnet_url if is_testnet else mainnet_url

        return cls(
            is_testnet=is_testnet,
            indexer_endpoint=indexer_endpoint,
            subaccountNumber=int(os.getenv("BOT_SUBACCOUNT_NUMBER", "0")),
            capitalAllocationUsd=float(os.getenv("BOT_CAPITAL_ALLOCATION_USD", "0.0")),
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
            maxPositions=int(os.getenv("BOT_MAX_POSITIONS", "5")),
            maxDrawdownPct=float(os.getenv("BOT_MAX_DRAWDOWN_PCT", "0.0")),
            stopLossPct=float(os.getenv("BOT_STOP_LOSS_PCT", "2.0")),
            takeProfitPct=float(os.getenv("BOT_TAKE_PROFIT_PCT", "5.0")),
            trailingStopPct=float(os.getenv("BOT_TRAILING_STOP_PCT", "0.0")),
            rebalanceIntervalHours=int(os.getenv("BOT_REBALANCE_INTERVAL_HOURS", "24")),
            positionTimeoutHours=int(os.getenv("BOT_POSITION_TIMEOUT_HOURS", "72")),
            selectedMarkets=[
                market.strip()
                for market in os.getenv("BOT_SELECTED_MARKETS", "").split(",")
                if market.strip()
            ],
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
    type: str = "postgres"
    cutover_mode: str = "shared"
    name: str = "dydx_bot"
    user: str = "dydx_bot"
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
class ValkeySettings:
    enabled: bool = True
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ssl: bool = False
    timeout: int = 5
    cache_ttl_seconds: int = 86400
    max_connections: int = 10


@dataclass
class NATSSettings:
    enabled: bool = False
    url: str = "nats://localhost:4222"
    monitoring_url: str = "http://localhost:8222"
    stream_prefix: str = "bot"
    command_bus_enabled: bool = False


@dataclass
class ClickHouseSettings:
    enabled: bool = False
    url: str = ""
    host: str = "localhost"
    port: int = 8123
    database: str = "default"
    user: str = "default"
    password: str = "change-me-clickhouse"
    secure: bool = False
    batch_size: int = 1000
    flush_interval_seconds: float = 5.0


@dataclass
class MinIOSettings:
    enabled: bool = False
    endpoint: str = ""
    console_url: str = ""
    bucket: str = "backtests"
    access_key: str = ""
    secret_key: str = ""
    secure: bool = False


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
    valkey: ValkeySettings = field(default_factory=ValkeySettings)
    nats: NATSSettings = field(default_factory=NATSSettings)
    clickhouse: ClickHouseSettings = field(default_factory=ClickHouseSettings)
    minio: MinIOSettings = field(default_factory=MinIOSettings)


class ConfigurationManager:
    _instance: Optional["ConfigurationManager"] = None
    _config: Optional[DydxConfig] = None

    def __new__(cls) -> "ConfigurationManager":
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

    def load_config(self) -> None:
        """Load configuration from environment variables with optional YAML fallback."""
        import os

        # Load environment variables from config/profiles.
        load_repo_env(__file__)

        try:
            # Load configuration primarily from environment variables

            # Load configuration from environment variables
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

            # dYdX credentials are managed through encrypted app settings and
            # per-instance bot payloads, not through the shared runtime config.
            dydx_testnet = DYDXTestnetSettings(
                dydx_chain_address="",
                dydx_chain_secret="",
            )

            dydx_mainnet = DYDXMainnetSettings(
                dydx_chain_address="",
                dydx_chain_secret="",
            )

            # Load other settings from environment
            logging_settings = self._build_logging_settings_from_env()
            database_settings = self._build_database_settings_from_env()
            redis_settings = self._build_redis_settings_from_env()
            valkey_settings = self._build_valkey_settings_from_env()
            nats_settings = self._build_nats_settings_from_env()
            clickhouse_settings = self._build_clickhouse_settings_from_env()
            minio_settings = self._build_minio_settings_from_env()

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
                valkey=valkey_settings,
                nats=nats_settings,
                clickhouse=clickhouse_settings,
                minio=minio_settings,
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
        db_type = _get_env("BOT_DB_TYPE", "DB_TYPE", default="postgres").strip().lower()
        if db_type not in {"postgres", "postgresql"}:
            raise ValueError(
                f"Unsupported DB_TYPE '{db_type}'. Supported: postgres, postgresql."
            )

        cutover_mode = (
            _get_env("BOT_DB_CUTOVER_MODE", default="shared")
            .strip()
            .lower()
            .replace("-", "_")
        )
        if cutover_mode not in {
            "shared",
            "dedicated",
            "dedicated_with_shared_fallback",
        }:
            raise ValueError(
                "Unsupported BOT_DB_CUTOVER_MODE. Use one of: "
                "shared, dedicated, dedicated_with_shared_fallback"
            )

        return DatabaseSettings(
            type="postgres",
            cutover_mode=cutover_mode,
            name=_get_env("BOT_DB_NAME", "DB_NAME", "POSTGRES_DB", default="dydx_bot"),
            user=_get_env(
                "BOT_DB_USER",
                "DB_USER",
                "POSTGRES_USER",
                default="dydx_bot",
            ),
            password=_get_env(
                "BOT_DB_PASSWORD",
                "DB_PASSWORD",
                "POSTGRES_PASSWORD",
                default="",
            ),
            host=_get_env(
                "BOT_DB_HOST",
                "DB_HOST",
                "POSTGRES_HOST",
                default="localhost",
            ),
            port=_get_env(
                "BOT_DB_PORT",
                "DB_PORT",
                "POSTGRES_PORT",
                default="5432",
            ),
            pool_size=_get_env_int("DB_POOL_SIZE", default=5),
            max_overflow=_get_env_int("DB_MAX_OVERFLOW", default=10),
            timeout=_get_env_int("DB_TIMEOUT", default=5),
        )

    def _build_redis_settings_from_env(self) -> RedisSettings:
        """Build Redis settings from environment variables."""
        return RedisSettings(
            enabled=_get_env_bool("REDIS_ENABLED", "VALKEY_ENABLED", default=False),
            host=_get_env("REDIS_HOST", "VALKEY_HOST", default="localhost"),
            port=_get_env_int("REDIS_PORT", "VALKEY_PORT", default=6379),
            db=_get_env_int("REDIS_DB", "VALKEY_DB", default=0),
            password=_get_env("REDIS_PASSWORD", "VALKEY_PASSWORD", default=""),
            ssl=_get_env_bool("REDIS_SSL", "VALKEY_SSL", default=False),
            timeout=_get_env_int("REDIS_TIMEOUT", "VALKEY_TIMEOUT", default=5),
            cache_ttl_seconds=_get_env_int(
                "REDIS_CACHE_TTL_SECONDS",
                "REDIS_CACHE_TTL",
                "VALKEY_CACHE_TTL_SECONDS",
                "VALKEY_CACHE_TTL",
                default=86400,
            ),
            max_connections=_get_env_int(
                "REDIS_MAX_CONNECTIONS", "VALKEY_MAX_CONNECTIONS", default=10
            ),
        )

    def _build_valkey_settings_from_env(self) -> ValkeySettings:
        """Build canonical Valkey settings from environment variables."""
        redis_settings = self._build_redis_settings_from_env()
        return ValkeySettings(
            enabled=_get_env_bool(
                "VALKEY_ENABLED", "REDIS_ENABLED", default=redis_settings.enabled
            ),
            host=_get_env("VALKEY_HOST", "REDIS_HOST", default=redis_settings.host),
            port=_get_env_int("VALKEY_PORT", "REDIS_PORT", default=redis_settings.port),
            db=_get_env_int("VALKEY_DB", "REDIS_DB", default=redis_settings.db),
            password=_get_env(
                "VALKEY_PASSWORD",
                "REDIS_PASSWORD",
                default=redis_settings.password or "",
            ),
            ssl=_get_env_bool("VALKEY_SSL", "REDIS_SSL", default=redis_settings.ssl),
            timeout=_get_env_int(
                "VALKEY_TIMEOUT", "REDIS_TIMEOUT", default=redis_settings.timeout
            ),
            cache_ttl_seconds=_get_env_int(
                "VALKEY_CACHE_TTL_SECONDS",
                "VALKEY_CACHE_TTL",
                "REDIS_CACHE_TTL_SECONDS",
                "REDIS_CACHE_TTL",
                default=redis_settings.cache_ttl_seconds,
            ),
            max_connections=_get_env_int(
                "VALKEY_MAX_CONNECTIONS",
                "REDIS_MAX_CONNECTIONS",
                default=redis_settings.max_connections,
            ),
        )

    def _build_nats_settings_from_env(self) -> NATSSettings:
        return NATSSettings(
            enabled=_get_env_bool("NATS_ENABLED", default=False),
            url=_get_env("NATS_URL", default="nats://localhost:4222"),
            monitoring_url=_get_env(
                "NATS_MONITORING_URL", default="http://localhost:8222"
            ),
            stream_prefix=_get_env("NATS_STREAM_PREFIX", default="bot"),
            command_bus_enabled=_get_env_bool("BOT_COMMAND_BUS_ENABLED", default=False),
        )

    def _build_clickhouse_settings_from_env(self) -> ClickHouseSettings:
        raw_url = _get_env("BACKTEST_CLICKHOUSE_URL", "CLICKHOUSE_URL", default="")
        host, parsed_port, scheme = _split_endpoint_url(raw_url, "http")
        default_secure = scheme == "https"

        return ClickHouseSettings(
            enabled=_get_env_bool(
                "CLICKHOUSE_ENABLED",
                "BACKTEST_CLICKHOUSE_WRITES_ENABLED",
                "BACKTEST_CLICKHOUSE_ENABLED",
                default=True,
            ),
            url=raw_url,
            host=host
                 or _get_env(
                "BACKTEST_CLICKHOUSE_HOST", "CLICKHOUSE_HOST", default="localhost"
            ),
            port=(
                int(parsed_port)
                if parsed_port
                else _get_env_int(
                    "BACKTEST_CLICKHOUSE_PORT", "CLICKHOUSE_PORT", default=8123
                )
            ),
            database=_get_env(
                "BACKTEST_CLICKHOUSE_DATABASE",
                "CLICKHOUSE_DATABASE",
                default=(
                            urlsplit(
                                raw_url if "://" in raw_url else f"http://{raw_url}"
                            ).path.lstrip("/")
                            if raw_url
                            else ""
                        )
                        or "default",
            ),
            user=_get_env(
                "BACKTEST_CLICKHOUSE_USER",
                "CLICKHOUSE_USER",
                default=(
                            urlsplit(
                                raw_url if "://" in raw_url else f"http://{raw_url}"
                            ).username
                            if raw_url
                            else ""
                        )
                        or "default",
            ),
            password=_get_env(
                "BACKTEST_CLICKHOUSE_PASSWORD",
                "CLICKHOUSE_PASSWORD",
                default=(
                            urlsplit(
                                raw_url if "://" in raw_url else f"http://{raw_url}"
                            ).password
                            if raw_url
                            else ""
                        )
                        or "",
            ),
            secure=default_secure
                   or _get_env_bool(
                "BACKTEST_CLICKHOUSE_SECURE", "CLICKHOUSE_SECURE", default=False
            ),
            batch_size=_get_env_int(
                "BACKTEST_CLICKHOUSE_BATCH_SIZE",
                "CLICKHOUSE_BATCH_SIZE",
                default=1000,
            ),
            flush_interval_seconds=_get_env_float(
                "BACKTEST_CLICKHOUSE_FLUSH_INTERVAL_SECONDS",
                "CLICKHOUSE_FLUSH_INTERVAL_SECONDS",
                default=5.0,
            ),
        )

    def _build_minio_settings_from_env(self) -> MinIOSettings:
        endpoint = _get_env(
            "BACKTEST_MINIO_ENDPOINT",
            "S3_ENDPOINT",
            "MINIO_ENDPOINT",
            default="",
        )
        _, _, scheme = _split_endpoint_url(endpoint, "http")
        return MinIOSettings(
            enabled=_get_env_bool(
                "MINIO_ENABLED",
                "BACKTEST_ARTIFACT_STORAGE_ENABLED",
                "BACKTEST_MINIO_ARTIFACTS_ENABLED",
                default=True,
            ),
            endpoint=endpoint,
            console_url=_get_env("MINIO_CONSOLE_URL", default=""),
            bucket=_get_env(
                "BACKTEST_MINIO_BUCKET", "MINIO_BUCKET", default="backtests"
            ),
            access_key=_get_env(
                "BACKTEST_MINIO_ACCESS_KEY",
                "MINIO_ACCESS_KEY",
                "MINIO_ROOT_USER",
                default="minioadmin",
            ),
            secret_key=_get_env(
                "BACKTEST_MINIO_SECRET_KEY",
                "MINIO_SECRET_KEY",
                "MINIO_ROOT_PASSWORD",
                default="change-me-minio",
            ),
            secure=_get_env_bool("BACKTEST_MINIO_SECURE", default=(scheme == "https")),
        )

    def _build_logging_settings(self, data: dict[str, Any]) -> LoggingSettings:
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
