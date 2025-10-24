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
class DydxConfig:
    is_testnet: bool = False
    environment: str = "development"
    telegram: TelegramSettings = field(default_factory=TelegramSettings)
    backtesting: BacktestSettings = field(default_factory=BacktestSettings)
