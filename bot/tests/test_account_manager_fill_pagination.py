"""Regression tests for backwards pagination of subaccount fills."""

import asyncio
from types import SimpleNamespace

from src.trading import account_manager


class _FakeIndexerFills:
    """Newest-first fills with an inclusive ``created_before_or_at`` bound."""

    def __init__(self, fills):
        self._fills = fills
        self.cursors = []

    async def get_subaccount_fills(
        self, _address, _subaccount, ticker=None, limit=100, created_before_or_at=None
    ):
        self.cursors.append(created_before_or_at)
        window = [
            fill
            for fill in self._fills
            if created_before_or_at is None or fill["createdAt"] <= created_before_or_at
        ]
        return {"fills": window[:limit]}


def _client(fake):
    return SimpleNamespace(indexer_account=SimpleNamespace(account=fake))


def _fills(count, target_positions, *, same_timestamp=False):
    fills = []
    for index in range(count):
        # Newest first: larger index == older fill.
        second = 0 if same_timestamp else count - index
        fills.append(
            {
                "id": f"fill-{index}",
                "orderId": "target" if index in target_positions else f"other-{index}",
                "createdAt": f"2026-01-01T00:{second // 60:02d}:{second % 60:02d}.000Z",
            }
        )
    return fills


def _patch_identity(monkeypatch):
    monkeypatch.setattr(
        account_manager, "_resolve_client_address", lambda _c: "dydx1test"
    )
    monkeypatch.setattr(account_manager, "_resolve_subaccount_number", lambda: 0)


def test_get_order_fills_finds_fills_beyond_the_first_page(monkeypatch):
    _patch_identity(monkeypatch)
    fake = _FakeIndexerFills(_fills(250, target_positions=set(range(150, 160))))

    result = asyncio.run(
        account_manager.get_order_fills(_client(fake), "target", limit=100, max_pages=5)
    )

    assert sorted(fill["id"] for fill in result) == sorted(
        f"fill-{index}" for index in range(150, 160)
    )
    # Every request moves strictly backwards in time.
    requested = [cursor for cursor in fake.cursors if cursor is not None]
    assert requested == sorted(requested, reverse=True)
    assert len(set(requested)) == len(requested)


def test_get_order_fills_never_returns_duplicates_across_page_boundaries(monkeypatch):
    _patch_identity(monkeypatch)
    fake = _FakeIndexerFills(_fills(250, target_positions={99, 100, 101}))

    result = asyncio.run(
        account_manager.get_order_fills(_client(fake), "target", limit=100, max_pages=5)
    )

    assert [fill["id"] for fill in result] == ["fill-99", "fill-100", "fill-101"]


def test_get_order_fills_stops_when_the_cursor_cannot_advance(monkeypatch):
    _patch_identity(monkeypatch)
    fake = _FakeIndexerFills(_fills(300, target_positions={5}, same_timestamp=True))

    result = asyncio.run(
        account_manager.get_order_fills(_client(fake), "target", limit=100, max_pages=5)
    )

    assert [fill["id"] for fill in result] == ["fill-5"]
    # One page, one identical follow-up that yields nothing new, then stop.
    assert len(fake.cursors) == 2


def test_get_order_fills_respects_max_pages(monkeypatch):
    _patch_identity(monkeypatch)
    fake = _FakeIndexerFills(_fills(1000, target_positions={950}))

    result = asyncio.run(
        account_manager.get_order_fills(_client(fake), "target", limit=100, max_pages=3)
    )

    assert result == []
    assert len(fake.cursors) == 3
