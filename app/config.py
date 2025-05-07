import yaml
from dataclasses import dataclass
from typing import Optional
from pathlib import Path


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


@dataclass
class TelegramSettings:
    token: str
    chat_id: str


@dataclass
class DydxConfig:
    dydx_chain_address: str
    dydx_secret_phrase: str
    is_testnet: bool
    telegram: TelegramSettings
    botSettings: BotSettings


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
            config_path = Path(__file__).parent / "config.yaml"

        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)

            # Parse nested structures
            indexer = data["botSettings"]["indexer_endpoint"]
            indexer_endpoint = IndexerEndpoint(**indexer)

            bot_settings = BotSettings(
                **{**data["botSettings"], "indexer_endpoint": indexer_endpoint}
            )

            telegram_settings = TelegramSettings(**data["telegram"])

            self._config = DydxConfig(
                dydx_chain_address=data["dydx_chain_address"],
                dydx_secret_phrase=data["dydx_secret_phrase"],
                is_testnet=data["is_testnet"],
                telegram=telegram_settings,
                botSettings=bot_settings,
            )
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found at: {config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML configuration: {e}")
        except KeyError as e:
            raise KeyError(f"Missing required configuration key: {e}")


# Create a global instance for easy access
config = ConfigurationManager.get_config
