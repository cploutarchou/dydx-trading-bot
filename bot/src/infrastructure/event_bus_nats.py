"""NATS JetStream consumer implementation for Phase 4 dual-write foundation.

This module provides the durable consumer side of the NATS JetStream command/event bus.
It implements explicit ack after authoritative PostgreSQL state updates using task
tables for idempotency checking, with retry/ack/dead-letter handling.

Subject namespace: the singular owner.kind.action form (e.g. ``backtest.command.start``)
is the canonical contract and MUST match the backend publisher
(``backend/internal/nats/publisher.go`` Subject()), which is the single source of
truth. See docs/FINAL_APPLICATION_IMPROVEMENT_PLAN.md (Phase 0).

Contract:
- PostgreSQL stores final state (authoritative)
- NATS JetStream provides durable async transport
- Workers must be idempotent and retry-safe
- Explicit ack only after state is persisted to PostgreSQL
- Failed messages moved to DEAD_LETTER stream after max deliveries
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import socket
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol

# Optional import for NATS - will be None if not installed
try:
    import nats
    from nats.aio.client import Client as NatsClient
    from nats.aio.subscription import Subscription as NatsSubscription
    NATS_AVAILABLE = True
except ImportError:
    NATS_AVAILABLE = False
    NatsClient = None
    NatsSubscription = None
    nats = None

from src.infrastructure.database import db
from src.infrastructure.persistence.repository_backtest import BacktestRepository

logger = logging.getLogger(__name__)


class ConsumerStatus(Enum):
    """Consumer lifecycle status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SUBSCRIBED = "subscribed"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"


class MessageAction(Enum):
    """Action types for NATS message handling."""
    ACK = "ack"
    NAK = "nak"
    REQUEUE = "requeue"
    DEAD_LETTER = "dead_letter"


@dataclass
class ConsumerConfig:
    """Configuration for a NATS JetStream durable consumer."""
    name: str
    stream: str
    subject_filter: str
    queue_group: str
    durable_name: str
    deliver_subject: Optional[str] = None
    ack_wait_seconds: int = 300  # 5 minutes for backtest commands
    max_deliver: int = 5
    max_ack_pending: int = 100
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    start_at: Optional[str] = None  # "all", "last", "time:...", "sequence:..."
    start_sequence: Optional[int] = None
    deliver_all: bool = False


@dataclass
class StreamConfig:
    """Configuration for a NATS JetStream stream."""
    name: str
    subjects: List[str]
    retention: str = "workqueue"  # "limits", "interest", "workqueue"
    max_bytes: int = 10 * 1024 * 1024 * 1024  # 10GB
    max_age: Optional[int] = None  # seconds
    max_msgs: Optional[int] = None
    max_msgs_per_subject: Optional[int] = None
    max_consumers: Optional[int] = None
    discard: str = "old"  # "old", "new"
    storage: str = "file"  # "memory", "file"
    replicas: int = 1
    duplicates_window: int = 2 * 60 * 60  # 2 hours in seconds for duplicate detection


@dataclass
class ProcessedResult:
    """Result of processing a NATS message."""
    action: MessageAction
    message_id: str
    idempotency_key: str
    error_message: Optional[str] = None
    requeue_delay_seconds: Optional[int] = None
    consumer_name: Optional[str] = None


class MessageHandler(Protocol):
    """Protocol for message handlers."""
    
    async def handle(self, message: Dict[str, Any], context: Dict[str, Any]) -> ProcessedResult:
        """Handle a NATS message and return processing result."""
        ...


