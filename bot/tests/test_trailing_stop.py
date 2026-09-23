"""Per-pair trailing stop in the live exit ladder.

The trailing stop is measured on the pair's unrealized P&L as a percentage of
its entry notional, the same number the stop loss and take profit use. It arms
once the pair's best P&L has reached the trail distance and closes the pair
when P&L falls that distance below its best level, so it never exits below
break-even and never tightens the stop loss.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from src.trading import bot_agents_state, position_manager


@pytest.fixture
def ladder(monkeypatch):
    monkeypatch.setattr(position_manager, "STOP_LOSS_PCT", 2.0)
    monkeypatch.setattr(position_manager, "TAKE_PROFIT_PCT", 5.0)
    monkeypatch.setattr(position_manager, "POSITION_TIMEOUT_HOURS", 72)
    monkeypatch.setattr(position_manager, "CLOSE_AT_ZSCORE_CROSS", False)
    monkeypatch.setattr(position_manager, "TRAILING_STOP_PCT", 1.0)


def _reason(pnl, peak):
    return position_manager._resolve_exit_reason(
        z_score_current=0.1,
        z_score_traded=1.0,
        unrealized_pnl_pct=pnl,
        position_age_hours=1.0,
        peak_unrealized_pnl_pct=peak,
    )


def test_it_fires_after_giving_back_the_trail_distance_from_the_best_level(ladder):
    assert _reason(0.6, 1.5) is None
    assert _reason(0.5, 1.5) == "trailing_stop"
    # The best level exactly at the distance arms it; its stop is break-even.
    assert _reason(0.0, 1.0) == "trailing_stop"


def test_it_is_not_armed_until_the_best_level_reaches_the_distance(ladder):
    # Up 0.9% at best, now down 1.9%: only the stop loss governs the downside.
    assert _reason(-1.9, 0.9) is None
    assert _reason(-2.0, 0.9) == "stop_loss"


def test_a_pair_that_never_went_positive_keeps_the_full_stop_loss(ladder):
    assert _reason(-1.5, -0.2) is None
    assert _reason(-2.1, -0.2) == "stop_loss"


def test_stop_loss_and_take_profit_keep_precedence(ladder):
    assert _reason(-2.5, 3.0) == "stop_loss"
    assert _reason(5.2, 7.0) == "take_profit"


def test_off_or_without_a_known_peak_it_never_fires(ladder, monkeypatch):
    assert _reason(0.0, None) is None
    monkeypatch.setattr(position_manager, "TRAILING_STOP_PCT", 0.0)
    assert _reason(0.0, 3.0) is None


def test_the_peak_ratchets_up_and_starts_from_the_first_observation():
    position = {"market_1": "BTC-USD", "market_2": "ETH-USD"}

    assert position_manager._fold_peak_unrealized_pnl(position, -0.3) == -0.3
    assert position_manager._fold_peak_unrealized_pnl(position, 1.2) == 1.2
    assert position_manager._fold_peak_unrealized_pnl(position, 0.4) == 1.2
    assert position[position_manager.PEAK_PNL_KEY] == 1.2
    assert position[position_manager.PEAK_PNL_AT_KEY]

    position[position_manager.PEAK_PNL_KEY] = "not-a-number"
    assert position_manager._fold_peak_unrealized_pnl(position, 0.2) == 0.2


# --------------------------------------------------------------- exit loop


def _tracked_position(**overrides):
    opened_at = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    position = {
        "market_1": "BTC-USD",
        "market_2": "ETH-USD",
        "order_id_m1": "m1-entry",
        "order_id_m2": "m2-entry",
        "order_m1_size": "0.1",
        "order_m2_size": "1.0",
        "order_m1_side": "BUY",
        "order_m2_side": "SELL",
        "order_m1_price": "100.0",
        "order_m2_price": "100.0",
        "order_time_m1": opened_at,
        "order_time_m2": opened_at,
        "z_score": -1.5,
        "hedge_ratio": 1.0,
        "pair_status": "LIVE",
    }
    position.update(overrides)
    return position


def _eth_price_for_pnl_pct(pnl_pct):
    """ETH close for the tracked pair's P&L %, with BTC at its 100.0 entry.

    Entry notional is 0.1 x 100 + 1.0 x 100 = 110; the short 1.0 ETH leg
    carries all the P&L while BTC stays at its entry price.
    """
    return 100.0 - pnl_pct * 110.0 / 100.0


class _Exchange:
    """Tracked pair open on the exchange until both legs were closed."""

    def __init__(self, monkeypatch, tmp_path, positions):
        self.eth_price = 100.0
        self.close_orders = []
        self.errors = []
        self.closed_messages = []
        self.path = tmp_path / "bot_agents.json"
        self.path.write_text(json.dumps(positions), encoding="utf-8")

        exchange = self

        class Messenger:
            def send_trade_closed_message(self, trade_info, reason):
                exchange.closed_messages.append((trade_info, reason))

            def send_error_message(self, *args, **kwargs):
                exchange.errors.append((args, kwargs))

        async def get_open_positions(_client):
            closed = {order["market"] for order in self.close_orders}
            return {
                market: {"market": market, "side": side, "sumOpen": size}
                for market, side, size in (
                    ("BTC-USD", "LONG", "0.1"),
                    ("ETH-USD", "SHORT", "1.0"),
                )
                if market not in closed
            }

        async def get_order(_client, order_id):
            return {
                "m1-entry": {"ticker": "BTC-USD", "size": "0.1", "side": "BUY"},
                "m2-entry": {"ticker": "ETH-USD", "size": "1.0", "side": "SELL"},
            }[order_id]

        async def get_candles_recent(_client, market):
            price = 100.0 if market == "BTC-USD" else self.eth_price
            return pd.Series([price, price, price])

        async def get_markets(_client):
            return {
                "markets": {
                    "BTC-USD": {"tickSize": "0.1"},
                    "ETH-USD": {"tickSize": "0.01"},
                }
            }

        async def place_market_order(_client, market, side, size, price, reduce_only):
            self.close_orders.append(
                {"market": market, "side": side, "size": size, "price": price}
            )
            return {"id": f"close-{market}"}, f"close-{market}"

        async def get_order_fills(*_args, **_kwargs):
            return []

        async def no_sleep(_seconds):
            return None

        monkeypatch.setattr(bot_agents_state, "BOT_AGENTS_PATH", self.path)
        monkeypatch.setattr(position_manager, "BOT_AGENTS_PATH", self.path)
        monkeypatch.setattr(position_manager, "TelegramMessenger", Messenger)
        monkeypatch.setattr(position_manager, "get_open_positions", get_open_positions)
        monkeypatch.setattr(position_manager, "get_order", get_order)
        monkeypatch.setattr(position_manager, "get_candles_recent", get_candles_recent)
        monkeypatch.setattr(position_manager, "get_markets", get_markets)
        monkeypatch.setattr(position_manager, "place_market_order", place_market_order)
        monkeypatch.setattr(position_manager, "get_order_fills", get_order_fills)
        monkeypatch.setattr(
            position_manager, "persist_live_trade_closed", lambda *a, **k: "trade-1"
        )
        monkeypatch.setattr(position_manager.asyncio, "sleep", no_sleep)
        monkeypatch.setenv("BOT_EXIT_CONFIRM_MAX_ATTEMPTS", "2")
        monkeypatch.setenv("BOT_EXIT_CONFIRM_DELAY_SECONDS", "0.1")

    def cycle(self, pnl_pct):
        self.eth_price = _eth_price_for_pnl_pct(pnl_pct)
        asyncio.run(position_manager.manage_trade_exits(object()))

    def tracked(self):
        return json.loads(self.path.read_text(encoding="utf-8"))


def test_the_exit_loop_keeps_the_peak_and_closes_on_the_give_back(
    ladder, monkeypatch, tmp_path
):
    exchange = _Exchange(monkeypatch, tmp_path, [_tracked_position()])

    exchange.cycle(1.5)
    assert exchange.close_orders == []
    [position] = exchange.tracked()
    assert position[position_manager.PEAK_PNL_KEY] == pytest.approx(1.5)

    exchange.cycle(0.8)
    assert exchange.close_orders == []
    assert exchange.tracked()[0][position_manager.PEAK_PNL_KEY] == pytest.approx(1.5)

    exchange.cycle(0.4)
    assert [order["market"] for order in exchange.close_orders] == [
        "BTC-USD",
        "ETH-USD",
    ]
    # A trailing stop is a stop: it gets the wide accept band (15%), not the
    # 5% band of discretionary exits, so it fills in a fast market.
    assert exchange.close_orders[0]["price"] == "85.0"
    assert exchange.closed_messages[0][1] == "Trailing stop"
    assert exchange.tracked() == []


def test_the_peak_survives_a_restart(ladder, monkeypatch, tmp_path):
    # Stored by an earlier process, before a restart or a replaced pod.
    exchange = _Exchange(
        monkeypatch,
        tmp_path,
        [_tracked_position(**{position_manager.PEAK_PNL_KEY: 2.4})],
    )

    exchange.cycle(1.3)

    assert exchange.closed_messages[0][1] == "Trailing stop"


def test_an_unknown_pnl_never_closes_on_the_trailing_stop(
    ladder, monkeypatch, tmp_path
):
    # The fallback P&L of 0.0 would read as a 2-point give-back from this
    # armed peak; the pair must stay open and the peak untouched.
    exchange = _Exchange(
        monkeypatch,
        tmp_path,
        [
            _tracked_position(
                order_m1_price="unknown", **{position_manager.PEAK_PNL_KEY: 2.0}
            )
        ],
    )

    exchange.cycle(0.0)

    assert exchange.close_orders == []
    [position] = exchange.tracked()
    assert position[position_manager.PEAK_PNL_KEY] == 2.0
    assert position["last_exit_warning"]


def test_with_the_trailing_stop_off_no_peak_is_tracked(ladder, monkeypatch, tmp_path):
    monkeypatch.setattr(position_manager, "TRAILING_STOP_PCT", 0.0)
    exchange = _Exchange(monkeypatch, tmp_path, [_tracked_position()])

    exchange.cycle(1.5)
    exchange.cycle(0.1)

    assert exchange.close_orders == []
    assert position_manager.PEAK_PNL_KEY not in exchange.tracked()[0]
