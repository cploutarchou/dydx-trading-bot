"""Tests for NATS JetStream consumer implementation (Phase 4).

These tests cover:
- NATS consumer service creation and configuration
- Stream and consumer provisioning
- Message handling and idempotency
- Ack/NAK/dead-letter handling
- Fail-closed behavior when NATS is disabled
- Duplicate detection via PostgreSQL task tables
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest


class TestNATSConsumerService(unittest.IsolatedAsyncioTestCase):
    """Test NATS consumer service functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock environment variables for testing
        self.original_nats_enabled = os.environ.get("NATS_ENABLED")
        self.original_command_bus_enabled = os.environ.get("BOT_COMMAND_BUS_ENABLED")
        self.original_nats_url = os.environ.get("NATS_URL")

        # Set NATS disabled by default for most tests
        os.environ["NATS_ENABLED"] = "false"
        os.environ["BOT_COMMAND_BUS_ENABLED"] = "false"
        os.environ.pop("NATS_URL", None)

    def tearDown(self):
        """Clean up test fixtures."""
        # Restore original environment variables
        if self.original_nats_enabled is not None:
            os.environ["NATS_ENABLED"] = self.original_nats_enabled
        else:
            os.environ.pop("NATS_ENABLED", None)

        if self.original_command_bus_enabled is not None:
            os.environ["BOT_COMMAND_BUS_ENABLED"] = self.original_command_bus_enabled
        else:
            os.environ.pop("BOT_COMMAND_BUS_ENABLED", None)

        if self.original_nats_url is not None:
            os.environ["NATS_URL"] = self.original_nats_url
        else:
            os.environ.pop("NATS_URL", None)

    def test_service_creation_disabled(self):
        """Test service creation when NATS is disabled."""
        from src.infrastructure.event_bus_nats import NATSConsumerService

        service = NATSConsumerService(enabled=False)
        self.assertFalse(service.is_enabled())
        self.assertEqual(service.get_status().value, "disconnected")

    def test_service_creation_enabled(self):
        """Test service creation when NATS is enabled."""
        from src.infrastructure.event_bus_nats import NATSConsumerService

        with patch.dict(os.environ, {"NATS_ENABLED": "true"}):
            service = NATSConsumerService()
            self.assertTrue(service.is_enabled())

    def test_default_servers_from_env(self):
        """Test default server configuration from environment."""
        from src.infrastructure.event_bus_nats import NATSConsumerService

        with patch.dict(os.environ, {
            "NATS_ENABLED": "true",
            "NATS_URL": "nats://custom-host:4222"
        }):
            service = NATSConsumerService()
            self.assertIn("nats://custom-host:4222", service.servers)

    def test_multiple_servers_from_env(self):
        """Test multiple servers configuration from environment."""
        from src.infrastructure.event_bus_nats import NATSConsumerService

        with patch.dict(os.environ, {
            "NATS_ENABLED": "true",
            "NATS_SERVERS": "nats://server1:4222,nats://server2:4222,nats://server3:4222"
        }):
            service = NATSConsumerService()
            self.assertEqual(len(service.servers), 3)
            self.assertIn("nats://server1:4222", service.servers)
            self.assertIn("nats://server2:4222", service.servers)
            self.assertIn("nats://server3:4222", service.servers)

    def test_stream_configs_match_plan(self):
        """Test that stream configurations match nats-jetstream-plan.md."""
        from src.infrastructure.event_bus_nats import NATSConsumerService, StreamConfig

        service = NATSConsumerService(enabled=False)

        # Check BACKTEST_COMMANDS stream configuration
        backtest_config = service.STREAM_CONFIGS["BACKTEST_COMMANDS"]
        self.assertEqual(backtest_config.name, "BACKTEST_COMMANDS")
        self.assertEqual(backtest_config.subjects, ["backtest.command.>"])
        self.assertEqual(backtest_config.retention, "workqueue")
        self.assertEqual(backtest_config.storage, "file")
        self.assertEqual(backtest_config.replicas, 1)
        self.assertEqual(backtest_config.duplicates_window, 2 * 60 * 60)  # 2 hours

        # Check BOT_COMMANDS stream configuration
        bot_config = service.STREAM_CONFIGS["BOT_COMMANDS"]
        self.assertEqual(bot_config.name, "BOT_COMMANDS")
        self.assertEqual(bot_config.subjects, ["bot.command.>"])

        # Check DEAD_LETTER stream configuration
        dead_letter_config = service.STREAM_CONFIGS["DEAD_LETTER"]
        self.assertEqual(dead_letter_config.name, "DEAD_LETTER")
        self.assertEqual(dead_letter_config.subjects, ["deadletter.>"])
        self.assertEqual(dead_letter_config.max_age, 90 * 24 * 60 * 60)  # 90 days

    def test_consumer_configs_match_plan(self):
        """Test that consumer configurations match nats-jetstream-plan.md."""
        from src.infrastructure.event_bus_nats import NATSConsumerService, ConsumerConfig

        service = NATSConsumerService(enabled=False)

        # Check backtest-worker consumer configuration
        backtest_consumer = service.CONSUMER_CONFIGS["backtest-worker"]
        self.assertEqual(backtest_consumer.name, "backtest-worker")
        self.assertEqual(backtest_consumer.stream, "BACKTEST_COMMANDS")
        self.assertEqual(backtest_consumer.subject_filter, "backtest.command.start")
        self.assertEqual(backtest_consumer.queue_group, "backtest-workers")
        self.assertEqual(backtest_consumer.durable_name, "backtest-worker")
        self.assertEqual(backtest_consumer.ack_wait_seconds, 600)  # 10 minutes
        self.assertEqual(backtest_consumer.max_deliver, 5)

        # Check bot-worker consumer configuration
        bot_consumer = service.CONSUMER_CONFIGS["bot-worker"]
        self.assertEqual(bot_consumer.name, "bot-worker")
        self.assertEqual(bot_consumer.stream, "BOT_COMMANDS")
        self.assertEqual(bot_consumer.subject_filter, "bot.command.>")
        self.assertEqual(bot_consumer.queue_group, "bot-workers")
        self.assertEqual(bot_consumer.ack_wait_seconds, 300)  # 5 minutes

    @patch('src.infrastructure.event_bus_nats.nats')
    async def test_connect_disabled_service(self, mock_nats):
        """Test connection when service is disabled."""
        from src.infrastructure.event_bus_nats import NATSConsumerService

        service = NATSConsumerService(enabled=False)
        result = await service.connect()
        self.assertFalse(result)
        self.assertFalse(service.is_connected())

    @patch('src.infrastructure.event_bus_nats.nats')
    async def test_connect_failure(self, mock_nats):
        """Test connection failure handling."""
        from src.infrastructure.event_bus_nats import NATSConsumerService

        # Mock connection to raise an exception
        mock_client = MagicMock()
        mock_client.connect.side_effect = Exception("Connection failed")
        mock_nats.aio.client.Client.return_value = mock_client

        service = NATSConsumerService(enabled=True)
        result = await service.connect()
        self.assertFalse(result)
        self.assertEqual(service.get_status().value, "error")

    def test_handler_registration(self):
        """Test message handler registration."""
        from src.infrastructure.event_bus_nats import NATSConsumerService, MessageHandler, ProcessedResult, \
            MessageAction

        service = NATSConsumerService(enabled=False)

        # Create a mock handler
        mock_handler = MagicMock()
        mock_handler.handle = AsyncMock()

        # Register the handler
        service.register_handler("test-consumer", mock_handler)

        # Verify handler is registered
        self.assertIn("test-consumer", service._handlers)
        self.assertEqual(service._handlers["test-consumer"], mock_handler)

    def test_stream_name_resolution(self):
        """Test stream name resolution from subjects."""
        from src.infrastructure.event_bus_nats import NATSConsumerService

        service = NATSConsumerService(enabled=False)

        # Test BACKTEST_COMMANDS stream
        stream_name = service._get_stream_name("backtest.command.start")
        self.assertEqual(stream_name, "BACKTEST_COMMANDS")

        stream_name = service._get_stream_name("backtest.command.cancel")
        self.assertEqual(stream_name, "BACKTEST_COMMANDS")

        # Test BOT_COMMANDS stream
        stream_name = service._get_stream_name("bot.command.start")
        self.assertEqual(stream_name, "BOT_COMMANDS")

        # Test unknown subject
        stream_name = service._get_stream_name("unknown.subject")
        self.assertEqual(stream_name, "UNKNOWN")


