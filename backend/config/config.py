from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

testnet_url = "https://indexer.v4testnet.dydx.exchange"
mainnet_url = "https://indexer.dydx.trade"


@dataclass
class IndexerEndpoint:
    testnet: str
    mainnet: str


@dataclass
class DatabaseSettings:
    type: str = "postgresql"
    host: str = "localhost"
    port: int = 5432
    dbname: str = "dydx_bot"
    user: str = "dydx_bot"
    password: str = ""
    ssl: bool = False
    timeout: int = 5
    max_connections: int = 10
    pool_size: int = 5
    max_overflow: int = 10
    enabled: bool = True
    def __post_init__(self):
        if self.type == "postgresql":
            self.dsn = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"
        elif self.type == "sqlite":
            self.dsn = f"sqlite:///{self.dbname}"


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
class DYDX:
    is_testnet: bool = False
    DYDXTestnetSettings: DYDXTestnetSettings = field(
        default_factory=lambda: DYDXTestnetSettings()
    )
    DYDXMainnetSettings: DYDXMainnetSettings = field(
        default_factory=lambda: DYDXMainnetSettings()
    )


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


@dataclass
class RedisSettings:
    enabled: bool = True
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""
    ssl: bool = False
    timeout: int = 5
    max_connections: int = 10
    ttl_seconds: int = 86400
    cache_ttl_seconds: int = 86400


@dataclass
class AuthSettings:
    jwt_secret_key: str = "your - secret - key - change - in -production - use - strong - key - 32 - chars"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7


@dataclass
class Config:
    database: DatabaseSettings = field(default_factory=lambda: DatabaseSettings())
    indexer: IndexerEndpoint = field(
        default_factory=lambda: IndexerEndpoint(testnet=testnet_url, mainnet=mainnet_url)
    )
    wallet: WalletSettings = field(default_factory=lambda: WalletSettings())
    telegram: TelegramSettings = field(default_factory=lambda: TelegramSettings())
    dydx: DYDX = field(default_factory=lambda: DYDX())
    loki: LokiSettings = field(default_factory=lambda: LokiSettings())
    backtest: BacktestSettings = field(default_factory=lambda: BacktestSettings())
    redis: RedisSettings = field(default_factory=lambda: RedisSettings())
    auth: AuthSettings = field(default_factory=lambda: AuthSettings())
