"""Tests for NATS worker metrics producer."""

from unittest.mock import MagicMock, patch

import pytest


def test_worker_id():
    """Test that worker_id returns expected format."""
    from src.infrastructure.workers.nats_worker_metrics import _worker_id

    wid = _worker_id()
    assert wid is not None
    assert "-" in wid
    assert "nats" in wid


def test_start_nats_command():
    """Test start_nats_command records start time."""
    from src.infrastructure.workers.nats_worker_metrics import (
        start_nats_command,
        _command_start_times,
    )

    # Clear any existing state
    _command_start_times.clear()

    correlation_id = "test-correlation-123"
    start_nats_command(correlation_id)

    assert correlation_id in _command_start_times
    assert _command_start_times[correlation_id] > 0


def test_start_nats_command_with_none():
    """Test start_nats_command handles None correlation_id."""
    from src.infrastructure.workers.nats_worker_metrics import (
        start_nats_command,
        _command_start_times,
    )

    _command_start_times.clear()

    start_nats_command(None)
    start_nats_command("")

    # Should not add empty/None keys
    assert None not in _command_start_times
    assert "" not in _command_start_times


@patch("src.infrastructure.workers.nats_worker_metrics._resolve_writer")
def test_complete_nats_command(mock_resolve_writer):
    """Test complete_nats_command records metrics."""
    from src.infrastructure.workers.nats_worker_metrics import (
        start_nats_command,
        complete_nats_command,
        _command_start_times,
    )

    _command_start_times.clear()

    correlation_id = "test-correlation-456"
    command_id = "cmd-123"
    run_id = "run-456"

    start_nats_command(correlation_id)

    mock_writer = MagicMock()
    mock_resolve_writer.return_value = mock_writer

    complete_nats_command(
        correlation_id=correlation_id,
        command_id=command_id,
        run_id=run_id,
        state="completed",
        retry_count=0,
        writer=mock_writer,
    )

    # Verify writer was called
    assert mock_writer.record_task_metrics.called
    call_args = mock_writer.record_task_metrics.call_args
    assert call_args[1]["task_id"] == command_id
    assert call_args[1]["task_name"] == f"backtest-execution-{run_id}"
    assert call_args[1]["success"] is True
    assert call_args[1]["worker_type"] == "nats"

    # Verify start time was removed
    assert correlation_id not in _command_start_times


@patch("src.infrastructure.workers.nats_worker_metrics._resolve_writer")
def test_complete_nats_command_without_start(mock_resolve_writer):
    """Test complete_nats_command handles missing start time gracefully."""
    from src.infrastructure.workers.nats_worker_metrics import (
        complete_nats_command,
        _command_start_times,
    )

    _command_start_times.clear()

    mock_writer = MagicMock()
    mock_resolve_writer.return_value = mock_writer

    # Call complete without start - should not crash
    complete_nats_command(
        correlation_id="unknown-correlation",
        command_id="cmd-123",
        run_id="run-456",
        state="completed",
        retry_count=0,
        writer=mock_writer,
    )

    # Writer should not be called if start time not found
    assert not mock_writer.record_task_metrics.called


@patch("src.infrastructure.workers.nats_worker_metrics._resolve_writer")
def test_complete_nats_command_calls_resolve_writer_by_default(mock_resolve_writer):
    """Test that complete_nats_command calls _resolve_writer if writer not provided."""
    from src.infrastructure.workers.nats_worker_metrics import (
        start_nats_command,
        complete_nats_command,
        _command_start_times,
    )

    _command_start_times.clear()

    mock_writer = MagicMock()
    mock_resolve_writer.return_value = mock_writer

    correlation_id = "test-correlation-789"
    start_nats_command(correlation_id)

    complete_nats_command(
        correlation_id=correlation_id,
        command_id="cmd-123",
        run_id="run-789",
        state="completed",
        retry_count=1,
        # Note: writer not provided, should use _resolve_writer
    )

    assert mock_resolve_writer.called
    assert mock_writer.record_task_metrics.called


@patch("src.infrastructure.workers.nats_worker_metrics._resolve_writer")
def test_fail_nats_command(mock_resolve_writer):
    """Test fail_nats_command records failure metrics."""
    from src.infrastructure.workers.nats_worker_metrics import (
        start_nats_command,
        fail_nats_command,
        _command_start_times,
    )

    _command_start_times.clear()

    correlation_id = "test-correlation-fail"
    start_nats_command(correlation_id)

    mock_writer = MagicMock()
    mock_resolve_writer.return_value = mock_writer

    fail_nats_command(
        correlation_id=correlation_id,
        command_id="cmd-fail",
        run_id="run-fail",
        error="Test error",
        retry_count=3,
        writer=mock_writer,
    )

    assert mock_writer.record_task_metrics.called
    call_args = mock_writer.record_task_metrics.call_args
    assert call_args[1]["success"] is False
    assert call_args[1]["retry_count"] == 3


@patch("src.infrastructure.workers.nats_worker_metrics._resolve_writer")
def test_metrics_with_none_writer(mock_resolve_writer):
    """Test that metrics functions handle None writer gracefully."""
    from src.infrastructure.workers.nats_worker_metrics import (
        record_nats_command_metric,
        start_nats_command,
        complete_nats_command,
        fail_nats_command,
        _command_start_times,
    )

    _command_start_times.clear()
    mock_resolve_writer.return_value = None

    # All these should not crash with None writer
    record_nats_command_metric(
        command_id="cmd",
        correlation_id="corr",
        run_id="run",
        state="completed",
        duration_ms=100.0,
        retry_count=0,
        writer=None,
    )

    start_nats_command("corr-1")
    complete_nats_command(
        correlation_id="corr-1",
        command_id="cmd",
        run_id="run",
        state="completed",
        retry_count=0,
        writer=None,
    )

    fail_nats_command(
        correlation_id="corr-2",
        command_id="cmd",
        run_id="run",
        error="err",
        retry_count=0,
        writer=None,
    )


@patch("src.infrastructure.workers.nats_worker_metrics._resolve_writer")
def test_get_nats_worker_metrics_writer(mock_resolve_writer):
    """Test get_nats_worker_metrics_writer returns writer."""
    from src.infrastructure.workers.nats_worker_metrics import (
        get_nats_worker_metrics_writer,
    )

    mock_writer = MagicMock()
    mock_resolve_writer.return_value = mock_writer

    writer = get_nats_worker_metrics_writer()
    assert writer == mock_writer
    mock_resolve_writer.assert_called_once()