class TestBacktestCommandHandler(unittest.IsolatedAsyncioTestCase):
    """Test backtest command handler functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock database session
        self.mock_session = MagicMock()
        self.mock_result = MagicMock()
        self.mock_row = MagicMock()

        # Configure mocks
        self.mock_row.__getitem__ = MagicMock(side_effect=lambda x: {
            0: "test-command-id",
            1: "completed"
        }[x])

        self.mock_result.fetchone.return_value = self.mock_row
        self.mock_session.execute.return_value = self.mock_result

    async def test_handler_creation(self):
        """Test handler creation."""
        from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler

        handler = BacktestCommandHandler()
        self.assertIsNotNone(handler)
        self.assertIsNotNone(handler._worker_id)
        self.assertEqual(handler._running_backtests, {})

    async def test_parse_valid_payload(self):
        """Test parsing of valid payload."""
        from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler, BacktestCommandPayload

        handler = BacktestCommandHandler()

        message = {
            "command_id": "cmd-123",
            "run_id": "run-456",
            "command_type": "backtest",
            "owner_type": "backtest",
            "owner_id": "run-456",
            "idempotency_key": "backtest-unique-key",
            "name": "test-backtest",
            "strategy_id": 42,
            "pairs": ["BTC-USD", "ETH-USD"],
            "source": "ui",
            "environment": "testnet"
        }

        context = {
            "message_id": "cmd-123",
            "idempotency_key": "backtest-unique-key",
            "consumer_name": "backtest-worker"
        }

        payload = handler._parse_payload(message, context)

        self.assertIsNotNone(payload)
        self.assertEqual(payload.command_id, "cmd-123")
        self.assertEqual(payload.run_id, "run-456")
        self.assertEqual(payload.idempotency_key, "backtest-unique-key")
        self.assertEqual(payload.strategy_id, 42)
        self.assertEqual(payload.pairs, ["BTC-USD", "ETH-USD"])

    async def test_parse_missing_required_fields(self):
        """Test parsing fails with missing required fields."""
        from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler

        handler = BacktestCommandHandler()

        # Missing command_id and idempotency_key
        message = {"name": "test"}
        context = {}

        payload = handler._parse_payload(message, context)
        self.assertIsNone(payload)

    async def test_parse_empty_payload(self):
        """Test parsing of empty payload."""
        from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler

        handler = BacktestCommandHandler()

        message = {}
        context = {}

        payload = handler._parse_payload(message, context)
        self.assertIsNone(payload)

    async def test_parse_uses_context_fallback(self):
        """Test parsing uses context values as fallback."""
        from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler

        handler = BacktestCommandHandler()

        message = {"name": "test"}
        context = {
            "message_id": "cmd-from-context",
            "idempotency_key": "key-from-context"
        }

        payload = handler._parse_payload(message, context)

        self.assertIsNotNone(payload)
        self.assertEqual(payload.command_id, "cmd-from-context")
        self.assertEqual(payload.idempotency_key, "key-from-context")

    @patch('src.infrastructure.workers.nats_backtest_consumer.db.get_session')
    async def test_duplicate_detection(self, mock_get_session):
        """Test duplicate detection using task_commands table."""
        from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler

        # Configure mock session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(side_effect=lambda x: {
            0: "cmd-123",  # command_id
            1: "completed"  # status
        }[x])
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result
        mock_get_session.return_value = mock_session

        handler = BacktestCommandHandler()

        # Test duplicate detection
        is_duplicate = await handler._is_duplicate("test-key", "cmd-123")
        self.assertTrue(is_duplicate)

    @patch('src.infrastructure.workers.nats_backtest_consumer.db.get_session')
    async def test_no_duplicate_when_not_found(self, mock_get_session):
        """Test no duplicate when command not found."""
        from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler

        # Configure mock session to return no rows
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result
        mock_get_session.return_value = mock_session

        handler = BacktestCommandHandler()

        # Test no duplicate
        is_duplicate = await handler._is_duplicate("new-key", "new-cmd")
        self.assertFalse(is_duplicate)


class TestGlobalFunctions(unittest.IsolatedAsyncioTestCase):
    """Test global consumer functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any existing global instances
        import src.infrastructure.event_bus_nats as event_bus_nats
        event_bus_nats._consumer_service = None

        import src.infrastructure.workers.nats_backtest_consumer as nats_backtest
        nats_backtest._backtest_command_handler = None

        # Mock NATS disabled
        os.environ["NATS_ENABLED"] = "false"
        os.environ["BOT_COMMAND_BUS_ENABLED"] = "false"

    def tearDown(self):
        """Clean up test fixtures."""
        # Clear global instances
        import src.infrastructure.event_bus_nats as event_bus_nats
        event_bus_nats._consumer_service = None

        import src.infrastructure.workers.nats_backtest_consumer as nats_backtest
        nats_backtest._backtest_command_handler = None

        # Clean up environment
        os.environ.pop("NATS_ENABLED", None)
        os.environ.pop("BOT_COMMAND_BUS_ENABLED", None)

    def test_get_consumer_service_initially_none(self):
        """Test global consumer service is initially None."""
        from src.infrastructure.event_bus_nats import get_nats_consumer_service

        service = get_nats_consumer_service()
        self.assertIsNone(service)

    def test_init_consumer_service(self):
        """Test global consumer service initialization."""
        from src.infrastructure.event_bus_nats import init_nats_consumer_service, get_nats_consumer_service

        service = init_nats_consumer_service(enabled=False)
        self.assertIsNotNone(service)

        # Verify it's the same instance
        retrieved_service = get_nats_consumer_service()
        self.assertIs(service, retrieved_service)

    @patch.dict(os.environ, {"NATS_ENABLED": "false"})
    async def test_init_nats_backtest_consumers_disabled(self):
        """Test backtest consumers initialization when NATS is disabled."""
        from src.infrastructure.workers.nats_backtest_consumer import init_nats_backtest_consumers

        handler = await init_nats_backtest_consumers()
        self.assertIsNone(handler)

    @patch('src.infrastructure.workers.nats_backtest_consumer.get_nats_consumer_service')
    @patch('src.infrastructure.workers.nats_backtest_consumer.get_backtest_command_handler')
    async def test_shutdown_nats_backtest_consumers(self, mock_handler, mock_service):
        """Test backtest consumers shutdown."""
        from src.infrastructure.workers.nats_backtest_consumer import shutdown_nats_backtest_consumers

        # Mock consumer service with async shutdown
        mock_consumer_service = MagicMock()
        mock_consumer_service.is_connected.return_value = True
        mock_consumer_service.shutdown = AsyncMock()  # Make shutdown awaitable
        mock_service.return_value = mock_consumer_service

        # Shutdown should not raise errors
        await shutdown_nats_backtest_consumers()
        mock_consumer_service.shutdown.assert_called_once()


