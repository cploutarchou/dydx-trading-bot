"""Unit tests for DataFrame memory-management utilities."""

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.shared import dataframe_utils as dfu  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_registry():
    """Isolate the module-global registry/tracking flag between tests."""
    dfu._frame_registry.clear()
    dfu._tracking_enabled = True
    yield
    dfu._frame_registry.clear()
    dfu._tracking_enabled = True


def _frame(rows: int = 10) -> pd.DataFrame:
    return pd.DataFrame({"a": np.arange(rows, dtype=np.int64)})


# ---------------------------------------------------------------- registry


def test_register_and_unregister_dataframe_roundtrip():
    frame = _frame(100)
    frame_id = dfu.register_dataframe(frame, "test_frame", {"purpose": "unit"})

    assert frame_id
    entry = dfu._frame_registry[frame_id]
    assert entry["name"] == "test_frame"
    assert entry["rows"] == 100
    assert entry["columns"] == 1
    assert entry["metadata"] == {"purpose": "unit"}
    assert entry["size_bytes"] == dfu.get_dataframe_memory_usage(frame)
    assert entry["df"] is frame

    assert dfu.unregister_dataframe(frame_id) is True
    assert frame_id not in dfu._frame_registry
    # Second unregister of the same id reports False
    assert dfu.unregister_dataframe(frame_id) is False


def test_register_dataframe_returns_empty_id_when_tracking_disabled():
    dfu.enable_dataframe_tracking(False)
    try:
        assert dfu.register_dataframe(_frame(), "x") == ""
        assert dfu.unregister_dataframe("anything") is False
    finally:
        dfu.enable_dataframe_tracking(True)


def test_register_dataframe_survives_bad_input():
    class Boom:
        def __len__(self):
            raise RuntimeError("no length")

        def memory_usage(self):
            raise RuntimeError("no memory")

    assert dfu.register_dataframe(Boom(), "boom") == ""


def test_unregister_dataframe_handles_empty_id():
    assert dfu.unregister_dataframe("") is False


# ---------------------------------------------------------- memory usage


def test_get_dataframe_memory_usage_sources():
    frame = _frame()
    assert dfu.get_dataframe_memory_usage(frame) == frame.memory_usage(deep=True).sum()
    assert dfu.get_dataframe_memory_usage(np.zeros(10)) == 10 * 8
    # Bare objects fall back to __sizeof__
    assert dfu.get_dataframe_memory_usage(object()) > 0
    # A broken memory_usage implementation degrades to 0, never raises
    broken = type("Bad", (), {"memory_usage": lambda self: 1 / 0})()
    assert dfu.get_dataframe_memory_usage(broken) == 0


# ---------------------------------------------------------------- cleanup


def test_cleanup_dataframe():
    frame = _frame()
    assert dfu.cleanup_dataframe(frame) is True
    assert frame.empty  # columns dropped in place

    assert dfu.cleanup_dataframe(None) is False


def test_cleanup_old_entries_removes_expired_registrations():
    frame_id = dfu.register_dataframe(_frame(), "old_frame")

    # Backdate two entries beyond the 30-minute cutoff; the next registration
    # (with the max-tracked threshold lowered to force a sweep) removes them.
    dfu._frame_registry[frame_id]["created_at"] = datetime.now() - timedelta(minutes=31)
    dfu._frame_registry["__expired__"] = {
        "created_at": datetime.now() - timedelta(minutes=31),
        "df": _frame(),
    }

    original_max = dfu._max_tracked_frames
    dfu._max_tracked_frames = 0
    try:
        dfu.register_dataframe(_frame(), "new_frame")
    finally:
        dfu._max_tracked_frames = original_max

    assert frame_id not in dfu._frame_registry
    assert "__expired__" not in dfu._frame_registry
    assert len(dfu._frame_registry) == 1  # only "new_frame" remains


def test_managed_dataframe_cleans_up_on_success_and_error():
    frame = _frame()
    with dfu.managed_dataframe(frame, "ctx") as df:
        assert df is frame
        assert len(dfu._frame_registry) == 1
    assert len(dfu._frame_registry) == 0

    with pytest.raises(ValueError, match="boom"):
        with dfu.managed_dataframe(_frame(), "ctx"):
            raise ValueError("boom")
    assert len(dfu._frame_registry) == 0


