import asyncio
import importlib
from datetime import datetime, timedelta, timezone
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


def test_check_jurisdiction_skips_recent_success(monkeypatch):
    dydx_client = importlib.import_module("src.trading.dydx_client")
    now = datetime.now(timezone.utc)

    dydx_client._jurisdiction_success_cache.clear()
    dydx_client._jurisdiction_success_cache["BTC-USD"] = now

    async def _should_not_run(*args, **kwargs):
        raise AssertionError("expected cached jurisdiction check to skip network call")

    monkeypatch.setattr(dydx_client, "get_candles_recent", _should_not_run)

    async def _run():
        await dydx_client.check_jurisdiction(SimpleNamespace(), "BTC-USD")

    asyncio.run(_run())


def test_check_jurisdiction_refreshes_expired_success(monkeypatch):
    dydx_client = importlib.import_module("src.trading.dydx_client")
    stale = datetime.now(timezone.utc) - timedelta(minutes=11)
    calls = {"count": 0}

    dydx_client._jurisdiction_success_cache.clear()
    dydx_client._jurisdiction_success_cache["BTC-USD"] = stale

    async def _fake_get_candles_recent(*args, **kwargs):
        calls["count"] += 1
        return []

    monkeypatch.setattr(dydx_client, "get_candles_recent", _fake_get_candles_recent)

    async def _run():
        await dydx_client.check_jurisdiction(SimpleNamespace(), "BTC-USD")

    asyncio.run(_run())

    assert calls["count"] == 1
    assert dydx_client._jurisdiction_success_cache["BTC-USD"] > stale
