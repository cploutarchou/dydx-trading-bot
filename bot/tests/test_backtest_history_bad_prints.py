"""Bad-print guard for backtest candle history."""

from src.infrastructure.use_cases import backtest_history as history


def _series(prices):
    return {f"2026-09-01T{hour:02d}:00:00Z": price for hour, price in enumerate(prices)}


def test_single_bar_spike_is_dropped():
    # Shape seen on testnet SOL-USD: one close ~100x the market.
    prices = [112.0, 113.0, 112.5, 11094.4, 113.2, 112.8, 113.5]
    clean, dropped = history._drop_bad_prints(_series(prices))

    assert dropped == 1
    assert 11094.4 not in clean.values()
    assert len(clean) == len(prices) - 1


def test_single_bar_crash_print_is_dropped():
    prices = [100.0, 101.0, 99.5, 0.5, 100.5, 100.2]
    clean, dropped = history._drop_bad_prints(_series(prices))

    assert dropped == 1
    assert 0.5 not in clean.values()


def test_sustained_move_is_kept():
    # A real repricing persists across bars, so the neighbour median follows it.
    prices = [1.0, 1.0, 1.0, 1.0, 4.0, 4.1, 4.2, 4.0, 4.3, 4.2, 4.1]
    clean, dropped = history._drop_bad_prints(_series(prices))

    assert dropped == 0
    assert list(clean.values()) == prices


def test_non_positive_prices_are_dropped():
    clean, dropped = history._drop_bad_prints(_series([10.0, 0.0, -1.0, 10.1]))

    assert dropped == 2
    assert list(clean.values()) == [10.0, 10.1]


def test_summary_reports_dropped_prints():
    summary = history._history_fetch_summary(
        {"SOL-USD": {"windows": 3, "bad_prints_dropped": 2}, "BTC-USD": {"windows": 3}}
    )

    assert summary["total_bad_prints_dropped"] == 2
    assert summary["markets"]["SOL-USD"]["bad_prints_dropped"] == 2
    assert summary["markets"]["BTC-USD"]["bad_prints_dropped"] == 0
