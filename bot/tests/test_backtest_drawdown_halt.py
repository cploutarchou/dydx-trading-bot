"""The strategy's drawdown limit halts new backtest entries, as live."""

from src.infrastructure.use_cases.service_backtest import BacktestService


def _trade(trade_id, entry, exit_, pnl):
    return {
        "trade_id": trade_id,
        "entry_timestamp": f"2026-09-{entry:02d}T00:00:00Z",
        "exit_timestamp": f"2026-09-{exit_:02d}T00:00:00Z",
        "pnl_usd": pnl,
        "win": pnl > 0,
    }


def test_no_limit_keeps_every_trade():
    trades = [_trade("a", 1, 2, -50.0), _trade("b", 3, 4, 5.0)]

    kept, halt = BacktestService._apply_drawdown_halt(trades, 100.0, 0.0)

    assert kept == trades
    assert halt is None


def test_entries_after_the_limit_are_skipped_but_open_positions_close():
    trades = [
        _trade("open-before", 1, 9, 2.0),  # opened before the halt: kept
        _trade("loser", 1, 2, -15.0),  # 15% below the 100 peak on day 2
        _trade("after", 3, 4, 50.0),  # would open after the halt: skipped
        _trade("later", 5, 6, 1.0),  # skipped
    ]

    kept, halt = BacktestService._apply_drawdown_halt(trades, 100.0, 10.0)

    assert [t["trade_id"] for t in kept] == ["open-before", "loser"]
    assert halt == {
        "limit_pct": 10.0,
        "reached": True,
        "reached_at": "2026-09-02T00:00:00Z",
        "equity_at_halt": 85.0,
        "trades_skipped": 2,
    }


def test_limit_measured_from_the_running_peak():
    trades = [
        _trade("up", 1, 2, 100.0),  # equity 200, new peak
        _trade("down", 3, 4, -30.0),  # 170: 15% below 200
        _trade("next", 5, 6, 1.0),
    ]

    kept, halt = BacktestService._apply_drawdown_halt(trades, 100.0, 10.0)

    assert [t["trade_id"] for t in kept] == ["up", "down"]
    assert halt["reached_at"] == "2026-09-04T00:00:00Z"


def test_limit_not_reached_keeps_all_and_says_so():
    trades = [_trade("a", 1, 2, -5.0), _trade("b", 3, 4, 3.0)]

    kept, halt = BacktestService._apply_drawdown_halt(trades, 100.0, 10.0)

    assert kept == trades
    assert halt["reached"] is False
    assert halt["trades_skipped"] == 0


def test_limit_reached_after_the_last_entry_skips_nothing():
    trades = [_trade("a", 1, 5, -40.0)]

    kept, halt = BacktestService._apply_drawdown_halt(trades, 100.0, 10.0)

    assert kept == trades
    assert halt["reached"] is True
    assert halt["trades_skipped"] == 0


def test_peak_open_exposure_flags_size_beyond_balance():
    trades = [
        _trade("a", 1, 5, 1.0),
        _trade("b", 2, 6, 1.0),
        _trade("c", 3, 4, 1.0),
        _trade("d", 5, 7, 1.0),  # opens as "a" closes: exits count first
    ]

    exposure = BacktestService._peak_open_exposure(trades, 10.0, 25.0)

    assert exposure == {
        "peak_open_positions": 3,
        "peak_open_notional_usd": 30.0,
        "initial_balance": 25.0,
        "exceeds_balance": True,
    }
    assert (
        BacktestService._peak_open_exposure(trades, 10.0, 100.0)["exceeds_balance"]
        is False
    )
