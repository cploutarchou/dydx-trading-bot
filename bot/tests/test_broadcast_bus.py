"""Tests for the cross-worker WebSocket broadcast bus (``src/infrastructure/broadcast``).

Mirrors the conventions of ``tests/test_market_data_cache.py``: plain sync test
functions that drive the async API through ``asyncio.run``, with an in-memory
fake async-redis client (no live Redis required).
"""

import asyncio
import json

from src.infrastructure.broadcast import (
    NoopBroadcastBus,
    RedisBroadcastBus,
)
from src.infrastructure.broadcast import bus as broadcast_module
from src.infrastructure.broadcast import (
    get_broadcast_bus,
    reset_broadcast_bus,
)

# ── Fakes for the redis.asyncio client + pubsub ───────────────────────────────


class _FakePubSub:
    """In-memory stand-in for ``redis.asyncio.client.PubSub``."""

    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.subscribed: list[str] = []
        self.closed = False
        self.aclose_calls = 0

    async def subscribe(self, *channels):
        self.subscribed.extend(str(c) for c in channels)

    async def listen(self):
        while not self.closed:
            msg = await self.queue.get()
            if msg is None:  # aclose() sentinel
                return
            yield msg

    async def aclose(self):
        self.aclose_calls += 1
        self.closed = True
        await self.queue.put(None)  # unblock a pending get()


class _FakeRedis:
    """In-memory stand-in for ``redis.asyncio.Redis``."""

    def __init__(self, *, fail_publish=False, fail_ping=False, fail_publish_first=0):
        self.published: list[tuple[str, str]] = []
        self.fail_publish = fail_publish
        self.fail_ping = fail_ping
        # Fail only the first N publish() calls, then succeed — drives the
        # publish failure circuit's open/reset/probe transitions.
        self.fail_publish_first = fail_publish_first
        self.publish_calls = 0
        self.pubsubs: list[_FakePubSub] = []

    def pubsub(self):
        ps = _FakePubSub()
        self.pubsubs.append(ps)
        return ps

    async def publish(self, channel, payload):
        self.publish_calls += 1
        if self.fail_publish or (
            self.fail_publish_first and self.publish_calls <= self.fail_publish_first
        ):
            raise RuntimeError("publish boom")
        self.published.append((channel, payload))

    async def ping(self):
        if self.fail_ping:
            raise RuntimeError("ping boom")
        return True

    async def aclose(self):
        return None

    def push_message(self, msg):
        """Deliver a raw pub/sub message dict to every created pubsub."""
        for ps in self.pubsubs:
            ps.queue.put_nowait(msg)


async def _settle():
    """Yield control so the background listener task can run, then pause briefly."""
    for _ in range(20):
        await asyncio.sleep(0)
    await asyncio.sleep(0.02)


def _msg(origin, channel, message):
    return {
        "type": "message",
        "channel": "ws:broadcast",
        "data": json.dumps({"channel": channel, "message": message, "origin": origin}),
    }


# ── Noop bus ──────────────────────────────────────────────────────────────────


def test_noop_bus_is_inert():
    bus = NoopBroadcastBus()
    asyncio.run(bus.publish("ch", {"x": 1}))  # must not raise

    async def _dispatch(channel, message):  # pragma: no cover - never invoked
        return None

    asyncio.run(bus.start(_dispatch))
    asyncio.run(bus.stop())
    asyncio.run(bus.aclose())
    assert asyncio.run(bus.health()) == {
        "enabled": False,
        "backend": "noop",
        "healthy": True,
        "error": None,
        "worker_id": None,
        "listening": False,
    }


# ── Factory / singleton ───────────────────────────────────────────────────────


def test_factory_disabled_returns_noop(monkeypatch):
    monkeypatch.setattr(broadcast_module, "WS_BROADCAST_ENABLED", False)
    reset_broadcast_bus()
    try:
        assert isinstance(get_broadcast_bus(), NoopBroadcastBus)
    finally:
        reset_broadcast_bus()


def test_factory_no_url_returns_noop(monkeypatch):
    monkeypatch.setattr(broadcast_module, "WS_BROADCAST_ENABLED", True)
    monkeypatch.setattr(broadcast_module, "WS_BROADCAST_REDIS_URL", "")
    monkeypatch.setattr(broadcast_module, "redis_url", lambda **_kw: "")
    reset_broadcast_bus()
    try:
        assert isinstance(get_broadcast_bus(), NoopBroadcastBus)
    finally:
        reset_broadcast_bus()


