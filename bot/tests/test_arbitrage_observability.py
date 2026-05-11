from src.trading.arbitrage_observability import (
    increment_metric,
    record_rejection,
    reset_metrics,
    snapshot_metrics,
)


def test_record_rejection_increments_total_and_reason_bucket():
    reset_metrics()

    record_rejection("insufficient collateral")
    record_rejection("insufficient collateral")

    snap = snapshot_metrics()
    assert snap["counters"]["opportunities_rejected_total"] == 2.0
    assert snap["rejection_reasons"]["insufficient_collateral"] == 2.0


def test_snapshot_includes_sorted_reason_buckets_and_reset_clears_them():
    reset_metrics()

    increment_metric("opportunities_detected_total")
    record_rejection("market_already_open")
    record_rejection("min_order_size")

    snap = snapshot_metrics()
    assert list(snap["rejection_reasons"].keys()) == ["market_already_open", "min_order_size"]

    reset_metrics()
    cleared = snapshot_metrics()
    assert cleared["counters"]["opportunities_detected_total"] == 0.0
    assert cleared["counters"]["opportunities_rejected_total"] == 0.0
    assert cleared["rejection_reasons"] == {}
