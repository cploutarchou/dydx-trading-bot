import yaml

from app.config import ConfigurationManager


def write_temp_yaml(tmp_path, data):
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(data))
    return str(p)


def test_load_config_with_dydx_block(tmp_path):
    data = {
        "dydx": {
            "dydx_chain_address": "addr",
            "dydx_secret_phrase": "seed words",
            "is_testnet": True,
        },
        "telegram": {"token": "t", "chat_id": "1"},
        "botSettings": {
            "abortAllPositions": True,
            "findCointegratedPairs": True,
            "manageExits": True,
            "placeTrades": True,
            "resolutionTimeframe": "1HOUR",
            "strategy": "cointegration",
            "statsWindow": 21,
            "maxHalfLife": 24,
            "ZScoreThreshold": 1.5,
            "usdPerTrade": 10,
            "usdMinCollateral": 100,
            "closeAtZscoreCross": True,
            "indexer_endpoint": {"testnet": "t", "mainnet": "m"},
        },
    }

    cfg_path = write_temp_yaml(tmp_path, data)
    cm = ConfigurationManager()
    cm.load_config(cfg_path)
    cfg = cm._config
    assert cfg.is_testnet is True
    assert cfg.telegram.token == "t"
    assert cfg.botSettings.ZScoreThreshold == 1.5


def test_load_config_with_explicit_networks(tmp_path):
    data = {
        "dydx_testnet": {"dydx_chain_address": "addr_t", "dydx_chain_secret": "seed_t"},
        "dydx_mainnet": {"dydx_chain_address": "addr_m", "dydx_chain_secret": "seed_m"},
        "telegram": {"token": "t", "chat_id": "1"},
        "botSettings": {
            "abortAllPositions": True,
            "findCointegratedPairs": True,
            "manageExits": True,
            "placeTrades": True,
            "resolutionTimeframe": "1HOUR",
            "strategy": "cointegration",
            "statsWindow": 21,
            "maxHalfLife": 24,
            "ZScoreThreshold": 1.5,
            "usdPerTrade": 10,
            "usdMinCollateral": 100,
            "closeAtZscoreCross": True,
            "indexer_endpoint": {"testnet": "t", "mainnet": "m"},
        },
    }

    cfg_path = write_temp_yaml(tmp_path, data)
    cm = ConfigurationManager()
    cm.load_config(cfg_path)
    cfg = cm._config
    assert cfg.dydx_testnet.dydx_chain_address == "addr_t"
    assert cfg.dydx_mainnet.dydx_chain_address == "addr_m"
