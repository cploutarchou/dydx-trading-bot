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
    """Phase 1 placeholder for the future JetStream-backed implementation."""

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

    def publish(
        self,
        subject: str,
        payload: Mapping[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        del subject, payload, headers
        raise RuntimeError(
            "NATS JetStream event bus is not wired in Phase 1. "
            "Keep the current HTTP/Celery execution path until Phase 4."
        )
