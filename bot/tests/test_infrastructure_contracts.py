from __future__ import annotations

import pytest

from src.infrastructure.cache_lock import ValkeyCacheLockService
from src.infrastructure.event_bus import NatsJetStreamEventBus


def test_nats_event_bus_placeholder_fails_closed():
    bus = NatsJetStreamEventBus(enabled=False, url="nats://nats:4222")

    with pytest.raises(RuntimeError, match="not wired in Phase 1"):
        bus.publish("backtest.commands.create", {"command_id": "cmd-1"})


def test_valkey_cache_lock_placeholder_fails_closed():
    service = ValkeyCacheLockService(enabled=False, url="redis://valkey:6379/0")

    with pytest.raises(RuntimeError, match="not wired in Phase 1"):
        service.acquire_lock("lock:task:run-1", "token-1", ttl_seconds=30)
