"""Tests for NATS consumer correlation ID propagation."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.asyncio
async def test_handle_extracts_correlation_id():
    """Test that handle method extracts correlation_id from context."""
    from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler
    
    handler = BacktestCommandHandler()
    
    # Mock the _parse_payload to return a valid payload
    handler._parse_payload = MagicMock(return_value=MagicMock(
        command_id="cmd-123",
        idempotency_key="key-123",
        run_id="run-123",
        correlation_id=None
    ))
    handler._is_duplicate = AsyncMock(return_value=False)
    handler._process_backtest_command = AsyncMock()
    
    message = {"command_id": "cmd-123"}
    context = {
        "correlation_id": "test-correlation-456",
        "message_id": "msg-123",
        "consumer_name": "test-consumer"
    }
    
    result = await handler.handle(message, context)
    
    # The payload should have correlation_id set
    assert handler._parse_payload.call_args[0][0] == message
    assert handler._parse_payload.call_args[0][1] == context


@pytest.mark.asyncio
async def test_handle_sets_correlation_id_on_payload():
    """Test that handle sets correlation_id on parsed payload."""
    from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler, BacktestCommandPayload
    
    handler = BacktestCommandHandler()
    
    # Track the payload that was passed to _is_duplicate
    duplicate_check_payload = None
    
    async def mock_is_duplicate(idemp_key, cmd_id):
        nonlocal duplicate_check_payload
        duplicate_check_payload = handler._parse_payload_last_payload
        return False
    
    handler._parse_payload = MagicMock(return_value=BacktestCommandPayload(
        command_id="cmd-123",
        run_id="run-123",
        command_type="backtest",
        owner_type="backtest",
        owner_id="run-123",
        idempotency_key="key-123",
        correlation_id=None
    ))
    handler._is_duplicate = mock_is_duplicate
    handler._process_backtest_command = AsyncMock()
    handler._update_task_command_status = AsyncMock()
    
    message = {"command_id": "cmd-123"}
    context = {
        "correlation_id": "test-correlation-789",
        "message_id": "msg-123",
        "consumer_name": "test-consumer"
    }
    
    await handler.handle(message, context)
    
    # The payload passed to _is_duplicate should have correlation_id
    assert duplicate_check_payload is not None
    assert duplicate_check_payload.correlation_id == "test-correlation-789"


@pytest.mark.asyncio
async def test_process_backtest_command_logs_correlation_id():
    """Test that _process_backtest_command logs with correlation_id."""
    from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler, BacktestCommandPayload
    from unittest.mock import patch
    
    handler = BacktestCommandHandler()
    
    payload = BacktestCommandPayload(
        command_id="cmd-123",
        run_id="run-123",
        command_type="backtest",
        owner_type="backtest",
        owner_id="run-123",
        idempotency_key="key-123",
        correlation_id="test-correlation-123"
    )
    
    context = {"consumer_name": "test-consumer"}
    
    # Mock all the methods that would be called
    handler._update_task_command_status = AsyncMock()
    handler._ensure_task_run = AsyncMock(return_value="task-run-123")
    handler._create_task_attempt = AsyncMock(return_value="attempt-123")
    handler._update_task_run_status = AsyncMock()
    handler._update_task_attempt_outcome = AsyncMock()
    handler._execute_backtest = AsyncMock(return_value=True)
    
    # Mock logger to capture log calls
    with patch('src.infrastructure.workers.nats_backtest_consumer.logger') as mock_logger:
        result = await handler._process_backtest_command(payload, context)
    
    # Verify logger was called with correlation_id
    assert mock_logger.info.called
    assert mock_logger.debug.called
    
    # Check that correlation_id appears in log calls
    log_calls = [str(call) for call in mock_logger.info.call_args_list]
    assert any("test-correlation-123" in str(call) for call in mock_logger.info.call_args_list)


@pytest.mark.asyncio
async def test_handle_error_logs_correlation_id():
    """Test that handle method error path logs correlation_id."""
    from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler
    from unittest.mock import patch
    
    handler = BacktestCommandHandler()
    
    # Mock parse_payload to return None (invalid payload)
    handler._parse_payload = MagicMock(return_value=None)
    
    message = {}
    context = {
        "correlation_id": "test-correlation-error",
        "message_id": "msg-123",
        "consumer_name": "test-consumer"
    }
    
    with patch('src.infrastructure.workers.nats_backtest_consumer.logger') as mock_logger:
        result = await handler.handle(message, context)
    
    # Verify error was logged with correlation_id
    assert mock_logger.warning.called
    log_call = str(mock_logger.warning.call_args)
    assert "test-correlation-error" in log_call


@pytest.mark.asyncio
async def test_handle_duplicate_logs_correlation_id():
    """Test that duplicate detection logs correlation_id."""
    from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler, BacktestCommandPayload
    from unittest.mock import patch
    
    handler = BacktestCommandHandler()
    
    payload = BacktestCommandPayload(
        command_id="cmd-123",
        run_id="run-123",
        command_type="backtest",
        owner_type="backtest",
        owner_id="run-123",
        idempotency_key="key-123",
        correlation_id="test-correlation-dup"
    )
    
    # Mock to return True (is duplicate)
    handler._parse_payload = MagicMock(return_value=payload)
    handler._is_duplicate = AsyncMock(return_value=True)
    
    message = {"command_id": "cmd-123"}
    context = {
        "correlation_id": "test-correlation-dup",
        "message_id": "msg-123",
        "consumer_name": "test-consumer"
    }
    
    with patch('src.infrastructure.workers.nats_backtest_consumer.logger') as mock_logger:
        result = await handler.handle(message, context)
    
    # Verify info was logged with correlation_id
    assert mock_logger.info.called
    log_call = str(mock_logger.info.call_args)
    assert "test-correlation-dup" in log_call
    assert "Duplicate" in log_call


def test_backtest_command_payload_has_correlation_id():
    """Test that BacktestCommandPayload has correlation_id field."""
    from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandPayload
    from dataclasses import fields
    
    payload_fields = {f.name for f in fields(BacktestCommandPayload)}
    assert "correlation_id" in payload_fields


def test_backtest_command_payload_default_correlation_id():
    """Test that BacktestCommandPayload has None default for correlation_id."""
    from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandPayload
    
    payload = BacktestCommandPayload(
        command_id="cmd-123",
        run_id="run-123",
        command_type="backtest",
        owner_type="backtest",
        owner_id="run-123",
        idempotency_key="key-123"
    )
    
    assert payload.correlation_id is None


def test_backtest_command_payload_with_correlation_id():
    """Test that BacktestCommandPayload can have correlation_id set."""
    from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandPayload
    
    payload = BacktestCommandPayload(
        command_id="cmd-123",
        run_id="run-123",
        command_type="backtest",
        owner_type="backtest",
        owner_id="run-123",
        idempotency_key="key-123",
        correlation_id="test-correlation"
    )
    
    assert payload.correlation_id == "test-correlation"
