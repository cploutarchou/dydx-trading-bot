"""Regression tests for robust order id lookup after order placement."""

import asyncio
from types import SimpleNamespace

import pytest

from src.trading import account_manager


class _FakeMarket:
    def __init__(self, _payload):
        pass

    def order_id(self, _address, _subaccount, client_id, _flags):
        # Keep clob pair deterministic for test matching.
        return SimpleNamespace(client_id=client_id, clob_pair_id=72)

    def order(self, _market_order_id, **_kwargs):
        return {"ok": True}


class _FakeNode:
    async def latest_block_height(self):
        return 123

    async def place_order(self, _wallet, _order):
        return {"tx": "ok"}


class _FakeMarkets:
    async def get_perpetual_markets(self, ticker):
        return {"markets": {ticker: {}}}


class _FakeAccount:
    def __init__(self, snapshots):
        self._snapshots = list(snapshots)
        self._calls = 0

    async def get_subaccount_orders(self, *_args, **_kwargs):
        if self._calls < len(self._snapshots):
            value = self._snapshots[self._calls]
            self._calls += 1
            return value
        return self._snapshots[-1] if self._snapshots else []


class _FakeClient:
    def __init__(self, snapshots):
        self.wallet = SimpleNamespace(address="dydx1testaddress")
        self.node = _FakeNode()
        self.indexer = SimpleNamespace(markets=_FakeMarkets())
        self.indexer_account = SimpleNamespace(account=_FakeAccount(snapshots))


@pytest.fixture
def _patch_market_and_sleep(monkeypatch):
    monkeypatch.setattr(account_manager, "Market", _FakeMarket)
    monkeypatch.setattr(account_manager.random, "randint", lambda _a, _b: 4242)

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr(account_manager.asyncio, "sleep", _fast_sleep)


def test_place_market_order_retries_until_matching_order_appears(
    _patch_market_and_sleep,
):
    client = _FakeClient(
        snapshots=[
            [],
            [
                {
                    "id": "older-non-match",
                    "clientId": "999",
                    "clobPairId": "72",
                    "side": "BUY",
                    "size": "60",
                    "reduceOnly": False,
                    "createdAtHeight": 1,
                }
            ],
            [
                {
                    "id": "match-order-id",
                    "clientId": "4242",
                    "clobPairId": "72",
                    "side": "BUY",
                    "size": "60",
                    "reduceOnly": False,
                    "createdAtHeight": 2,
                }
            ],
        ]
    )

    _order, order_id = asyncio.run(
        account_manager.place_market_order(
            client,
            market="IMX-USD",
            side="BUY",
            size="60",
            price="0.166",
            reduce_only=False,
        )
    )

    assert order_id == "match-order-id"


def test_place_market_order_raises_clean_runtime_error_when_orders_never_appear(
    _patch_market_and_sleep,
):
    client = _FakeClient(snapshots=[[], [], [], []])

    with pytest.raises(RuntimeError) as exc:
        asyncio.run(
            account_manager.place_market_order(
                client,
                market="IMX-USD",
                side="BUY",
                size="60",
                price="0.166",
                reduce_only=False,
            )
        )

    assert "Unable to detect latest exchange order id after placement" in str(exc.value)