def test_factory_enabled_with_url_builds_redis(monkeypatch):
    monkeypatch.setattr(broadcast_module, "WS_BROADCAST_ENABLED", True)
    monkeypatch.setattr(
        broadcast_module, "WS_BROADCAST_REDIS_URL", "redis://localhost:6379/0"
    )
    reset_broadcast_bus()
    try:
        assert isinstance(get_broadcast_bus(), RedisBroadcastBus)
    finally:
        reset_broadcast_bus()


# ── publish / decode / health (no listener) ───────────────────────────────────


def test_publish_encodes_envelope_with_origin():
    fake = _FakeRedis()
    bus = RedisBroadcastBus(
        url="redis://localhost:6379/0", worker_id="worker-A", client=fake
    )
    asyncio.run(bus.publish("bot-42", {"type": "position_opened", "value": 1}))
    assert len(fake.published) == 1
    channel, payload = fake.published[0]
    assert channel == "ws:broadcast"
    assert json.loads(payload) == {
        "channel": "bot-42",
        "message": {"type": "position_opened", "value": 1},
        "origin": "worker-A",
    }


def test_publish_swallows_errors():
    fake = _FakeRedis(fail_publish=True)
    bus = RedisBroadcastBus(url="redis://localhost:6379/0", worker_id="w", client=fake)
    asyncio.run(bus.publish("ch", {"x": 1}))  # must not raise
    assert fake.published == []


def test_publish_swallows_serialization_errors():
    """A non-JSON-serializable message must not raise (publish is non-raising)."""
    fake = _FakeRedis()
    bus = RedisBroadcastBus(url="redis://localhost:6379/0", worker_id="w", client=fake)

    class _NotSerializable:
        pass

    asyncio.run(bus.publish("ch", {"bad": _NotSerializable()}))  # must not raise
    assert fake.published == []  # json.dumps failed → nothing published


def test_health_redis_ok_and_down():
    ok = RedisBroadcastBus(
        url="redis://localhost:6379/0", worker_id="w", client=_FakeRedis()
    )
    health = asyncio.run(ok.health())
    assert health["enabled"] is True
    assert health["backend"] == "redis"
    assert health["healthy"] is True
    assert health["error"] is None
    assert health["worker_id"] == "w"
    assert health["listening"] is False

    sick = RedisBroadcastBus(
        url="redis://localhost:6379/0", worker_id="w", client=_FakeRedis(fail_ping=True)
    )
    health = asyncio.run(sick.health())
    assert health["healthy"] is False
    assert health["error"]


def test_decode_garbage_returns_none():
    assert RedisBroadcastBus._decode(None) is None
    assert RedisBroadcastBus._decode("") is None
    assert RedisBroadcastBus._decode("not-json{") is None
    assert RedisBroadcastBus._decode(json.dumps([1, 2, 3])) is None  # not a dict
    assert RedisBroadcastBus._decode(json.dumps({"channel": "c"})) == {"channel": "c"}


# ── Listener scenarios ────────────────────────────────────────────────────────


def _run_listener(fake, worker_id, messages):
    """Start a bus with the fake client, push ``messages``, return deliveries."""

    async def _scenario():
        bus = RedisBroadcastBus(
            url="redis://localhost:6379/0", worker_id=worker_id, client=fake
        )
        delivered = []

        async def dispatch(channel, message):
            delivered.append((channel, message))

        await bus.start(dispatch)
        await _settle()
        assert fake.pubsubs, "listener never created a pubsub"
        assert fake.pubsubs[0].subscribed == ["ws:broadcast"]
        for msg in messages:
            fake.push_message(msg)
        await _settle()
        await bus.stop()
        return delivered, bus

    return asyncio.run(_scenario())


def test_listener_dispatches_remote_messages():
    fake = _FakeRedis()
    delivered, _ = _run_listener(
        fake,
        "me",
        [
            # subscribe-ack must be ignored
            {"type": "subscribe", "channel": "ws:broadcast", "data": 1},
            _msg("other", "bot-1", {"hi": 1}),
        ],
    )
    assert delivered == [("bot-1", {"hi": 1})]


def test_listener_skips_self_origin():
    fake = _FakeRedis()
    delivered, _ = _run_listener(fake, "me", [_msg("me", "bot-1", {"hi": 1})])
    assert delivered == []  # own origin suppressed → no double delivery


def test_listener_ignores_malformed_payloads():
    fake = _FakeRedis()
    delivered, _ = _run_listener(
        fake,
        "me",
        [
            {"type": "message", "data": "not-json"},
            {"type": "message", "data": json.dumps([1, 2])},  # not a dict
            {"type": "message", "data": json.dumps({"channel": "c"})},  # no message
            _msg("other", "c", {"ok": True}),
        ],
    )
    assert delivered == [("c", {"ok": True})]