# ------------------------------------------------------------- summaries


def test_get_memory_summary_empty_and_populated():
    empty = dfu.get_memory_summary()
    assert empty["tracked_dataframes"] == 0
    assert empty["total_memory_mb"] == 0.0

    big = _frame(1000)
    small = _frame(10)
    dfu.register_dataframe(big, "big")
    dfu.register_dataframe(small, "small")

    summary = dfu.get_memory_summary()
    assert summary["tracked_dataframes"] == 2
    assert summary["largest_frame_name"] == "big"
    assert summary["total_memory_mb"] == pytest.approx(
        (dfu.get_dataframe_memory_usage(big) + dfu.get_dataframe_memory_usage(small))
        / (1024 * 1024)
    )
    assert summary["oldest_frame_minutes"] >= 0.0

    stats = dfu.get_dataframe_cleanup_stats()
    assert stats["tracking_enabled"] is True
    assert stats["tracked_count"] == 2
    assert stats["registry_size_kb"] > 0


def test_force_cleanup_all_clears_registry():
    dfu.register_dataframe(_frame(), "a")
    dfu.register_dataframe(_frame(), "b")

    assert dfu.force_cleanup_all() == 2
    assert dfu._frame_registry == {}


# ----------------------------------------------------------- optimization


def test_optimize_dataframe_memory_downcasts_and_categorizes():
    # String columns must be built with an explicit object dtype: pandas 3
    # infers the dedicated `str` dtype by default, which skips the
    # object->category branch entirely.
    frame = pd.DataFrame(
        {
            "ints": np.array([1, 2, 3], dtype="int64"),
            "floats": np.array([1.5, 2.5, 3.5], dtype="float64"),
            "dupes": pd.Series(["x", "x", "x"], dtype="object"),
            "unique": pd.Series(["a", "b", "c"], dtype="object"),
        }
    )

    optimized = dfu.optimize_dataframe_memory(frame)

    assert optimized is not frame  # original untouched
    assert str(optimized["ints"].dtype) == "int32"
    assert str(optimized["floats"].dtype) == "float32"
    assert str(optimized["dupes"].dtype) == "category"
    assert str(optimized["unique"].dtype) == "object"
    assert dfu.get_dataframe_memory_usage(optimized) < dfu.get_dataframe_memory_usage(
        frame
    )


def test_optimize_dataframe_memory_passthrough_and_failure():
    assert dfu.optimize_dataframe_memory(None) is None
    assert dfu.optimize_dataframe_memory("not a frame") == "not a frame"

    # Has dtypes but no copy() -> warning path returns the input unchanged
    broken = type("Broken", (), {"dtypes": object()})()
    assert dfu.optimize_dataframe_memory(broken) is broken


# ----------------------------------------------------------- cache entries


def test_cleanup_cache_entries_removes_expired_and_stale_entries(monkeypatch):
    # The age math mixes time.monotonic() with dict-supplied timestamps; pin
    # monotonic to the epoch clock so datetime-based entries compare sanely.
    epoch_now = datetime.now(timezone.utc).timestamp()
    monkeypatch.setattr(dfu.time, "monotonic", lambda: epoch_now)

    cache = {
        "expired": {"expires": epoch_now - 7200, "data": _frame()},
        "stale_created": {
            "created_at": datetime.now(timezone.utc) - timedelta(hours=2)
        },
        "fresh": {"expires": epoch_now + 3600, "data": _frame()},
        "fresh_created": {"created_at": datetime.now(timezone.utc)},
        "no_marker": {"value": 1},
    }

    dfu.cleanup_cache_entries(cache, max_size=10, max_age_minutes=60)

    assert set(cache) == {"fresh", "fresh_created", "no_marker"}


def test_cleanup_cache_entries_evicts_oldest_when_over_size():
    now = time.monotonic()
    cache = {
        "a": {"expires": now + 100},
        "b": {"expires": now + 50},  # smallest expires -> evicted first
        "c": {"expires": now + 200},
    }

    dfu.cleanup_cache_entries(cache, max_size=2, max_age_minutes=60)

    assert set(cache) == {"a", "c"}


def test_cleanup_cache_entries_never_raises():
    # Unsortable/malformed entries must fall into the warning path, not crash
    dfu.cleanup_cache_entries({"bad": {"expires": "not-a-number"}}, max_size=0)
