"""NATS JetStream backtest command consumer for Phase 4.

This module implements the durable consumer for backtest commands that:
1. Consumes backtest.command.start messages from BACKTEST_COMMANDS stream
2. Performs idempotency checking using PostgreSQL task_commands table
3. Updates task_runs with execution state
4. Creates task_attempts for each retry
5. Implements explicit ack after authoritative PostgreSQL state update
6. Handles retry/ack/dead-letter

Note: the subject ``backtest.command.start`` is the singular canonical form and
must match the backend publisher (backend/internal/nats/publisher.go Subject()).
See docs/FINAL_APPLICATION_IMPROVEMENT_PLAN.md (Phase 0 / Phase 2).

Contract:
- PostgreSQL remains authoritative for all state
- NATS provides durable transport only
- Workers are idempotent and retry-safe
- Explicit ack only after state is persisted
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.infrastructure.database import db
from src.infrastructure.event_bus_nats import (
    MessageAction,
    MessageHandler,
    ProcessedResult,
    get_nats_consumer_service,
)
from src.infrastructure.persistence.repository_backtest import BacktestRepository
from src.infrastructure.workers.nats_worker_metrics import (
    complete_nats_command,
    fail_nats_command,
    start_nats_command,
)

logger = logging.getLogger(__name__)


class TaskRunStatus:
    """Task run status constants matching backend Phase 4 implementation."""
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskAttemptOutcome:
    """Task attempt outcome constants."""
    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILED = "failed"
    REQUEUED = "requeued"


@dataclass
class BacktestCommandPayload:
    """Parsed backtest command payload from NATS message."""
    command_id: str
    run_id: str
    command_type: str
    owner_type: str
    owner_id: str
    idempotency_key: str
    created_at: Optional[str] = None
    status: Optional[str] = None
    name: Optional[str] = None
    strategy_id: Optional[int] = None
    correlation_id: Optional[str] = None
    # Additional fields from payload
    pairs: Optional[List[str]] = None
    source: Optional[str] = None
    environment: Optional[str] = None
    requested_by_user_id: Optional[int] = None


class BacktestCommandHandler:
    """
    Message handler for backtest commands from NATS JetStream.
    
    Implements the Phase 4 consumer pattern:
    - Explicit ack after authoritative PostgreSQL state update
    - Idempotency checking using task_commands table
    - Task run lifecycle management
    - Retry/attempt tracking
    - Dead-letter handling for poison messages
    """

    def __init__(self, backtest_repo: Optional[BacktestRepository] = None):
        """
        Initialize backtest command handler.
        
        Args:
            backtest_repo: Backtest repository for persistence operations
        """
        self.backtest_repo = backtest_repo
        self._worker_id = f"{socket.gethostname()}-{os.getpid()}"
        self._active_tasks: Dict[str, asyncio.Task] = {}  # command_id -> task
        self._running_backtests: Dict[str, bool] = {}  # run_id -> is_running

        logger.info(f"BacktestCommandHandler initialized with worker_id: {self._worker_id}")

    async def handle(self, message: Dict[str, Any], context: Dict[str, Any]) -> ProcessedResult:
        """
        Handle a backtest command message.
        
        This is the main entry point called by the NATS consumer service.
        Implements explicit ack pattern: only ack after PostgreSQL state is updated.
        
        Args:
            message: The message payload (envelope.payload)
            context: Additional context including nats_message, consumer_name, etc.
            
        Returns:
            ProcessedResult with action (ACK, NAK, REQUEUE, DEAD_LETTER)
        """
        # Extract correlation_id from context for traceability
        correlation_id = context.get("correlation_id", "unknown")

        try:
            # Parse the message payload
            payload = self._parse_payload(message, context)
            if not payload:
                logger.warning(
                    f"Invalid or empty payload | correlation_id={correlation_id} | "
                    f"message_id={context.get('message_id', 'unknown')}"
                )
                return ProcessedResult(
                    action=MessageAction.NAK,
                    message_id=context.get("message_id", "unknown"),
                    idempotency_key=context.get("idempotency_key", "unknown"),
                    error_message="Invalid or empty payload",
                    consumer_name=context.get("consumer_name")
                )

            # Add correlation_id to payload for downstream use
            payload.correlation_id = correlation_id

            # Check for duplicate using task_commands table
            if await self._is_duplicate(payload.idempotency_key, payload.command_id):
                logger.info(
                    f"Duplicate backtest command detected | correlation_id={correlation_id} | "
                    f"command_id={payload.command_id} | idempotency_key={payload.idempotency_key}"
                )
                return ProcessedResult(
                    action=MessageAction.ACK,  # Ack duplicates to remove from stream
                    message_id=payload.command_id,
                    idempotency_key=payload.idempotency_key,
                    consumer_name=context.get("consumer_name")
                )

            # Process the backtest command
            result = await self._process_backtest_command(payload, context)

            # Update task command status based on result
            if result.action == MessageAction.ACK:
                await self._update_task_command_status(payload.command_id, "completed")
            elif result.action == MessageAction.NAK:
                await self._update_task_command_status(payload.command_id, "failed")
            elif result.action == MessageAction.REQUEUE:
                await self._update_task_command_status(payload.command_id, "pending")

            return result

        except Exception as e:
            # Extract correlation_id for error logging
            correlation_id = context.get("correlation_id", "unknown")
            logger.error(
                f"Error in backtest command handler | correlation_id={correlation_id} | "
                f"command_id={payload.command_id if payload else 'unknown'} | "
                f"error={e}"
            )
            return ProcessedResult(
                action=MessageAction.NAK,
                message_id=context.get("message_id", "unknown"),
                idempotency_key=context.get("idempotency_key", "unknown"),
                error_message=str(e),
                consumer_name=context.get("consumer_name")
            )

    def _parse_payload(self, message: Dict[str, Any], context: Dict[str, Any]) -> Optional[BacktestCommandPayload]:
        """Parse and validate backtest command payload."""
        try:
            # Extract fields from message (this is the payload from the envelope)
            payload = BacktestCommandPayload(
                command_id=message.get("command_id", context.get("message_id", "")),
                run_id=message.get("run_id", message.get("owner_id", "")),  # owner_id is used as run_id in dual-write
                command_type=message.get("command_type", "backtest"),
                owner_type=message.get("owner_type", "backtest"),
                owner_id=message.get("owner_id", message.get("run_id", "")),
                idempotency_key=message.get("idempotency_key", context.get("idempotency_key", "")),
                created_at=message.get("created_at"),
                status=message.get("status"),
                name=message.get("name"),
                strategy_id=message.get("strategy_id"),
                pairs=message.get("pairs"),
                source=message.get("source"),
                environment=message.get("environment"),
                requested_by_user_id=message.get("requested_by_user_id"),
            )

            # Validate required fields
            if not payload.command_id or not payload.idempotency_key:
                logger.error("Missing required fields: command_id or idempotency_key")
                return None

            # Ensure we have a run_id
            if not payload.run_id:
                payload.run_id = payload.command_id  # Use command_id as run_id if not provided

            return payload

        except Exception as e:
            logger.error(f"Failed to parse payload: {e}")
            return None

    async def _is_duplicate(self, idempotency_key: str, command_id: str) -> bool:
        """Check if this command has already been processed using task_commands table."""
        try:
            session = db.get_session()

            # Check if a task command with this idempotency key exists and is completed
            query = text("""
                SELECT id, status FROM task_commands 
                WHERE idempotency_key = :idempotency_key 
                ORDER BY created_at DESC 
                LIMIT 1
            """)

            result = session.execute(query, {"idempotency_key": idempotency_key})
            row = result.fetchone()

            if row:
                cmd_id = row[0]
                status = row[1]

                # If this is the same command and it's already completed, it's a duplicate
                if cmd_id == command_id and status in ["completed", "failed"]:
                    logger.info(f"Duplicate command {command_id} with status {status}")
                    return True

                # If it's a different command with same idempotency key, it's also a duplicate
                # (shouldn't happen with proper idempotency, but be safe)
                if status in ["completed", "failed"]:
                    logger.info(f"Duplicate idempotency key {idempotency_key} with different command")
                    return True

            return False

        except Exception as e:
            logger.warning(f"Failed to check for duplicates: {e}")
            # On error, assume not duplicate to avoid blocking processing
            return False

    async def _process_backtest_command(self, payload: BacktestCommandPayload,
                                        context: Dict[str, Any]) -> ProcessedResult:
        """Process the backtest command and return appropriate result."""
        # Extract correlation_id for traceability
        correlation_id = payload.correlation_id or context.get("correlation_id", "unknown")

        try:
            logger.info(
                f"Starting backtest processing | correlation_id={correlation_id} | "
                f"command_id={payload.command_id} | run_id={payload.run_id}"
            )

            # Record metrics start time
            start_nats_command(correlation_id)

            # Update task command status to running
            await self._update_task_command_status(payload.command_id, "running")

            # Create or update task run
            task_run_id = await self._ensure_task_run(payload)
            logger.debug(
                f"Task run created/updated | correlation_id={correlation_id} | "
                f"task_run_id={task_run_id}"
            )

            # Create task attempt for this processing
            attempt_id = await self._create_task_attempt(task_run_id, payload)
            logger.debug(
                f"Task attempt created | correlation_id={correlation_id} | "
                f"attempt_id={attempt_id}"
            )

            # Update task run status to starting
            await self._update_task_run_status(task_run_id, TaskRunStatus.STARTING, 0.0)

            # Mark this task as running to prevent concurrent processing
            self._running_backtests[payload.run_id] = True

            # Process the backtest (this would call the actual backtest execution)
            success = await self._execute_backtest(payload, task_run_id, attempt_id)

            # Track retry count from task run
            retry_count = 0

            if success:
                # Update task run to completed
                await self._update_task_run_status(
                    task_run_id, TaskRunStatus.COMPLETED, 100.0
                )
                await self._update_task_attempt_outcome(attempt_id, TaskAttemptOutcome.SUCCESS)

                # Record successful completion metrics
                complete_nats_command(
                    correlation_id=correlation_id,
                    command_id=payload.command_id,
                    run_id=payload.run_id,
                    state="completed",
                    retry_count=retry_count,
                )

                logger.info(
                    f"Backtest completed successfully | correlation_id={correlation_id} | "
                    f"run_id={payload.run_id} | task_run_id={task_run_id}"
                )
                return ProcessedResult(
                    action=MessageAction.ACK,
                    message_id=payload.command_id,
                    idempotency_key=payload.idempotency_key,
                    consumer_name=context.get("consumer_name")
                )
            else:
                # Update task run to failed
                await self._update_task_run_status(task_run_id, TaskRunStatus.FAILED, 0.0)
                await self._update_task_attempt_outcome(
                    attempt_id, TaskAttemptOutcome.FAILED, error_message="Backtest execution failed"
                )

                # Record failure metrics
                fail_nats_command(
                    correlation_id=correlation_id,
                    command_id=payload.command_id,
                    run_id=payload.run_id,
                    error="Backtest execution failed",
                    retry_count=retry_count,
                )

                logger.error(
                    f"Backtest execution failed | correlation_id={correlation_id} | "
                    f"run_id={payload.run_id} | task_run_id={task_run_id}"
                )
                return ProcessedResult(
                    action=MessageAction.NAK,
                    message_id=payload.command_id,
                    idempotency_key=payload.idempotency_key,
                    error_message="Backtest execution failed",
                    consumer_name=context.get("consumer_name")
                )

        except Exception as e:
            logger.error(f"Error processing backtest command {payload.command_id}: {e}")

            # Try to update task run to failed if we have the task_run_id
            if 'task_run_id' in locals():
                try:
                    await self._update_task_run_status(task_run_id, TaskRunStatus.FAILED, 0.0)
                except Exception:
                    pass

            # Try to update task attempt to failed if we have the attempt_id
            if 'attempt_id' in locals():
                try:
                    await self._update_task_attempt_outcome(
                        attempt_id, TaskAttemptOutcome.FAILED, error_message=str(e)
                    )
                except Exception:
                    pass

            return ProcessedResult(
                action=MessageAction.NAK,
                message_id=payload.command_id,
                idempotency_key=payload.idempotency_key,
                error_message=str(e),
                consumer_name=context.get("consumer_name")
            )
        finally:
            # Clean up running state
            self._running_backtests.pop(payload.run_id, None)

    async def _execute_backtest(self, payload: BacktestCommandPayload, task_run_id: str, attempt_id: str) -> bool:
        """Execute the real backtest via BacktestService (same path Celery uses).

        Imports are local so the consumer module stays import-safe and so a real
        backtest only runs when a command is actually consumed. Emits the same
        durable lifecycle/progress events the Celery task emits, so the backend
        projector works identically regardless of which executor ran the backtest.
        """
        try:
            from src.infrastructure.use_cases.service_backtest import BacktestService
            from src.infrastructure.workers.backtest_event_emitter import publish_backtest_event

            logger.info(f"Starting backtest execution for run_id: {payload.run_id}")

            session = db.get_session()
            repository = BacktestRepository(session)
            service = BacktestService(repository)

            async def _progress(callback_run_id: str, progress: float, current_pair: str, eta: float) -> None:
                await self._update_task_run_progress(task_run_id, float(progress))
                await publish_backtest_event(
                    run_id=callback_run_id, status="progress",
                    progress=float(progress), current_pair=current_pair,
                )

            await self._update_task_run_status(task_run_id, TaskRunStatus.RUNNING, 0.0)
            await publish_backtest_event(run_id=payload.run_id, status="started")

            # propagate_exceptions=True so failures surface here for the consumer
            # to mark the run/command failed and emit a failed event.
            await service.execute_existing_backtest(
                payload.run_id, _progress, propagate_exceptions=True
            )

            await self._update_task_run_progress(task_run_id, 100.0)
            await publish_backtest_event(run_id=payload.run_id, status="completed", progress=100.0)
            logger.info(f"Backtest {payload.run_id}: Completed successfully via NATS consumer")
            return True

        except Exception as e:
            logger.error(f"Backtest execution failed for {payload.run_id}: {e}")
            from src.infrastructure.workers.backtest_event_emitter import publish_backtest_event
            await publish_backtest_event(
                run_id=payload.run_id, status="failed",
                error_code="BACKTEST_EXECUTION_FAILED", error_message=str(e),
            )
            return False

    async def _ensure_task_run(self, payload: BacktestCommandPayload) -> str:
        """Create or return the task run for this command.

        SQL is aligned with migration 000064_create_task_runs.up.sql:
        task_runs has no requested_by_user_id column, and id is a server-generated
        UUID (gen_random_uuid()), so we omit id from the INSERT and read back the
        generated value via RETURNING.
        """
        try:
            session = db.get_session()

            # Check if a task run already exists for this command (idempotent).
            query = text("""
                SELECT id FROM task_runs
                WHERE command_id = :command_id
                ORDER BY created_at DESC
                LIMIT 1
            """)

            result = session.execute(query, {"command_id": payload.command_id})
            row = result.fetchone()

            if row:
                return str(row[0])  # Return existing task run ID

            # Create new task run. id/created_at/updated_at are defaulted by the DB.
            insert_query = text("""
                INSERT INTO task_runs
                    (command_id, task_type, max_retries, status, progress_pct)
                VALUES
                    (:command_id, :task_type, :max_retries, :status, :progress_pct)
                RETURNING id
            """)

            result = session.execute(insert_query, {
                "command_id": payload.command_id,
                "task_type": "backtest_execution",
                "max_retries": 3,  # Default max retries
                "status": TaskRunStatus.PENDING,
                "progress_pct": 0.0,
            })

            row = result.fetchone()
            session.commit()

            if row is None:
                raise RuntimeError("task_runs INSERT did not return an id")
            return str(row[0])

        except Exception as e:
            logger.error(f"Failed to create task run for command {payload.command_id}: {e}")
            session.rollback()
            raise

    async def _create_task_attempt(self, task_run_id: str, payload: BacktestCommandPayload) -> str:
        """Create a task attempt record for this processing.

        SQL is aligned with migration 000065_create_task_attempts.up.sql:
        task_attempts has no status column, and id is a server-generated UUID.
        started_at defaults to NOW() in the schema, and outcome is NOT NULL.
        """
        try:
            session = db.get_session()

            # Get current retry count for this run
            retry_count = await self._get_task_run_retry_count(task_run_id)

            insert_query = text("""
                INSERT INTO task_attempts
                    (task_run_id, attempt_number, worker_id, consumer_name, outcome)
                VALUES
                    (:task_run_id, :attempt_number, :worker_id, :consumer_name, :outcome)
                RETURNING id
            """)

            result = session.execute(insert_query, {
                "task_run_id": task_run_id,
                "attempt_number": retry_count + 1,
                "worker_id": self._worker_id,
                "consumer_name": "backtest-worker",
                "outcome": TaskAttemptOutcome.STARTED,
            })

            row = result.fetchone()
            session.commit()

            if row is None:
                raise RuntimeError("task_attempts INSERT did not return an id")
            return str(row[0])

        except Exception as e:
            logger.error(f"Failed to create task attempt for run {task_run_id}: {e}")
            session.rollback()
            raise

    async def _get_task_run_retry_count(self, task_run_id: str) -> int:
        """Get the current retry count for a task run."""
        try:
            session = db.get_session()

            query = text("""
                SELECT COUNT(*) FROM task_attempts 
                WHERE task_run_id = :task_run_id 
                AND outcome != 'success'
            """)

            result = session.execute(query, {"task_run_id": task_run_id})
            row = result.fetchone()
            return row[0] if row else 0

        except Exception as e:
            logger.error(f"Failed to get retry count for run {task_run_id}: {e}")
            return 0

    async def _update_task_command_status(self, command_id: str, status: str) -> None:
        """Update task command status.

        updated_at is provided by migration 000067 (DEFAULT NOW() + BEFORE UPDATE
        trigger), matching repository.UpdateTaskCommandStatus on the Go side.
        """
        try:
            session = db.get_session()

            update_query = text("""
                UPDATE task_commands
                SET status = :status, updated_at = NOW()
                WHERE id = :command_id
            """)

            session.execute(update_query, {
                "status": status,
                "command_id": command_id,
            })
            session.commit()

        except Exception as e:
            logger.error(f"Failed to update task command {command_id} status to {status}: {e}")
            session.rollback()

    async def _update_task_run_status(self, task_run_id: str, status: str, progress_pct: float) -> None:
        """Update task run status and progress."""
        try:
            session = db.get_session()

            update_query = text("""
                UPDATE task_runs 
                SET status = :status, 
                    progress_pct = :progress_pct,
                    updated_at = :updated_at,
                    last_heartbeat_at = :last_heartbeat_at
                WHERE id = :task_run_id
            """)

            session.execute(update_query, {
                "status": status,
                "progress_pct": progress_pct,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "last_heartbeat_at": datetime.now(timezone.utc).isoformat(),
                "task_run_id": task_run_id
            })
            session.commit()

        except Exception as e:
            logger.error(f"Failed to update task run {task_run_id} status: {e}")
            session.rollback()

    async def _update_task_run_progress(self, task_run_id: str, progress_pct: float) -> None:
        """Update task run progress percentage."""
        try:
            session = db.get_session()

            update_query = text("""
                UPDATE task_runs 
                SET progress_pct = :progress_pct,
                    updated_at = :updated_at,
                    last_heartbeat_at = :last_heartbeat_at
                WHERE id = :task_run_id
            """)

            session.execute(update_query, {
                "progress_pct": min(max(progress_pct, 0.0), 100.0),  # Clamp to 0-100
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "last_heartbeat_at": datetime.now(timezone.utc).isoformat(),
                "task_run_id": task_run_id
            })
            session.commit()

        except Exception as e:
            logger.error(f"Failed to update task run {task_run_id} progress: {e}")
            session.rollback()

    async def _update_task_attempt_outcome(
            self,
            attempt_id: str,
            outcome: str,
            error_message: Optional[str] = None,
            error_code: Optional[str] = None
    ) -> None:
        """Update task attempt outcome."""
        try:
            session = db.get_session()

            update_query = text("""
                UPDATE task_attempts 
                SET outcome = :outcome,
                    finished_at = :finished_at,
                    error_message = :error_message,
                    error_code = :error_code
                WHERE id = :attempt_id
            """)

            session.execute(update_query, {
                "outcome": outcome,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error_message": error_message,
                "error_code": error_code,
                "attempt_id": attempt_id
            })
            session.commit()

        except Exception as e:
            logger.error(f"Failed to update task attempt {attempt_id} outcome: {e}")
            session.rollback()


# Global handler instance
_backtest_command_handler: Optional[BacktestCommandHandler] = None


def get_backtest_command_handler() -> BacktestCommandHandler:
    """Get or create the global backtest command handler."""
    global _backtest_command_handler
    if _backtest_command_handler is None:
        _backtest_command_handler = BacktestCommandHandler()
    return _backtest_command_handler


async def init_nats_backtest_consumers() -> Optional[BacktestCommandHandler]:
    """
    Initialize NATS backtest consumers.
    
    This function:
    1. Creates the NATS consumer service
    2. Registers the backtest command handler
    3. Subscribes to backtest command messages
    4. Starts the consumer service
    
    Returns the backtest command handler or None if initialization failed.
    """
    try:
        # Get or create consumer service
        consumer_service = get_nats_consumer_service()
        if consumer_service is None:
            from src.infrastructure.event_bus_nats import init_nats_consumer_service
            consumer_service = init_nats_consumer_service()

        # Check if NATS is enabled
        if not consumer_service.is_enabled():
            logger.info("NATS consumers disabled by configuration")
            return None

        # Connect to NATS if not already connected
        if not consumer_service.is_connected():
            await consumer_service.connect()

        # Get or create backtest command handler
        handler = get_backtest_command_handler()

        # Register handler with consumer service
        consumer_service.register_handler("backtest-worker", handler)

        # Subscribe to backtest commands
        await consumer_service.subscribe_backtest_commands()

        logger.info("NATS backtest consumers initialized successfully")
        return handler

    except Exception as e:
        logger.error(f"Failed to initialize NATS backtest consumers: {e}")
        return None


async def shutdown_nats_backtest_consumers() -> None:
    """Shutdown NATS backtest consumers."""
    consumer_service = get_nats_consumer_service()
    if consumer_service is not None:
        await consumer_service.shutdown()
        logger.info("NATS backtest consumers shutdown complete")