def test_listener_survives_dispatch_failure():
    fake = _FakeRedis()

    async def _scenario():
        bus = RedisBroadcastBus(
            url="redis://localhost:6379/0", worker_id="me", client=fake
        )
        calls = []

        async def dispatch(channel, message):
            calls.append((channel, message))
            if len(calls) == 1:
                raise RuntimeError("bad dispatch")

        await bus.start(dispatch)
        await _settle()
        fake.push_message(_msg("other", "c", {"a": 1}))
        fake.push_message(_msg("other", "c", {"b": 2}))
        await _settle()
        await bus.stop()
        return calls

    calls = asyncio.run(_scenario())
    # The first dispatch raised but the listener kept going and delivered the second.
    assert len(calls) == 2


# ── Operational metrics ────────────────────────────────────────────────────────


def test_listener_metrics_count_the_full_path():
    fake = _FakeRedis()
    delivered, bus = _run_listener(
        fake,
        "me",
        [
            _msg("other", "bot-1", {"hi": 1}),  # delivered
            _msg("me", "bot-2", {"hi": 2}),  # self-suppressed
            {"type": "message", "data": "not-json"},  # decode error
            {"type": "message", "data": json.dumps([1, 2])},  # decode error
            {"type": "message", "data": json.dumps({"channel": "c"})},  # no message
        ],
    )
    assert delivered == [("bot-1", {"hi": 1})]
    m = bus._metrics
    assert m["received"] == 5
    assert m["dispatched"] == 1
    assert m["self_suppressed"] == 1
    assert m["decode_errors"] == 2
    assert m["dispatch_errors"] == 0
    assert m["dispatch_timeouts"] == 0


def test_publish_metrics_count_success_and_error():
    ok = _FakeRedis()
    ok_bus = RedisBroadcastBus(url="redis://localhost:6379/0", worker_id="w", client=ok)
    asyncio.run(ok_bus.publish("c", {"x": 1}))
    assert ok_bus._metrics["published"] == 1
    assert ok_bus._metrics["publish_errors"] == 0

    sick = _FakeRedis(fail_publish=True)
    sick_bus = RedisBroadcastBus(
        url="redis://localhost:6379/0", worker_id="w", client=sick
    )
    asyncio.run(sick_bus.publish("c", {"x": 1}))
    assert sick_bus._metrics["published"] == 0
    assert sick_bus._metrics["publish_errors"] == 1


# ── Publish failure circuit ───────────────────────────────────────────────────


def test_publish_circuit_opens_after_consecutive_failures():
    """After the threshold, publishes are skipped outright (no client call)."""
    fake = _FakeRedis(fail_publish=True)
    bus = RedisBroadcastBus(
        url="redis://localhost:6379/0",
        worker_id="w",
        client=fake,
        publish_failure_threshold=3,
        publish_pause_seconds=60.0,
    )

    async def _scenario():
        for _ in range(3):  # 3 consecutive failures → circuit opens
            await bus.publish("c", {"x": 1})
        for _ in range(5):  # paused: skipped without touching the client
            await bus.publish("c", {"x": 1})
        return await bus.health()

    health = asyncio.run(_scenario())
    assert fake.publish_calls == 3
    m = bus._metrics
    assert m["publish_errors"] == 3
    assert m["publish_suppressed"] == 5
    assert m["publish_pauses"] == 1
    assert health["publish_paused"] is True


def test_publish_circuit_streak_resets_on_success():
    """Failures below the threshold, interrupted by a success, never open it."""
    fake = _FakeRedis(fail_publish_first=2)  # calls 1-2 fail, 3+ succeed
    bus = RedisBroadcastBus(
        url="redis://localhost:6379/0",
        worker_id="w",
        client=fake,
        publish_failure_threshold=3,
        publish_pause_seconds=60.0,
    )

    async def _scenario():
        await bus.publish("c", {"x": 1})  # failure 1
        await bus.publish("c", {"x": 2})  # failure 2
        await bus.publish("c", {"x": 3})  # success → streak reset
        await bus.publish("c", {"x": 4})  # success
        await bus.publish("c", {"x": 5})  # success
        return await bus.health()

    health = asyncio.run(_scenario())
    assert fake.publish_calls == 5
    assert len(fake.published) == 3
    m = bus._metrics
    assert m["publish_errors"] == 2
    assert m["publish_suppressed"] == 0
    assert m["publish_pauses"] == 0
    assert health["publish_paused"] is False


