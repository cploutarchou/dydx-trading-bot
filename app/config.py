from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class IndexerEndpoint:
    testnet: str
    mainnet: str


@dataclass
class BotSettings:
    abortAllPositions: bool
    findCointegratedPairs: bool
    manageExits: bool
    placeTrades: bool
    resolutionTimeframe: str
    strategy: str
    statsWindow: int
    maxHalfLife: int
    ZScoreThreshold: float
    usdPerTrade: float
    usdMinCollateral: float
    closeAtZscoreCross: bool
    indexer_endpoint: IndexerEndpoint
    # WalletSettings is optional in the YAML; if present add parsing logic later


@dataclass
class EthereumSettings:
    Address: str
    PrivateKey: str


@dataclass
class WalletSettings:
    EthereumSettings: EthereumSettings


@dataclass
class TelegramSettings:
    token: str
    chat_id: str


@dataclass
class DYDXTestnetSettings:
    dydx_chain_address: str
    dydx_chain_secret: str


@dataclass
class DYDXMainnetSettings:
    dydx_chain_address: str
    dydx_chain_secret: str


@dataclass
class DydxConfig:
    is_testnet: bool
    telegram: TelegramSettings
    botSettings: BotSettings
    dydx_testnet: DYDXTestnetSettings
    dydx_mainnet: DYDXMainnetSettings


class ConfigurationManager:
    _instance: Optional["ConfigurationManager"] = None
    _config: Optional[DydxConfig] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigurationManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_config(cls) -> DydxConfig:
        """Get the configuration instance. Loads it if not already loaded."""
        if cls._instance is None or cls._instance._config is None:
            cls._instance = ConfigurationManager()
            cls._instance.load_config()
        return cls._instance._config

    def load_config(self, config_path: str = None) -> None:
        """Load configuration from the YAML file."""
        if config_path is None:
            # Default to looking for config.yaml in the same directory as this file
            app_config_path = Path(__file__).parent / "config.yaml"
            scripts_config_path = Path(__file__).parent.parent / "scripts" / "config.yaml"

            # Try app directory first, then scripts directory
            if app_config_path.exists():
                config_path = app_config_path
            elif scripts_config_path.exists():
                config_path = scripts_config_path
            else:
                config_path = app_config_path  # Default to app path for error message

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
            indexer = data["botSettings"]["indexer_endpoint"]
            indexer_endpoint = IndexerEndpoint(**indexer)

            bot_settings = BotSettings(
                **{**data["botSettings"], "indexer_endpoint": indexer_endpoint}
            )

            telegram_settings = TelegramSettings(**data["telegram"])

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

            # Create DydxConfig instance
            self._config = DydxConfig(
                is_testnet=is_testnet,
                telegram=telegram_settings,
                botSettings=bot_settings,
                dydx_testnet=dydx_testnet,
                dydx_mainnet=dydx_mainnet,
            )
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found at: {config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML configuration: {e}")
        except KeyError as e:
            raise KeyError(f"Missing required configuration key: {e}")


# Create a global instance for easy access
config = ConfigurationManager.get_config