class TestMessageProcessing(unittest.IsolatedAsyncioTestCase):
    """Test message processing functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.mock_result = MagicMock()
        self.mock_row = MagicMock()

        # Configure mocks for database operations
        self.mock_row.__getitem__ = MagicMock(side_effect=lambda x: {
            0: "test-command-id",
            1: "completed"
        }[x])

        self.mock_result.fetchone.return_value = self.mock_row
        self.mock_session.execute.return_value = self.mock_result
        self.mock_session.commit = MagicMock()
        self.mock_session.rollback = MagicMock()

    @patch('src.infrastructure.workers.nats_backtest_consumer.db.get_session')
    async def test_handle_duplicate_message(self, mock_get_session):
        """Test handling of duplicate message."""
        from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler, MessageAction
        from src.infrastructure.event_bus_nats import ProcessedResult

        # Configure mock for duplicate detection
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(side_effect=lambda x: {
            0: "cmd-123",
            1: "completed"
        }[x])
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result
        mock_get_session.return_value = mock_session

        handler = BacktestCommandHandler()

        message = {
            "command_id": "cmd-123",
            "idempotency_key": "test-key"
        }

        context = {
            "message_id": "cmd-123",
            "idempotency_key": "test-key",
            "consumer_name": "backtest-worker"
        }

        result = await handler.handle(message, context)

        self.assertEqual(result.action, MessageAction.ACK)
        self.assertEqual(result.idempotency_key, "test-key")

    @patch('src.infrastructure.workers.nats_backtest_consumer.db.get_session')
    async def test_handle_invalid_payload(self, mock_get_session):
        """Test handling of invalid payload."""
        from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler, MessageAction
        from src.infrastructure.event_bus_nats import ProcessedResult

        handler = BacktestCommandHandler()

        # Invalid payload (missing required fields)
        message = {}
        context = {"consumer_name": "backtest-worker"}

        result = await handler.handle(message, context)

        self.assertEqual(result.action, MessageAction.NAK)
        self.assertIn("Invalid or empty payload", result.error_message)

    @patch('src.infrastructure.workers.nats_backtest_consumer.db.get_session')
    async def test_task_run_creation(self, mock_get_session):
        """Test task run creation returns the DB-generated UUID via RETURNING."""
        from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler

        # Two executes happen in _ensure_task_run: SELECT (no existing run) then
        # INSERT ... RETURNING id (returns the generated id).
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.side_effect = [None, ["gen-run-uuid"]]
        mock_session.execute.return_value = mock_result
        mock_get_session.return_value = mock_session

        handler = BacktestCommandHandler()

        payload = BacktestCommandHandler._parse_payload(
            handler,
            {
                "command_id": "cmd-123",
                "idempotency_key": "test-key",
                "run_id": "run-456"
            },
            {"message_id": "cmd-123", "idempotency_key": "test-key"}
        )

        task_run_id = await handler._ensure_task_run(payload)

        # The id is now server-generated; the handler must surface that value.
        self.assertEqual("gen-run-uuid", task_run_id)
        # The INSERT must not reference the legacy requested_by_user_id column
        # (removed because task_runs has no such column per migration 000064).
        insert_call = mock_session.execute.call_args_list[1]
        self.assertNotIn("requested_by_user_id", str(insert_call))

    @patch('src.infrastructure.workers.backtest_event_emitter.publish_backtest_event', new_callable=AsyncMock)
    @patch('src.infrastructure.use_cases.service_backtest.BacktestService')
    @patch('src.infrastructure.workers.nats_backtest_consumer.db.get_session')
    async def test_execute_backtest_invokes_real_service_and_emits_events(
            self, mock_get_session, mock_service_cls, mock_emit,
    ):
        """_execute_backtest delegates to BacktestService.execute_existing_backtest
        (the real runtime, same path Celery uses) and emits started/completed events."""
        from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler

        mock_service = MagicMock()
        mock_service.execute_existing_backtest = AsyncMock()
        mock_service_cls.return_value = mock_service
        mock_get_session.return_value = MagicMock()

        handler = BacktestCommandHandler()
        # Avoid real DB writes for task-run status/progress updates.
        handler._update_task_run_status = AsyncMock()
        handler._update_task_run_progress = AsyncMock()

        payload = BacktestCommandHandler._parse_payload(
            handler,
            {"command_id": "cmd-1", "idempotency_key": "k-1", "run_id": "run-real-1"},
            {"message_id": "cmd-1", "idempotency_key": "k-1"},
        )

        ok = await handler._execute_backtest(payload, "task-run-1", "attempt-1")
        self.assertTrue(ok)

        # Real service invoked with the command's run_id.
        mock_service.execute_existing_backtest.assert_awaited_once()
        called_run_id = mock_service.execute_existing_backtest.await_args.args[0]
        self.assertEqual(called_run_id, "run-real-1")

        # Lifecycle events emitted (started + completed).
        emitted_statuses = [c.kwargs.get("status") for c in mock_emit.await_args_list]
        self.assertIn("started", emitted_statuses)
        self.assertIn("completed", emitted_statuses)

    @patch('src.infrastructure.workers.backtest_event_emitter.publish_backtest_event', new_callable=AsyncMock)
    @patch('src.infrastructure.use_cases.service_backtest.BacktestService')
    @patch('src.infrastructure.workers.nats_backtest_consumer.db.get_session')
    async def test_execute_backtest_failure_emits_failed_event(
            self, mock_get_session, mock_service_cls, mock_emit,
    ):
        """A raised backtest exception is caught and emits a failed event."""
        from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler

        mock_service = MagicMock()
        mock_service.execute_existing_backtest = AsyncMock(side_effect=RuntimeError("boom"))
        mock_service_cls.return_value = mock_service
        mock_get_session.return_value = MagicMock()

        handler = BacktestCommandHandler()
        handler._update_task_run_status = AsyncMock()
        handler._update_task_run_progress = AsyncMock()

        payload = BacktestCommandHandler._parse_payload(
            handler,
            {"command_id": "cmd-2", "idempotency_key": "k-2", "run_id": "run-real-2"},
            {"message_id": "cmd-2", "idempotency_key": "k-2"},
        )

        ok = await handler._execute_backtest(payload, "task-run-2", "attempt-2")
        self.assertFalse(ok)

        emitted_statuses = [c.kwargs.get("status") for c in mock_emit.await_args_list]
        self.assertIn("failed", emitted_statuses)


class TestConfigurationConsistency(unittest.TestCase):
    """Test configuration consistency with nats-jetstream-plan.md."""

    def test_stream_policies_match_plan(self):
        """Test that stream policies match the plan document."""
        from src.infrastructure.event_bus_nats import NATSConsumerService, StreamConfig

        service = NATSConsumerService(enabled=False)

        # From nats-jetstream-plan.md:
        # BOT_COMMANDS: work queue retention, bot-worker durable consumer, 60s-300s ack, max delivery 5
        bot_commands = service.STREAM_CONFIGS["BOT_COMMANDS"]
        self.assertEqual(bot_commands.retention, "workqueue")

        bot_consumer = service.CONSUMER_CONFIGS["bot-worker"]
        self.assertEqual(bot_consumer.queue_group, "bot-workers")
        self.assertEqual(bot_consumer.max_deliver, 5)
        self.assertEqual(bot_consumer.ack_wait_seconds, 300)

        # BACKTEST_COMMANDS: work queue retention, backtest-worker durable consumer, long ack window
        backtest_commands = service.STREAM_CONFIGS["BACKTEST_COMMANDS"]
        self.assertEqual(backtest_commands.retention, "workqueue")

        backtest_consumer = service.CONSUMER_CONFIGS["backtest-worker"]
        self.assertEqual(backtest_consumer.queue_group, "backtest-workers")
        self.assertEqual(backtest_consumer.max_deliver, 5)
        self.assertEqual(backtest_consumer.ack_wait_seconds, 600)  # 10 minutes

        # DEAD_LETTER: limits retention with long retention window
        dead_letter = service.STREAM_CONFIGS["DEAD_LETTER"]
        self.assertEqual(dead_letter.retention, "limits")
        self.assertEqual(dead_letter.max_age, 90 * 24 * 60 * 60)  # 90 days

    def test_subject_namespace_matches_plan(self):
        """Subjects use the singular owner.kind.action form (Phase 0 unification).

        The consumer subject namespace MUST match the backend publisher
        (backend/internal/nats/publisher.go Subject()), which is the single
        source of truth. Singular form: backtest.command.start, bot.event.started.
        """
        from src.infrastructure.event_bus_nats import NATSConsumerService

        service = NATSConsumerService(enabled=False)

        # Canonical singular subjects that the backend publisher emits.
        expected_subjects = [
            "bot.command.create",
            "bot.command.start",
            "bot.command.stop",
            "bot.command.pause",
            "bot.command.resume",
            "bot.event.started",
            "bot.event.stopped",
            "bot.event.failed",
            "bot.event.trade.created",
            "bot.event.order.updated",
            "backtest.command.create",
            "backtest.command.cancel",
            "backtest.event.started",
            "backtest.event.progress",
            "backtest.event.completed",
            "backtest.event.failed",
            "worker.event.heartbeat",
            "worker.event.failed",
            "system.audit.created",
        ]

        # No canonical subject may use the legacy plural form.
        for subject in expected_subjects:
            self.assertNotIn(".commands.", subject)
            self.assertNotIn(".events.", subject)

        # Check BOT_COMMANDS stream covers bot.command.*
        bot_commands = service.STREAM_CONFIGS["BOT_COMMANDS"]
        self.assertIn("bot.command.>", bot_commands.subjects)

        # Check BACKTEST_COMMANDS stream covers backtest.command.*
        backtest_commands = service.STREAM_CONFIGS["BACKTEST_COMMANDS"]
        self.assertIn("backtest.command.>", backtest_commands.subjects)

        # Check BOT_EVENTS stream covers bot.event.*
        bot_events = service.STREAM_CONFIGS["BOT_EVENTS"]
        self.assertIn("bot.event.>", bot_events.subjects)

    def test_consumer_subjects_match_backend_publisher(self):
        """Phase 0: consumer subject_filter must equal the backend publisher subject.

        backend/internal/nats/publisher.go builds subjects as
        Subject(owner, kind, action) -> "owner.kind.action" (singular). The
        durable backtest consumer must filter on exactly that subject or
        JetStream delivery silently never matches.
        """
        from src.infrastructure.event_bus_nats import NATSConsumerService

        service = NATSConsumerService(enabled=False)
        backtest_consumer = service.CONSUMER_CONFIGS["backtest-worker"]

        # Exact contract value emitted by nats.Subject("backtest", "command", "start").
        self.assertEqual(backtest_consumer.subject_filter, "backtest.command.start")

        # The filtered subject must resolve to the BACKTEST_COMMANDS stream and
        # be covered by that stream's wildcard subject.
        self.assertEqual(service._get_stream_name("backtest.command.start"), "BACKTEST_COMMANDS")
        backtest_stream = service.STREAM_CONFIGS["BACKTEST_COMMANDS"]
        self.assertIn("backtest.command.>", backtest_stream.subjects)


class TestFailClosedBehavior(unittest.IsolatedAsyncioTestCase):
    """Test fail-closed behavior."""

    def setUp(self):
        """Set up test fixtures."""
        os.environ["NATS_ENABLED"] = "false"
        os.environ["BOT_COMMAND_BUS_ENABLED"] = "false"

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ.pop("NATS_ENABLED", None)
        os.environ.pop("BOT_COMMAND_BUS_ENABLED", None)

    @patch('src.infrastructure.event_bus_nats.nats')
    async def test_service_disabled_no_connection_attempt(self, mock_nats):
        """Test that disabled service doesn't attempt connection."""
        from src.infrastructure.event_bus_nats import NATSConsumerService

        service = NATSConsumerService(enabled=False)

        # Mock the NATS client to track if connect is called
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_nats.aio.client.Client.return_value = mock_client

        # Connect should return False without calling NATS when disabled
        result = await service.connect()

        # Verify no connection attempt when disabled
        self.assertFalse(result)
        self.assertFalse(service.is_connected())
        # Verify that Client() was not called (NATS library not used)
        mock_nats.aio.client.Client.assert_not_called()

    def test_global_functions_disabled(self):
        """Test global functions handle disabled NATS gracefully."""
        from src.infrastructure.event_bus_nats import init_nats_consumer_service

        service = init_nats_consumer_service(enabled=False)
        self.assertFalse(service.is_enabled())


if __name__ == "__main__":
    unittest.main()
