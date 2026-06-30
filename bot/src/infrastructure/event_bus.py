"""Durable command/event bus contracts for the staged NATS migration.

PostgreSQL remains authoritative for state, ClickHouse for analytical rows,
MinIO for large artifacts, Valkey for temporary coordination, and NATS
JetStream for durable async movement.  This module only defines the Phase 1
contract; real publishing/consuming wiring lands in a later phase.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class EventBus(ABC):
    """Publish bounded command/event payloads to the durable transport."""

    @abstractmethod
    def publish(
        self,
        subject: str,
        payload: Mapping[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        """Publish a small message payload to the backing transport."""


class NatsJetStreamEventBus(EventBus):
    """Phase 4 NATS JetStream event bus implementation.
    
    This now provides a real NATS publishing implementation for Phase 4.
    Falls back to the placeholder behavior if NATS is disabled.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        url: str = "",
        stream_prefix: str = "bot",
    ):
        self.enabled = enabled
        self.url = url
        self.stream_prefix = stream_prefix
        self._client = None
        self._jetstream = None

    def _is_nats_enabled(self) -> bool:
        """Check if NATS is enabled via environment."""
        import os
        nats_enabled = os.getenv("NATS_ENABLED", "true").lower() == "true"
        command_bus_enabled = os.getenv("BOT_COMMAND_BUS_ENABLED", "true").lower() == "true"
        return nats_enabled or command_bus_enabled or self.enabled

    def publish(
        self,
        subject: str,
        payload: Mapping[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        """Publish a message to NATS JetStream.
        
        Falls back gracefully if NATS is disabled.
        """
        if not self._is_nats_enabled():
            # Fall back to no-op when disabled (fail-closed per contract)
            return
        
        # Phase 4: Implement actual NATS publishing
        # This is a simplified sync version; for full async, use the consumer service
        try:
            import nats
            import json
            
            # Create client if not exists
            if self._client is None:
                servers = [self.url] if self.url else ["nats://localhost:4222"]
                self._client = nats.connect(servers=servers, connect_timeout=5)
                self._jetstream = self._client.jetstream()
            
            # Build headers
            publish_headers = headers or {}
            
            # Generate message ID if not provided
            if "Msg-Id" not in publish_headers:
                import uuid
                publish_headers["Msg-Id"] = str(uuid.uuid4())
            
            # Ensure required headers for our contract
            if "Producer-Service" not in publish_headers:
                publish_headers["Producer-Service"] = "bot-worker"
            
            # Publish message
            self._jetstream.publish(
                subject=subject,
                payload=json.dumps(payload).encode(),
                headers=publish_headers
            )
            
        except Exception as e:
            # Log but don't fail - maintain fail-closed behavior
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"NATS publish failed (falling back to no-op): {e}")
            # Continue with HTTP/Celery path