def test_publish_circuit_probes_again_after_pause_window():
    """The circuit half-opens when the pause elapses; success closes it."""
    fake = _FakeRedis(fail_publish_first=1)  # call 1 fails, 2+ succeed
    bus = RedisBroadcastBus(
        url="redis://localhost:6379/0",
        worker_id="w",
        client=fake,
        publish_failure_threshold=1,
        publish_pause_seconds=0.02,
    )

    async def _scenario():
        await bus.publish("c", {"x": 1})  # failure → immediately paused
        await bus.publish("c", {"x": 2})  # suppressed
        assert fake.publish_calls == 1
        await asyncio.sleep(0.05)  # pause window elapses → half-open probe
        await bus.publish("c", {"x": 3})  # probe succeeds → circuit closed
        await bus.publish("c", {"x": 4})  # straight through again
        return await bus.health()

    health = asyncio.run(_scenario())
    assert fake.publish_calls == 3
    assert len(fake.published) == 2
    m = bus._metrics
    assert m["publish_suppressed"] == 1
    assert m["publish_pauses"] == 1
    assert health["publish_paused"] is False


def test_dispatch_timeout_is_counted_and_listener_continues():
    fake = _FakeRedis()

    async def _scenario():
        bus = RedisBroadcastBus(
            url="redis://localhost:6379/0",
            worker_id="me",
            client=fake,
            dispatch_timeout=0.05,
        )
        delivered = []

        async def dispatch(channel, message):
            if message.get("slow"):
                await asyncio.sleep(1.0)  # exceeds the 0.05s bound
            delivered.append((channel, message))

        await bus.start(dispatch)
        await _settle()
        fake.push_message(_msg("other", "c", {"slow": True}))
        fake.push_message(_msg("other", "c", {"slow": False}))
        # Long enough for the timeout to fire, short enough to stay snappy.
        await asyncio.sleep(0.2)
        await bus.stop()
        return delivered, bus

    delivered, bus = asyncio.run(_scenario())
    # The stuck dispatch was cancelled+counted; the next message still delivered.
    assert delivered == [("c", {"slow": False})]
    assert bus._metrics["dispatch_timeouts"] == 1
    assert bus._metrics["dispatched"] == 1


def test_stop_closes_pubsub_and_is_idempotent():
    fake = _FakeRedis()

    async def _scenario():
        bus = RedisBroadcastBus(
            url="redis://localhost:6379/0", worker_id="me", client=fake
        )

        async def dispatch(channel, message):  # pragma: no cover - no messages
            return None

        await bus.start(dispatch)
        await _settle()
        assert fake.pubsubs[0].aclose_calls == 0
        await bus.stop()
        await bus.stop()  # idempotent — must not raise
        await bus.aclose()
        await bus.aclose()  # idempotent — must not raise
        return fake.pubsubs[0].aclose_calls

    aclose_calls = asyncio.run(_scenario())
    assert aclose_calls >= 1


# ── ConnectionManager integration (producer + subscriber paths) ───────────────


class _FakeWS:
    def __init__(self):
        self.sent = []

    async def send_json(self, message):
        self.sent.append(message)


def test_broadcast_to_bot_delivers_locally_with_noop_bus():
    """With the default Noop bus, broadcast_to_bot is identical to local-only."""
    from src.api.websocket_server import ConnectionManager

    mgr = ConnectionManager()
    ws = _FakeWS()
    mgr.active_connections["bot-1"] = {ws}

    asyncio.run(mgr.broadcast_to_bot("bot-1", {"type": "ping"}))

    assert ws.sent == [{"type": "ping"}]


def test_broadcast_to_bot_publishes_even_with_no_local_clients(monkeypatch):
    """A producer must publish even when it has zero local clients (other workers may)."""
    from src.api import websocket_server
    from src.api.websocket_server import ConnectionManager

    published = []

    class _RecordingBus:
        async def publish(self, channel, message):
            published.append((channel, message))

    monkeypatch.setattr(websocket_server, "get_broadcast_bus", lambda: _RecordingBus())

    mgr = ConnectionManager()  # no local connections for "bot-9"
    asyncio.run(mgr.broadcast_to_bot("bot-9", {"type": "y"}))

    assert published == [("bot-9", {"type": "y"})]


def test_deliver_local_broadcast_does_not_republish(monkeypatch):
    """The subscriber callback must deliver locally but NOT re-publish (loop guard)."""
    from src.api import websocket_server
    from src.api.websocket_server import ConnectionManager

    published = []

    class _RecordingBus:
        async def publish(self, channel, message):
            published.append((channel, message))

    monkeypatch.setattr(websocket_server, "get_broadcast_bus", lambda: _RecordingBus())

    mgr = ConnectionManager()
    ws = _FakeWS()
    mgr.active_connections["bot-2"] = {ws}

    asyncio.run(mgr.deliver_local_broadcast("bot-2", {"type": "x"}))

    assert ws.sent == [{"type": "x"}]  # delivered locally
    assert published == []  # …but NOT re-published → no fan-out loop