class NATSConsumerService:
    """
    NATS JetStream durable consumer service.
    
    Implements explicit ack after authoritative PostgreSQL state updates,
    with retry/ack/dead-letter handling per the NATS JetStream plan.
    """
    
    # Stream configurations. The subject namespace MUST stay in sync with the
    # backend publisher (backend/internal/nats/publisher.go Subject()), which is
    # the single source of truth. Subjects use the singular owner.kind.action
    # form, e.g. "backtest.command.start" / "backtest.event.completed". Stream
    # names (e.g. BACKTEST_COMMANDS) are collection names and are intentionally
    # plural; only the subject strings must match the publisher exactly.
    STREAM_CONFIGS = {
        "BOT_COMMANDS": StreamConfig(
            name="BOT_COMMANDS",
            subjects=["bot.command.>"],
            retention="workqueue",
            max_bytes=10 * 1024 * 1024 * 1024,  # 10GB
            storage="file",
            replicas=1,
            duplicates_window=2 * 60 * 60,  # 2 hours
        ),
        "BOT_EVENTS": StreamConfig(
            name="BOT_EVENTS",
            subjects=["bot.event.>"],
            retention="limits",
            max_bytes=5 * 1024 * 1024 * 1024,  # 5GB
            storage="file",
            replicas=1,
            duplicates_window=2 * 60 * 60,
        ),
        "BACKTEST_COMMANDS": StreamConfig(
            name="BACKTEST_COMMANDS",
            subjects=["backtest.command.>"],
            retention="workqueue",
            max_bytes=10 * 1024 * 1024 * 1024,  # 10GB
            storage="file",
            replicas=1,
            duplicates_window=2 * 60 * 60,
        ),
        "BACKTEST_EVENTS": StreamConfig(
            name="BACKTEST_EVENTS",
            subjects=["backtest.event.>"],
            retention="limits",
            max_bytes=5 * 1024 * 1024 * 1024,  # 5GB
            storage="file",
            replicas=1,
            duplicates_window=2 * 60 * 60,
        ),
        "WORKER_EVENTS": StreamConfig(
            name="WORKER_EVENTS",
            subjects=["worker.event.>"],
            retention="limits",
            max_bytes=2 * 1024 * 1024 * 1024,  # 2GB
            storage="file",
            replicas=1,
            duplicates_window=2 * 60 * 60,
        ),
        "SYSTEM_AUDIT": StreamConfig(
            name="SYSTEM_AUDIT",
            subjects=["system.audit.>"],
            retention="limits",
            max_bytes=1 * 1024 * 1024 * 1024,  # 1GB
            storage="file", 
            replicas=1,
            max_age=30 * 24 * 60 * 60,  # 30 days
            duplicates_window=2 * 60 * 60,
        ),
        "DEAD_LETTER": StreamConfig(
            name="DEAD_LETTER",
            subjects=["deadletter.>"],
            retention="limits",
            max_bytes=2 * 1024 * 1024 * 1024,  # 2GB
            storage="file",
            replicas=1,
            max_age=90 * 24 * 60 * 60,  # 90 days
            duplicates_window=2 * 60 * 60,
        ),
    }
    
    # Consumer configurations
    CONSUMER_CONFIGS = {
        "backtest-worker": ConsumerConfig(
            name="backtest-worker",
            stream="BACKTEST_COMMANDS",
            subject_filter="backtest.command.start",
            queue_group="backtest-workers",
            durable_name="backtest-worker",
            ack_wait_seconds=600,  # 10 minutes for long-running backtests
            max_deliver=5,
            max_ack_pending=50,
        ),
        "bot-worker": ConsumerConfig(
            name="bot-worker",
            stream="BOT_COMMANDS",
            subject_filter="bot.command.>",
            queue_group="bot-workers",
            durable_name="bot-worker",
            ack_wait_seconds=300,  # 5 minutes
            max_deliver=5,
            max_ack_pending=50,
        ),
    }
    
    def __init__(
        self,
        *,
        servers: Optional[List[str]] = None,
        enabled: bool = False,
        connect_timeout: int = 10,
        reconnect_timeout: int = 30,
        max_reconnects: int = -1,  # -1 = unlimited
        verbose: bool = False,
    ):
        """
        Initialize NATS consumer service.
        
        Args:
            servers: List of NATS server URLs (e.g., ["nats://localhost:4222"])
            enabled: Whether NATS consumers are enabled
            connect_timeout: Connection timeout in seconds
            reconnect_timeout: Reconnect timeout in seconds
            max_reconnects: Maximum reconnection attempts (-1 for unlimited)
            verbose: Enable verbose logging
        """
        self.servers = servers or self._get_default_servers()
        self.enabled = enabled or self._is_nats_enabled()
        self.connect_timeout = connect_timeout
        self.reconnect_timeout = reconnect_timeout
        self.max_reconnects = max_reconnects
        self.verbose = verbose
        
        self._client: Optional[NatsClient] = None
        self._jetstream: Optional[nats.aio.client.JetStreamContext] = None
        self._subscriptions: Dict[str, NatsSubscription] = {}
        self._handlers: Dict[str, MessageHandler] = {}
        self._status = ConsumerStatus.DISCONNECTED
        self._shutdown_event = asyncio.Event()
        self._stream_configs = self.STREAM_CONFIGS.copy()
        self._consumer_configs = self.CONSUMER_CONFIGS.copy()
        
        # Task repository for idempotency checking
        self._task_repo: Optional[Any] = None  # Will be set via set_task_repository
        
        # Check if NATS library is available
        if not NATS_AVAILABLE:
            logger.warning("NATS library not available - consumer service will be disabled")
            self.enabled = False
        
        logger.info(
            f"NATS Consumer Service initialized: enabled={self.enabled}, "
            f"servers={self.servers}, timeout={self.connect_timeout}s, "
            f"nats_available={NATS_AVAILABLE}"
        )
    
    def _get_default_servers(self) -> List[str]:
        """Get default NATS servers from environment."""
        servers = []
        
        # Try NATS_ENABLED first
        nats_enabled = os.getenv("NATS_ENABLED", "false").lower() == "true"
        
        # Try individual server configs
        nats_url = os.getenv("NATS_URL", os.getenv("NATS_SERVER_URL", ""))
        if nats_url:
            servers.append(nats_url)
        
        # Try multiple servers
        nats_servers = os.getenv("NATS_SERVERS", "")
        if nats_servers:
            servers.extend([s.strip() for s in nats_servers.split(",") if s.strip()])
        
        # Default fallback
        if not servers:
            servers = ["nats://localhost:4222"]
        
        return servers
    
    def _is_nats_enabled(self) -> bool:
        """Check if NATS is enabled via environment variables."""
        nats_enabled = os.getenv("NATS_ENABLED", "false").lower() == "true"
        command_bus_enabled = os.getenv("BOT_COMMAND_BUS_ENABLED", "false").lower() == "true"
        return nats_enabled or command_bus_enabled
    
    def set_task_repository(self, repo: Any) -> None:
        """Set the task repository for idempotency checking."""
        self._task_repo = repo
        logger.info("Task repository set for idempotency checking")
    
    def register_handler(self, consumer_name: str, handler: MessageHandler) -> None:
        """Register a message handler for a specific consumer."""
        self._handlers[consumer_name] = handler
        logger.info(f"Registered handler for consumer: {consumer_name}")
    
    async def connect(self) -> bool:
        """Connect to NATS server and initialize JetStream context."""
        if not self.enabled:
            logger.warning("NATS consumer disabled, skipping connection")
            self._status = ConsumerStatus.DISCONNECTED
            return False
        
        if self._client is not None:
            logger.info("Already connected to NATS server")
            return True
        
        self._status = ConsumerStatus.CONNECTING
        
        if not NATS_AVAILABLE:
            logger.warning("NATS library not available, cannot connect")
            self._status = ConsumerStatus.ERROR
            return False
            
        try:
            # Create NATS client
            self._client = NatsClient()
            
            # Configure connection options
            # Note: max_reconnects=-1 means unlimited in our API, but nats-py uses max_reconnect_attempts
            max_reconnect_attempts = self.max_reconnects if self.max_reconnects >= 0 else 60
            
            options = {
                "servers": self.servers,
                "connect_timeout": self.connect_timeout,
                "reconnect_time_wait": self.reconnect_timeout,
                "max_reconnect_attempts": max_reconnect_attempts,
                "verbose": self.verbose,
                "allow_reconnect": True,
                "name": "bot-nats-consumer",
                "error_cb": self._on_error,
                "disconnected_cb": self._on_disconnect,
                "closed_cb": self._on_close,
                "reconnected_cb": self._on_reconnect,
            }
            
            await self._client.connect(**options)
            
            # Create JetStream context
            self._jetstream = self._client.jetstream()
            
            self._status = ConsumerStatus.CONNECTED
            logger.info(
                f"Connected to NATS server: {self._client.connected_url}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to NATS server: {e}")
            self._status = ConsumerStatus.ERROR
            self._client = None
            return False
    
    def _on_connect(self, client: NatsClient) -> None:
        """Callback when NATS connection is established."""
        logger.info(f"NATS connection established to {client.connected_url}")
        self._status = ConsumerStatus.CONNECTED
    
    def _on_disconnect(self, client: NatsClient) -> None:
        """Callback when NATS connection is lost."""
        logger.warning(f"NATS connection lost from {client.connected_url}")
        self._status = ConsumerStatus.DISCONNECTED
    
    def _on_reconnect(self, client: NatsClient) -> None:
        """Callback when NATS connection is re-established."""
        logger.info(f"NATS connection re-established to {client.connected_url}")
        self._status = ConsumerStatus.CONNECTED
        # Re-subscribe all consumers
        asyncio.create_task(self._resubscribe_all())
    
    def _on_close(self, client: NatsClient) -> None:
        """Callback when NATS connection is closed."""
        logger.info("NATS connection closed")
        self._status = ConsumerStatus.DISCONNECTED
    
    def _on_error(self, client: NatsClient, error: Exception) -> None:
        """Callback when NATS connection error occurs."""
        logger.error(f"NATS connection error: {error}")
        self._status = ConsumerStatus.ERROR
    
    async def _resubscribe_all(self) -> None:
        """Re-subscribe all consumers after reconnection."""
        if not self._client or not self._jetstream:
            return
            
        logger.info("Re-subscribing all NATS consumers...")
        
        for consumer_name, consumer_config in self._consumer_configs.items():
            try:
                await self._ensure_stream(consumer_config.stream)
                await self._subscribe_consumer(consumer_name, consumer_config)
                logger.info(f"Re-subscribed consumer: {consumer_name}")
            except Exception as e:
                logger.error(f"Failed to re-subscribe consumer {consumer_name}: {e}")
    
    async def _ensure_stream(self, stream_name: str) -> None:
        """Ensure the specified stream exists with proper configuration."""
        if not self._jetstream:
            raise RuntimeError("JetStream context not available")
        
        stream_config = self._stream_configs.get(stream_name)
        if not stream_config:
            logger.warning(f"No configuration found for stream: {stream_name}")
            return
        
        # Check if stream exists
        try:
            stream_info = await self._jetstream.stream_info(stream_name)
            logger.info(f"Stream {stream_name} already exists")
            return
        except nats.errors.StreamNotFoundError:
            logger.info(f"Stream {stream_name} not found, creating...")
        except Exception as e:
            logger.warning(f"Error checking stream {stream_name}: {e}")
            return
        
        # Create stream
        try:
            await self._jetstream.add_stream(
                name=stream_name,
                subjects=stream_config.subjects,
                retention=nats.api.RetentionPolicy[stream_config.retention.upper()],
                max_bytes=stream_config.max_bytes,
                max_age=stream_config.max_age,
                max_msgs=stream_config.max_msgs,
                max_msgs_per_subject=stream_config.max_msgs_per_subject,
                max_consumers=stream_config.max_consumers,
                discard=nats.api.DiscardPolicy[stream_config.discard.upper()],
                storage=nats.api.StorageType[stream_config.storage.upper()],
                replicas=stream_config.replicas,
                duplicates=stream_config.duplicates_window,
            )
            logger.info(f"Created stream {stream_name} with subjects {stream_config.subjects}")
            
        except Exception as e:
            logger.error(f"Failed to create stream {stream_name}: {e}")
            raise
    
    async def _ensure_consumer(self, consumer_config: ConsumerConfig) -> None:
        """Ensure the specified consumer exists for the stream."""
        if not self._jetstream:
            raise RuntimeError("JetStream context not available")
        
        try:
            # Check if consumer exists
            consumer_info = await self._jetstream.consumer_info(
                stream=consumer_config.stream,
                consumer=consumer_config.durable_name
            )
            logger.info(f"Consumer {consumer_config.durable_name} already exists in stream {consumer_config.stream}")
            return
        except nats.errors.ConsumerNotFoundError:
            logger.info(f"Consumer {consumer_config.durable_name} not found, creating...")
        except Exception as e:
            logger.warning(f"Error checking consumer {consumer_config.durable_name}: {e}")
            return
        
        # Create consumer
        try:
            await self._jetstream.add_consumer(
                stream=consumer_config.stream,
                durable=consumer_config.durable_name,
                filter_subject=consumer_config.subject_filter,
                deliver_subject=consumer_config.deliver_subject,
                deliver_group=consumer_config.queue_group,
                ack=300,  # Explicit ack required
                ack_wait=consumer_config.ack_wait_seconds,
                max_deliver=consumer_config.max_deliver,
                max_ack_pending=consumer_config.max_ack_pending,
                max_bytes=consumer_config.max_bytes,
                start_at=consumer_config.start_at,
                start_sequence=consumer_config.start_sequence,
                deliver_all=consumer_config.deliver_all,
            )
            logger.info(f"Created consumer {consumer_config.durable_name} in stream {consumer_config.stream}")
            
        except Exception as e:
            logger.error(f"Failed to create consumer {consumer_config.durable_name}: {e}")
            raise
    
    async def _subscribe_consumer(self, consumer_name: str, consumer_config: ConsumerConfig) -> None:
        """Subscribe to messages for a specific consumer."""
        if not self._jetstream:
            raise RuntimeError("JetStream context not available")
        
        if not self._client:
            raise RuntimeError("NATS client not connected")
        
        try:
            # Ensure consumer exists
            await self._ensure_consumer(consumer_config)
            
            # Create subscription
            subscription = await self._jetstream.subscribe(
                subject=consumer_config.subject_filter,
                queue=consumer_config.queue_group,
                durable=consumer_config.durable_name,
                config=nats.api.ConsumerConfig(
                    ack_policy=nats.api.AckExplicitPolicy,
                    ack_wait=consumer_config.ack_wait_seconds,
                    max_delivery_attempts=consumer_config.max_deliver,
                    max_ack_pending=consumer_config.max_ack_pending,
                )
            )
            
            self._subscriptions[consumer_name] = subscription
            self._status = ConsumerStatus.SUBSCRIBED
            
            logger.info(
                f"Subscribed consumer {consumer_name} to {consumer_config.subject_filter} "
                f"with queue group {consumer_config.queue_group}"
            )
            
            # Start processing messages
            asyncio.create_task(self._process_messages(consumer_name, subscription))
            
        except Exception as e:
            logger.error(f"Failed to subscribe consumer {consumer_name}: {e}")
            raise
    
    async def _process_messages(self, consumer_name: str, subscription: NatsSubscription) -> None:
        """Process messages from a subscription."""
        handler = self._handlers.get(consumer_name)
        if not handler:
            logger.warning(f"No handler registered for consumer {consumer_name}")
            return
        
        consumer_config = self._consumer_configs.get(consumer_name)
        if not consumer_config:
            logger.warning(f"No configuration found for consumer {consumer_name}")
            return
        
        logger.info(f"Starting message processing for consumer: {consumer_name}")
        
        try:
            async for message in subscription.messages:
                try:
                    # Parse message
                    subject = message.subject
                    data = message.data.decode()
                    
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON payload: {e}")
                        await message.nak()
                        continue
                    
                    logger.info(
                        f"Received message on {subject}: "
                        f"msg_id={message.header.get('Msg-Id', 'unknown')}, "
                        f"sequence={message.meta.sequence}"
                    )
                    
                    # Extract envelope fields
                    envelope = self._extract_envelope(payload)
                    if not envelope:
                        logger.error("Invalid message envelope format")
                        await message.nak()
                        continue
                    
                    # Check for duplicates using PostgreSQL task tables
                    if self._task_repo:
                        is_duplicate = await self._check_duplicate(envelope)
                        if is_duplicate:
                            logger.info(
                                f"Duplicate message detected, acking: "
                                f"idempotency_key={envelope.get('idempotency_key')}"
                            )
                            await message.ack()
                            continue
                    
                    # Build context for handler
                    context = {
                        "consumer_name": consumer_name,
                        "subject": subject,
                        "message_id": envelope.get("message_id"),
                        "correlation_id": envelope.get("correlation_id"),
                        "idempotency_key": envelope.get("idempotency_key"),
                        "producer_service": envelope.get("producer_service"),
                        "schema_version": envelope.get("schema_version"),
                        "occurred_at": envelope.get("occurred_at"),
                        "raw_payload": payload,
                        "nats_message": message,
                    }
                    
                    # Process message with handler
                    result = await handler.handle(envelope.get("payload", {}), context)
                    
                    # Handle result
                    await self._handle_result(message, result)
                    
                except Exception as e:
                    logger.error(f"Error processing message in consumer {consumer_name}: {e}")
                    try:
                        await message.nak()
                    except Exception as nak_error:
                        logger.error(f"Failed to send NAK: {nak_error}")
                    
        except Exception as e:
            logger.error(f"Message processing loop failed for consumer {consumer_name}: {e}")
        except asyncio.CancelledError:
            logger.info(f"Message processing cancelled for consumer {consumer_name}")
        finally:
            logger.info(f"Message processing stopped for consumer {consumer_name}")
    
    def _extract_envelope(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract envelope from message payload."""
        if not isinstance(payload, dict):
            return None
        
        # Check if this is already the envelope format
        required_fields = ["message_id", "idempotency_key", "correlation_id", "subject", "occurred_at", "producer_service", "schema_version"]
        if all(field in payload for field in required_fields):
            return payload
        
        # Check if payload is nested under "payload" key
        if "payload" in payload and isinstance(payload["payload"], dict):
            nested_payload = payload["payload"]
            if all(field in nested_payload for field in required_fields):
                return nested_payload
        
        return None
    
    async def _check_duplicate(self, envelope: Dict[str, Any]) -> bool:
        """Check if message is a duplicate using PostgreSQL task tables."""
        try:
            idempotency_key = envelope.get("idempotency_key")
            if not idempotency_key:
                return False
            
            message_id = envelope.get("message_id")
            if not message_id:
                return False
            
            # Check if task command with this idempotency key already exists
            # and has reached a terminal state
            session = db.get_session()
            
            # This would query the task_commands table created in Phase 4
            # For now, we'll implement a simple check; this will be enhanced
            # when the task repository is fully integrated
            from sqlalchemy import text
            
            query = text("""
                SELECT id, status FROM task_commands 
                WHERE idempotency_key = :idempotency_key 
                ORDER BY created_at DESC 
                LIMIT 1
            """)
            
            result = session.execute(query, {"idempotency_key": idempotency_key})
            row = result.fetchone()
            
            if row:
                status = row[1]  # status column
                # If command exists and is already published/completed, it's a duplicate
                if status in ["published", "completed", "failed"]:
                    logger.info(f"Duplicate detected for idempotency_key: {idempotency_key}, status: {status}")
                    return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Failed to check for duplicates: {e}")
            # On error, assume not duplicate to avoid blocking message processing
            return False
    
    async def _handle_result(self, message: nats.aio.client.Msg, result: ProcessedResult) -> None:
        """Handle the result of message processing."""
        try:
            if result.action == MessageAction.ACK:
                logger.info(f"Acking message: {result.message_id}")
                await message.ack()
            elif result.action == MessageAction.NAK:
                logger.warning(f"Nak-ing message {result.message_id}: {result.error_message}")
                await message.nak()
            elif result.action == MessageAction.REQUEUE:
                delay = result.requeue_delay_seconds or 0
                logger.info(f"Requeuing message {result.message_id} with delay: {delay}s")
                await message.nak(delay=delay)
            elif result.action == MessageAction.DEAD_LETTER:
                logger.error(f"Moving message {result.message_id} to dead letter: {result.error_message}")
                await self._move_to_dead_letter(message, result)
            else:
                logger.warning(f"Unknown action {result.action} for message {result.message_id}")
                await message.nak()
                
        except Exception as e:
            logger.error(f"Failed to handle result for message {result.message_id}: {e}")
    
    async def _move_to_dead_letter(self, message: nats.aio.client.Msg, result: ProcessedResult) -> None:
        """Move message to dead letter stream."""
        if not self._jetstream:
            await message.nak()
            return
        
        try:
            # Build dead letter payload
            original_subject = message.subject
            dead_letter_subject = f"deadletter.{original_subject.replace('.', '_')}"
            
            dead_letter_payload = {
                "original_stream": self._get_stream_name(original_subject),
                "original_subject": original_subject,
                "message_id": result.message_id,
                "idempotency_key": result.idempotency_key,
                "consumer_name": result.consumer_name,
                "error_message": result.error_message,
                "delivery_count": message.meta.num_delivered,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "producer_service": message.header.get("Producer-Service", "unknown"),
                "original_payload": message.data.decode(),
            }
            
            # Publish to dead letter stream
            await self._jetstream.publish(
                subject=dead_letter_subject,
                payload=json.dumps(dead_letter_payload).encode(),
                headers={
                    "Msg-Id": result.message_id,
                    "Original-Subject": original_subject,
                    "Error": result.error_message or "unknown",
                    "Delivery-Count": str(message.meta.num_delivered),
                }
            )
            
            logger.info(f"Published to dead letter: {dead_letter_subject}")
            
            # Ack the original message since it's been moved to dead letter
            await message.ack()
            
        except Exception as e:
            logger.error(f"Failed to move to dead letter: {e}")
            await message.nak()
    
    def _get_stream_name(self, subject: str) -> str:
        """Get stream name for a given subject based on configuration."""
        for stream_name, config in self._stream_configs.items():
            for stream_subject in config.subjects:
                # Exact match
                if subject == stream_subject:
                    return stream_name
                
                # Wildcard match (stream_subject ends with '>')
                if stream_subject.endswith('>'):
                    prefix = stream_subject[:-1]  # Remove the '>'
                    # In NATS, '>' is a wildcard that matches any suffix.
                    # 'backtest.command.>' matches 'backtest.command.start',
                    # 'backtest.command.cancel', etc. (singular form, matching
                    # the backend publisher Subject()).
                    if subject.startswith(prefix):
                        return stream_name
                
                # Also check if subject starts with the stream_subject directly
                if subject.startswith(stream_subject):
                    return stream_name
        return "UNKNOWN"
    
    async def subscribe_backtest_commands(self) -> bool:
        """Subscribe to backtest command messages."""
        if not self.enabled:
            logger.info("NATS consumer disabled, skipping backtest command subscription")
            return False
        
        if not self._client:
            await self.connect()
            if not self._client:
                return False
        
        consumer_config = self.CONSUMER_CONFIGS.get("backtest-worker")
        if not consumer_config:
            logger.error("No consumer configuration found for backtest-worker")
            return False
        
        try:
            # Ensure stream exists
            await self._ensure_stream(consumer_config.stream)
            
            # Subscribe consumer
            await self._subscribe_consumer("backtest-worker", consumer_config)
            
            logger.info("Successfully subscribed to backtest commands")
            return True
            
        except Exception as e:
            logger.error(f"Failed to subscribe to backtest commands: {e}")
            return False
    
    async def subscribe_all(self) -> Dict[str, bool]:
        """Subscribe to all configured consumers."""
        results = {}
        
        for consumer_name, consumer_config in self._consumer_configs.items():
            try:
                await self._ensure_stream(consumer_config.stream)
                success = await self._subscribe_consumer(consumer_name, consumer_config)
                results[consumer_name] = success
            except Exception as e:
                logger.error(f"Failed to subscribe consumer {consumer_name}: {e}")
                results[consumer_name] = False
        
        return results
    
    async def start(self) -> bool:
        """Start the NATS consumer service."""
        if not self.enabled:
            logger.info("NATS consumer service disabled")
            return False
        
        try:
            # Connect to NATS
            if not await self.connect():
                return False
            
            # Subscribe to all consumers
            results = await self.subscribe_all()
            
            success_count = sum(1 for result in results.values() if result)
            logger.info(f"Started {success_count}/{len(results)} consumers successfully")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Failed to start NATS consumer service: {e}")
            return False
    
    async def shutdown(self) -> None:
        """Shutdown the NATS consumer service gracefully."""
        logger.info("Shutting down NATS consumer service...")
        self._status = ConsumerStatus.SHUTTING_DOWN
        self._shutdown_event.set()
        
        # Cancel all subscriptions
        for consumer_name, subscription in self._subscriptions.items():
            try:
                await subscription.unsubscribe()
                logger.info(f"Unsubscribed consumer: {consumer_name}")
            except Exception as e:
                logger.warning(f"Error unsubscribing consumer {consumer_name}: {e}")
        
        self._subscriptions.clear()
        
        # Close NATS connection
        if self._client:
            try:
                await self._client.close()
                logger.info("NATS connection closed")
            except Exception as e:
                logger.warning(f"Error closing NATS connection: {e}")
            finally:
                self._client = None
                self._jetstream = None
        
        self._status = ConsumerStatus.DISCONNECTED
        logger.info("NATS consumer service shutdown complete")
    
    def is_connected(self) -> bool:
        """Check if connected to NATS server."""
        return self._client is not None and self._client.is_connected
    
    def is_enabled(self) -> bool:
        """Check if NATS consumer is enabled."""
        return self.enabled
    
    def get_status(self) -> ConsumerStatus:
        """Get current consumer status."""
        return self._status


# Global consumer service instance
_consumer_service: Optional[NATSConsumerService] = None


def get_nats_consumer_service() -> Optional[NATSConsumerService]:
    """Get the global NATS consumer service instance."""
    global _consumer_service
    return _consumer_service


def init_nats_consumer_service(
    servers: Optional[List[str]] = None,
    enabled: Optional[bool] = None,
) -> NATSConsumerService:
    """Initialize the global NATS consumer service."""
    global _consumer_service
    
    if _consumer_service is None:
        # If enabled is not specified, check environment variables
        if enabled is None:
            enabled = os.getenv("NATS_ENABLED", "false").lower() == "true" or \
                     os.getenv("BOT_COMMAND_BUS_ENABLED", "false").lower() == "true"
        
        _consumer_service = NATSConsumerService(
            servers=servers,
            enabled=enabled,
        )
    
    return _consumer_service


async def start_nats_consumers() -> Optional[NATSConsumerService]:
    """Start the NATS consumer service and subscribe to all consumers."""
    service = get_nats_consumer_service()
    
    if service is None:
        service = init_nats_consumer_service()
    
    if not service.is_enabled():
        logger.info("NATS consumers disabled by configuration")
        return service
    
    try:
        await service.start()
        return service
    except Exception as e:
        logger.error(f"Failed to start NATS consumers: {e}")
        return None


async def shutdown_nats_consumers() -> None:
    """Shutdown the NATS consumer service."""
    service = get_nats_consumer_service()
    if service is not None:
        await service.shutdown()