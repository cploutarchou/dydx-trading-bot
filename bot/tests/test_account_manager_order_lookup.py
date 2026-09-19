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


# --- node rejection and bounded fallback -------------------------------------


class _RejectingNode(_FakeNode):
    def __init__(self, response):
        self._response = response

    async def place_order(self, _wallet, _order):
        return self._response


class _CountingAccount(_FakeAccount):
    async def get_subaccount_orders(self, *args, **kwargs):
        self._calls_made = getattr(self, "_calls_made", 0) + 1
        return await super().get_subaccount_orders(*args, **kwargs)


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(
            tx_response=SimpleNamespace(code=5, raw_log="insufficient funds")
        ),
        {"tx_response": {"code": 5, "raw_log": "insufficient funds"}},
        {"code": "5", "rawLog": "insufficient funds"},
    ],
)
def test_rejected_tx_raises_without_polling(_patch_market_and_sleep, response):
    client = _FakeClient(snapshots=[[]])
    client.node = _RejectingNode(response)
    account = _CountingAccount([[]])
    client.indexer_account = SimpleNamespace(account=account)

    with pytest.raises(account_manager.OrderRejectedError) as excinfo:
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

    assert excinfo.value.code == 5
    assert "insufficient funds" in str(excinfo.value)
    # No order exists, so the indexer must not be polled for one.
    assert getattr(account, "_calls_made", 0) == 0


@pytest.mark.parametrize(
    "response",
    [
        {"tx": "ok"},
        SimpleNamespace(tx_response=SimpleNamespace(code=0, raw_log="")),
        {"tx_response": {"code": 0}},
    ],
)
def test_accepted_broadcast_is_not_treated_as_rejection(response):
    assert account_manager._broadcast_rejection(response) is None


def _snapshot_order(order_id, **fields):
    base = {
        "id": order_id,
        "clientId": "999",
        "clobPairId": "72",
        "side": "BUY",
        "size": "60",
        "reduceOnly": False,
    }
    base.update(fields)
    return base


def _resolve(orders, **bounds):
    return account_manager._resolve_order_from_snapshot(
        orders,
        market_order_id=SimpleNamespace(client_id=4242, clob_pair_id=72),
        expected_side="BUY",
        expected_size="60",
        expected_reduce_only=False,
        allow_fallback=True,
        **bounds,
    )


def test_fallback_ignores_orders_older_than_placement_block():
    """Same market, side and size as an earlier, already filled entry."""
    older = [_snapshot_order("older-filled", createdAtHeight=100)]

    assert _resolve(older, min_created_height=123, min_good_til_block=134) is None


def test_fallback_ignores_short_term_orders_with_an_earlier_good_til_block():
    older = [_snapshot_order("older-short-term", goodTilBlock=130)]

    assert _resolve(older, min_created_height=123, min_good_til_block=134) is None


def test_fallback_accepts_an_order_placed_at_this_block():
    orders = [
        _snapshot_order("older-filled", goodTilBlock=120),
        _snapshot_order("just-placed", goodTilBlock=134),
    ]

    assert _resolve(orders, min_created_height=123, min_good_til_block=134) == (
        "just-placed"
    )


def test_fallback_rejects_orders_with_no_placement_bound_at_all():
    assert (
        _resolve(
            [_snapshot_order("unknown-age")],
            min_created_height=123,
            min_good_til_block=134,
        )
        is None
    )


def test_deterministic_client_id_match_is_unaffected_by_the_bounds():
    orders = [_snapshot_order("mine", clientId="4242", createdAtHeight=1)]

    assert _resolve(orders, min_created_height=123, min_good_til_block=134) == "mine"
