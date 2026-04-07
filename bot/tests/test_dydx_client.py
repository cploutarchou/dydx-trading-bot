import asyncio
import importlib
from types import SimpleNamespace


class _FakeIndexerClient:
    def __init__(self, host, api_timeout=5):
        self.host = host
        self.api_timeout = api_timeout


class _FakeNode:
    async def close(self):
        return None


def test_connect_dydx_uses_sdk_node_config(monkeypatch):
    dydx_client = importlib.import_module("src.trading.dydx_client")
    captured = {}

    async def _fake_connect(config):
        captured["config"] = config
        return _FakeNode()

    async def _fake_wallet_from_mnemonic(node, mnemonic, address):
        return SimpleNamespace(address=address, node=node, mnemonic=mnemonic)

    async def _fake_check_jurisdiction(client, market):
        assert market == "BTC-USD"
        return None

    monkeypatch.setattr(dydx_client, "IndexerClient", _FakeIndexerClient)
    monkeypatch.setattr(dydx_client.NodeClient, "connect", staticmethod(_fake_connect))
    monkeypatch.setattr(
        dydx_client.Wallet,
        "from_mnemonic",
        staticmethod(_fake_wallet_from_mnemonic),
    )
    monkeypatch.setattr(dydx_client, "check_jurisdiction", _fake_check_jurisdiction)
    monkeypatch.setattr(dydx_client, "_is_placeholder_value", lambda value: False)

    client = asyncio.run(dydx_client.connect_dydx())

    assert hasattr(captured["config"], "channel")
    assert client.node is not None
    assert getattr(client.wallet, "address", "") == dydx_client.DYDX_ADDRESS

