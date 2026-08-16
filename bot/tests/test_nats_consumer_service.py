"""Unit tests for the NATS JetStream consumer service (event_bus_nats).

Covers the full consumer lifecycle against hand-rolled fakes (no live NATS
server): connect success/failure/disabled, stream + consumer provisioning,
the message-processing loop (ack / nak / duplicate / handler failure), result
handling incl. dead-letter publishing, lifecycle (subscribe/start/shutdown),
and the module-level singleton helpers.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.infrastructure import event_bus_nats as ebn  # noqa: E402
from src.infrastructure.event_bus_nats import (  # noqa: E402
    ConsumerStatus,
    MessageAction,
    NATSConsumerService,
    ProcessedResult,
)

pytestmark = pytest.mark.asyncio


# ------------------------------------------------------------------- fakes


class _FakeMeta:
    def __init__(self, sequence: int = 1, num_delivered: int = 1):
        self.sequence = sequence
        self.num_delivered = num_delivered


class _FakeMsg:
    def __init__(
        self,
        subject: str = "backtest.command.start",
        data: Any = b"{}",
        header: Optional[Dict[str, str]] = None,
        num_delivered: int = 3,
    ):
        self.subject = subject
        self.data = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.header = header
        self.metadata = _FakeMeta(num_delivered=num_delivered)
        self.ack_count = 0
        self.nak_delays: List[Optional[float]] = []

    async def ack(self) -> None:
        self.ack_count += 1

    async def nak(self, delay: Optional[float] = None) -> None:
        self.nak_delays.append(delay)


def _async_gen(items):
    async def _gen():
        for item in items:
            yield item

    return _gen()


class _FakeSubscription:
    def __init__(self, messages):
        self.messages = _async_gen(messages)
        self.unsubscribe_count = 0

    async def unsubscribe(self) -> None:
        self.unsubscribe_count += 1


class _FakeJetStream:
    def __init__(
        self,
        *,
        stream_exists: bool = True,
        consumer_exists: bool = True,
        fail_add_stream: bool = False,
        fail_subscribe: bool = False,
        fail_publish: bool = False,
    ):
        self.stream_exists = stream_exists
        self.consumer_exists = consumer_exists
        self.fail_add_stream = fail_add_stream
        self.fail_subscribe = fail_subscribe
        self.fail_publish = fail_publish
        self.stream_info_calls: List[str] = []
        self.add_stream_calls: List[dict] = []
        self.consumer_info_calls: List[tuple] = []
        self.add_consumer_calls: List[dict] = []
        self.subscribe_calls: List[dict] = []
        self.published: List[tuple] = []

    async def stream_info(self, name: str):
        self.stream_info_calls.append(name)
        if self.stream_exists:
            return {"name": name}
        raise ebn.NatsNotFoundError(f"stream {name} not found")

    async def add_stream(self, **kwargs):
        self.add_stream_calls.append(kwargs)
        if self.fail_add_stream:
            raise RuntimeError("add_stream failed")

    async def consumer_info(self, stream: str, consumer: str):
        self.consumer_info_calls.append((stream, consumer))
        if self.consumer_exists:
            return {"name": consumer}
        raise ebn.NatsNotFoundError(f"consumer {consumer} not found")

    async def add_consumer(self, **kwargs):
        self.add_consumer_calls.append(kwargs)

    async def subscribe(self, **kwargs):
        self.subscribe_calls.append(kwargs)
        if self.fail_subscribe:
            raise RuntimeError("subscribe failed")
        return _FakeSubscription([])

    async def publish(self, subject, payload, headers=None):
        self.published.append((subject, payload, headers))
        if self.fail_publish:
            raise RuntimeError("publish failed")


class _FakeNatsClient:
    """Patched over event_bus_nats.NatsClient for connect() tests."""

    jetstream_instance: Optional[_FakeJetStream] = None
    fail_connect: bool = False
    last: Optional["_FakeNatsClient"] = None

    def __init__(self):
        self.connect_kwargs: Optional[Dict[str, Any]] = None
        self.closed = False
        self.connected_url = "nats://fake:4222"
        self.is_connected = True
        _FakeNatsClient.last = self

    async def connect(self, **kwargs):
        if _FakeNatsClient.fail_connect:
            raise ConnectionRefusedError("nats unreachable")
        self.connect_kwargs = kwargs

    def jetstream(self):
        return _FakeNatsClient.jetstream_instance

    async def close(self):
        self.closed = True


class _RecordingHandler:
    def __init__(self, result: Optional[ProcessedResult] = None, exc=None):
        self.calls: List[dict] = []
        self.result = result
        self.exc = exc

    async def handle(self, message, context):
        self.calls.append({"message": message, "context": context})
        if self.exc is not None:
            raise self.exc
        return self.result or ProcessedResult(
            action=MessageAction.ACK,
            message_id="m-1",
            idempotency_key="idem-1",
        )


def _envelope(**overrides) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "message_id": "m-1",
        "idempotency_key": "idem-1",
        "correlation_id": "corr-1",
        "subject": "backtest.command.start",
        "occurred_at": "2026-01-01T00:00:00Z",
        "producer_service": "backend",
        "schema_version": "1.0",
        "payload": {"command": "start"},
    }
    payload.update(overrides)
    return payload


def _make_service(**kwargs) -> NATSConsumerService:
    service = NATSConsumerService(enabled=True, **kwargs)
    service._jetstream = _FakeJetStream()
    return service


@pytest.fixture(autouse=True)
def _reset_module_state(monkeypatch):
    monkeypatch.setenv("NATS_ENABLED", "false")
    monkeypatch.setenv("BOT_COMMAND_BUS_ENABLED", "false")
    monkeypatch.delenv("NATS_URL", raising=False)
    monkeypatch.delenv("NATS_SERVERS", raising=False)
    _FakeNatsClient.fail_connect = False
    _FakeNatsClient.jetstream_instance = None
    saved_service = ebn._consumer_service
    ebn._consumer_service = None
    yield
    ebn._consumer_service = saved_service


# ----------------------------------------------------------------- connect


async def test_connect_success_patches_client_and_jetstream(monkeypatch):
    monkeypatch.setattr(ebn, "NatsClient", _FakeNatsClient)
    jetstream = _FakeJetStream()
    _FakeNatsClient.jetstream_instance = jetstream

    service = NATSConsumerService(
        enabled=True, servers=["nats://one:4222"], max_reconnects=-1
    )
    connected = await service.connect()

    assert connected is True
    assert service.get_status() is ConsumerStatus.CONNECTED
    client = _FakeNatsClient.last
    assert client is not None
    # max_reconnects=-1 (unlimited in our API) maps to nats-py's 60 attempts
    assert client.connect_kwargs["max_reconnect_attempts"] == 60
    assert client.connect_kwargs["servers"] == ["nats://one:4222"]
    assert client.connect_kwargs["allow_reconnect"] is True
    for callback in ("error_cb", "disconnected_cb", "closed_cb", "reconnected_cb"):
        assert callable(client.connect_kwargs[callback])
    assert service.is_connected() is True


async def test_connect_translates_explicit_reconnect_limit(monkeypatch):
    monkeypatch.setattr(ebn, "NatsClient", _FakeNatsClient)
    _FakeNatsClient.jetstream_instance = _FakeJetStream()

    service = NATSConsumerService(enabled=True, max_reconnects=5)
    assert await service.connect() is True
    assert _FakeNatsClient.last.connect_kwargs["max_reconnect_attempts"] == 5


async def test_connect_disabled_returns_false():
    service = NATSConsumerService(enabled=False)
    assert await service.connect() is False
    assert service.get_status() is ConsumerStatus.DISCONNECTED


async def test_connect_without_nats_library(monkeypatch):
    monkeypatch.setattr(ebn, "NATS_AVAILABLE", False)
    service = NATSConsumerService(enabled=True)
    # The constructor force-disables the service when nats-py is absent —
    # connect() then short-circuits on the enabled check (fail-safe)
    assert service.is_enabled() is False
    assert await service.connect() is False
    assert service.get_status() is ConsumerStatus.DISCONNECTED


async def test_connect_failure_resets_state(monkeypatch):
    monkeypatch.setattr(ebn, "NatsClient", _FakeNatsClient)
    _FakeNatsClient.fail_connect = True

    service = NATSConsumerService(enabled=True)
    assert await service.connect() is False
    assert service.get_status() is ConsumerStatus.ERROR
    assert service._client is None
    assert service.is_connected() is False


async def test_connect_is_idempotent_when_already_connected():
    service = _make_service()
    service._client = _FakeNatsClient()

    assert await service.connect() is True  # short-circuits, no new client


# -------------------------------------------------------------- callbacks


async def test_connection_callbacks_update_status(monkeypatch):
    service = _make_service()
    client = _FakeNatsClient()
    resubscribed = []

    async def _record_resubscribe():
        resubscribed.append(True)

    monkeypatch.setattr(service, "_resubscribe_all", _record_resubscribe)

    service._on_disconnect(client)
    assert service.get_status() is ConsumerStatus.DISCONNECTED

    service._on_error(client, RuntimeError("boom"))
    assert service.get_status() is ConsumerStatus.ERROR

    service._on_reconnect(client)
    assert service.get_status() is ConsumerStatus.CONNECTED
    await asyncio.sleep(0)  # let the scheduled resubscribe task run
    assert resubscribed == [True]

    service._on_close(client)
    assert service.get_status() is ConsumerStatus.DISCONNECTED


# ------------------------------------------------------- stream provisioning


async def test_ensure_stream_creates_when_missing_with_mapped_kwargs():
    service = _make_service()
    jetstream: _FakeJetStream = service._jetstream
    jetstream.stream_exists = False

    await service._ensure_stream("BACKTEST_COMMANDS")

    assert len(jetstream.add_stream_calls) == 1
    kwargs = jetstream.add_stream_calls[0]
    assert kwargs["name"] == "BACKTEST_COMMANDS"
    assert kwargs["subjects"] == ["backtest.command.>"]
    # Enums are constructed by VALUE (server-JSON spelling), not member name
    assert kwargs["retention"] is ebn.nats_api.RetentionPolicy.WORK_QUEUE
    assert kwargs["storage"] is ebn.nats_api.StorageType.FILE
    assert kwargs["duplicates"] == 2 * 60 * 60


async def test_ensure_stream_skips_when_exists():
    service = _make_service()
    jetstream: _FakeJetStream = service._jetstream

    await service._ensure_stream("BOT_EVENTS")

    assert jetstream.add_stream_calls == []
    assert jetstream.stream_info_calls == ["BOT_EVENTS"]


async def test_ensure_stream_unknown_name_and_probe_errors():
    service = _make_service()
    jetstream: _FakeJetStream = service._jetstream

    # Unknown stream name: warns and returns without creating anything
    await service._ensure_stream("NOT_CONFIGURED")
    assert jetstream.add_stream_calls == []

    # Generic probe error: aborts without creating
    async def _probe_error(name):
        raise RuntimeError("jetstream broken")

    jetstream.stream_info = _probe_error
    await service._ensure_stream("BACKTEST_COMMANDS")
    assert jetstream.add_stream_calls == []

    # Creation failure propagates (caller decides subscription fate)
    del jetstream.stream_info  # restore the normal probe behavior
    jetstream.stream_exists = False
    jetstream.fail_add_stream = True
    with pytest.raises(RuntimeError, match="add_stream failed"):
        await service._ensure_stream("BACKTEST_COMMANDS")


async def test_ensure_stream_requires_jetstream_context():
    service = NATSConsumerService(enabled=True)
    with pytest.raises(RuntimeError, match="JetStream context"):
        await service._ensure_stream("BACKTEST_COMMANDS")


# ----------------------------------------------------- consumer provisioning


async def test_ensure_consumer_creates_when_missing():
    service = _make_service()
    jetstream: _FakeJetStream = service._jetstream
    jetstream.consumer_exists = False
    config = service.CONSUMER_CONFIGS["backtest-worker"]

    await service._ensure_consumer(config)

    assert len(jetstream.add_consumer_calls) == 1
    kwargs = jetstream.add_consumer_calls[0]
    assert kwargs["stream"] == "BACKTEST_COMMANDS"
    assert kwargs["durable"] == "backtest-worker"
    assert kwargs["filter_subject"] == "backtest.command.start"
    assert kwargs["deliver_group"] == "backtest-workers"
    assert kwargs["ack_wait"] == 600


async def test_ensure_consumer_skips_or_aborts():
    service = _make_service()
    jetstream: _FakeJetStream = service._jetstream
    config = service.CONSUMER_CONFIGS["bot-worker"]

    # Existing consumer: no create call
    await service._ensure_consumer(config)
    assert jetstream.add_consumer_calls == []

    # Generic probe error: abort without creating
    async def _probe_error(stream, consumer):
        raise RuntimeError("probe failed")

    jetstream.consumer_info = _probe_error
    await service._ensure_consumer(config)
    assert jetstream.add_consumer_calls == []


async def test_ensure_consumer_requires_jetstream_context():
    service = NATSConsumerService(enabled=True)
    with pytest.raises(RuntimeError, match="JetStream context"):
        await service._ensure_consumer(service.CONSUMER_CONFIGS["bot-worker"])


# ----------------------------------------------------------- subscription


async def test_subscribe_consumer_happy_path(monkeypatch):
    service = _make_service()
    client = _FakeNatsClient()
    service._client = client
    jetstream: _FakeJetStream = service._jetstream

    # Neutralize the spawned message-processing task for this test
    async def _noop_processor(name, subscription):
        return None

    monkeypatch.setattr(service, "_process_messages", _noop_processor)

    config = service.CONSUMER_CONFIGS["backtest-worker"]
    assert await service._subscribe_consumer("backtest-worker", config) is True

    assert len(jetstream.subscribe_calls) == 1
    kwargs = jetstream.subscribe_calls[0]
    assert kwargs["subject"] == "backtest.command.start"
    assert kwargs["queue"] == "backtest-workers"
    assert kwargs["durable"] == "backtest-worker"
    assert kwargs["config"].ack_policy == ebn.nats_api.AckPolicy.EXPLICIT
    assert "backtest-worker" in service._subscriptions
    assert service.get_status() is ConsumerStatus.SUBSCRIBED
    await asyncio.sleep(0)  # let the spawned processor task finish


async def test_subscribe_consumer_failure_returns_false():
    service = _make_service()
    service._client = _FakeNatsClient()
    jetstream: _FakeJetStream = service._jetstream
    jetstream.fail_subscribe = True

    config = service.CONSUMER_CONFIGS["backtest-worker"]
    assert await service._subscribe_consumer("backtest-worker", config) is False


async def test_subscribe_consumer_requires_client_and_jetstream():
    service = NATSConsumerService(enabled=True)
    service._jetstream = _FakeJetStream()
    with pytest.raises(RuntimeError, match="NATS client not connected"):
        await service._subscribe_consumer(
            "backtest-worker", service.CONSUMER_CONFIGS["backtest-worker"]
        )


# ---------------------------------------------------- message processing


async def test_process_messages_happy_path_acks():
    service = _make_service()
    handler = _RecordingHandler(
        result=ProcessedResult(
            action=MessageAction.ACK, message_id="m-1", idempotency_key="idem-1"
        )
    )
    service.register_handler("backtest-worker", handler)

    message = _FakeMsg(data=_envelope())
    subscription = _FakeSubscription([message])

    await service._process_messages("backtest-worker", subscription)

    assert message.ack_count == 1
    assert message.nak_delays == []
    assert len(handler.calls) == 1
    call = handler.calls[0]
    assert call["message"] == {"command": "start"}  # envelope payload only
    context = call["context"]
    assert context["consumer_name"] == "backtest-worker"
    assert context["subject"] == "backtest.command.start"
    assert context["message_id"] == "m-1"
    assert context["idempotency_key"] == "idem-1"
    assert context["nats_message"] is message
    assert context["raw_payload"]["producer_service"] == "backend"


async def test_process_messages_invalid_json_naks():
    service = _make_service()
    service.register_handler("backtest-worker", _RecordingHandler())

    message = _FakeMsg(data=b"not-json{")
    await service._process_messages("backtest-worker", _FakeSubscription([message]))

    assert message.nak_delays == [None]
    assert message.ack_count == 0


async def test_process_messages_invalid_envelope_naks():
    service = _make_service()
    handler = _RecordingHandler()
    service.register_handler("backtest-worker", handler)

    message = _FakeMsg(data={"unexpected": "shape"})
    await service._process_messages("backtest-worker", _FakeSubscription([message]))

    assert message.nak_delays == [None]
    assert handler.calls == []


async def test_process_messages_duplicate_acks_without_handler_call(monkeypatch):
    service = _make_service()
    service.set_task_repository(object())  # enables the duplicate check
    handler = _RecordingHandler()
    service.register_handler("backtest-worker", handler)

    async def _always_duplicate(envelope):
        return True

    monkeypatch.setattr(service, "_check_duplicate", _always_duplicate)

    message = _FakeMsg(data=_envelope())
    await service._process_messages("backtest-worker", _FakeSubscription([message]))

    assert message.ack_count == 1
    assert handler.calls == []


async def test_process_messages_handler_exception_naks():
    service = _make_service()
    service.register_handler(
        "backtest-worker",
        _RecordingHandler(exc=RuntimeError("handler exploded")),
    )

    message = _FakeMsg(data=_envelope())
    await service._process_messages("backtest-worker", _FakeSubscription([message]))

    assert message.nak_delays == [None]


async def test_process_messages_without_handler_or_config_returns():
    service = _make_service()

    # No handler registered: returns before consuming anything
    await service._process_messages("backtest-worker", _FakeSubscription([]))

    # Handler registered but no consumer config: also returns
    service.register_handler("ghost", _RecordingHandler())
    await service._process_messages("ghost", _FakeSubscription([]))


# ------------------------------------------------------------ envelope


def test_extract_envelope_accepts_direct_and_nested_forms():
    service = _make_service()

    envelope = _envelope()
    assert service._extract_envelope(envelope) is envelope

    nested = _envelope()
    assert service._extract_envelope({"payload": nested}) is nested

    assert service._extract_envelope("not-a-dict") is None
    assert service._extract_envelope({"payload": {"message_id": "only-one"}}) is None


# ------------------------------------------------------- duplicate checking


async def test_check_duplicate_terminal_statuses(monkeypatch):
    service = _make_service()

    class _Result:
        def __init__(self, row):
            self._row = row

        def fetchone(self):
            return self._row

    class _Session:
        def __init__(self, row):
            self._row = row
            self.params = None

        def execute(self, query, params):
            self.params = params
            return _Result(self._row)

    class _DB:
        def __init__(self, row):
            self._session = _Session(row)

        def get_session(self):
            return self._session

    for status in ("published", "completed", "failed"):
        db = _DB(("cmd-1", status))
        monkeypatch.setattr(ebn, "db", db)
        assert await service._check_duplicate(_envelope()) is True
        assert db._session.params == {"idempotency_key": "idem-1"}

    # Non-terminal status and no row at all are NOT duplicates
    monkeypatch.setattr(ebn, "db", _DB(("cmd-1", "pending")))
    assert await service._check_duplicate(_envelope()) is False
    monkeypatch.setattr(ebn, "db", _DB(None))
    assert await service._check_duplicate(_envelope()) is False


async def test_check_duplicate_missing_keys_and_errors(monkeypatch):
    service = _make_service()

    # Missing idempotency key / message id short-circuit to False
    assert await service._check_duplicate({"message_id": "m"}) is False
    assert await service._check_duplicate({"idempotency_key": "k"}) is False

    class _BrokenDB:
        def get_session(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(ebn, "db", _BrokenDB())
    # Fail open: processing continues rather than blocking on a DB error
    assert await service._check_duplicate(_envelope()) is False


# --------------------------------------------------------- result handling


async def test_handle_result_dispatches_all_actions():
    service = _make_service()

    ack_msg = _FakeMsg()
    await service._handle_result(
        ack_msg,
        ProcessedResult(action=MessageAction.ACK, message_id="a", idempotency_key="k"),
    )
    assert ack_msg.ack_count == 1

    nak_msg = _FakeMsg()
    await service._handle_result(
        nak_msg,
        ProcessedResult(
            action=MessageAction.NAK,
            message_id="b",
            idempotency_key="k",
            error_message="nope",
        ),
    )
    assert nak_msg.nak_delays == [None]

    requeue_msg = _FakeMsg()
    await service._handle_result(
        requeue_msg,
        ProcessedResult(
            action=MessageAction.REQUEUE,
            message_id="c",
            idempotency_key="k",
            requeue_delay_seconds=17,
        ),
    )
    assert requeue_msg.nak_delays == [17]

    unknown_msg = _FakeMsg()
    await service._handle_result(
        unknown_msg,
        ProcessedResult(action="bogus", message_id="d", idempotency_key="k"),  # type: ignore[arg-type]
    )
    assert unknown_msg.nak_delays == [None]


class _ExplodingMsg(_FakeMsg):
    async def ack(self) -> None:
        raise RuntimeError("ack refused")

    async def nak(self, delay=None) -> None:
        raise RuntimeError("nak refused")


async def test_handle_result_swallows_ack_failures():
    service = _make_service()
    # Must not raise even when the transport rejects the ack
    await service._handle_result(
        _ExplodingMsg(),
        ProcessedResult(action=MessageAction.ACK, message_id="x", idempotency_key="k"),
    )


# --------------------------------------------------------- dead letter


async def test_move_to_dead_letter_publishes_and_acks():
    service = _make_service()
    jetstream: _FakeJetStream = service._jetstream

    message = _FakeMsg(
        subject="backtest.command.start",
        data=_envelope(),
        header={"Producer-Service": "backend"},
        num_delivered=4,
    )
    result = ProcessedResult(
        action=MessageAction.DEAD_LETTER,
        message_id="m-1",
        idempotency_key="idem-1",
        error_message="too many deliveries",
        consumer_name="backtest-worker",
    )

    await service._move_to_dead_letter(message, result)

    assert len(jetstream.published) == 1
    subject, payload, headers = jetstream.published[0]
    assert subject == "deadletter.backtest_command_start"
    body = json.loads(payload)
    assert body["original_stream"] == "BACKTEST_COMMANDS"
    assert body["original_subject"] == "backtest.command.start"
    assert body["delivery_count"] == 4
    assert body["error_message"] == "too many deliveries"
    # The original payload is carried as the raw (encoded) message body
    original = json.loads(body["original_payload"])
    assert original["idempotency_key"] == "idem-1"
    assert headers["Msg-Id"] == "m-1"
    assert headers["Delivery-Count"] == "4"
    assert message.ack_count == 1  # acked after successful move


async def test_move_to_dead_letter_naks_without_jetstream_or_on_failure():
    service = NATSConsumerService(enabled=True)
    message = _FakeMsg()
    result = ProcessedResult(
        action=MessageAction.DEAD_LETTER, message_id="m", idempotency_key="k"
    )
    await service._move_to_dead_letter(message, result)
    assert message.nak_delays == [None]

    service2 = _make_service()
    jetstream: _FakeJetStream = service2._jetstream
    jetstream.fail_publish = True
    message2 = _FakeMsg()
    await service2._move_to_dead_letter(message2, result)
    assert message2.nak_delays == [None]


# --------------------------------------------------- stream name mapping


def test_get_stream_name_families():
    service = _make_service()

    assert service._get_stream_name("backtest.event.completed") == "BACKTEST_EVENTS"
    assert service._get_stream_name("bot.event.started") == "BOT_EVENTS"
    assert service._get_stream_name("worker.event.heartbeat") == "WORKER_EVENTS"
    assert service._get_stream_name("system.audit.login") == "SYSTEM_AUDIT"
    assert service._get_stream_name("deadletter.foo") == "DEAD_LETTER"
    assert service._get_stream_name("unmapped.thing") == "UNKNOWN"


# ----------------------------------------------------------- lifecycle


async def test_subscribe_backtest_commands_paths(monkeypatch):
    # Disabled: no-op
    disabled = NATSConsumerService(enabled=False)
    assert await disabled.subscribe_backtest_commands() is False

    # Connect failure: aborts
    monkeypatch.setattr(ebn, "NatsClient", _FakeNatsClient)
    _FakeNatsClient.fail_connect = True
    failing = NATSConsumerService(enabled=True)
    assert await failing.subscribe_backtest_commands() is False

    # Happy path
    service = _make_service()
    monkeypatch.setattr(ebn, "NatsClient", _FakeNatsClient)
    _FakeNatsClient.fail_connect = False
    _FakeNatsClient.jetstream_instance = service._jetstream
    assert await service.subscribe_backtest_commands() is True
    assert service._jetstream.subscribe_calls  # consumer subscribed


async def test_subscribe_all_reports_per_consumer_outcome(monkeypatch):
    service = _make_service()
    service._client = _FakeNatsClient()
    jetstream: _FakeJetStream = service._jetstream

    async def _noop_processor(name, subscription):
        return None

    monkeypatch.setattr(service, "_process_messages", _noop_processor)
    # Make the SECOND configured consumer's subscribe call fail
    configs = list(service._consumer_configs)
    original_subscribe = jetstream.subscribe
    calls = {"n": 0}

    async def _flaky_subscribe(**kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("second consumer broke")
        return await original_subscribe(**kwargs)

    jetstream.subscribe = _flaky_subscribe
    results = await service.subscribe_all()

    assert set(results) == set(configs)
    assert len([ok for ok in results.values() if ok]) == len(configs) - 1
    await asyncio.sleep(0)


async def test_start_lifecycle(monkeypatch):
    disabled = NATSConsumerService(enabled=False)
    assert await disabled.start() is False

    monkeypatch.setattr(ebn, "NatsClient", _FakeNatsClient)
    _FakeNatsClient.fail_connect = True
    unreachable = NATSConsumerService(enabled=True)
    assert await unreachable.start() is False

    service = _make_service()
    _FakeNatsClient.fail_connect = False
    _FakeNatsClient.jetstream_instance = service._jetstream

    async def _noop_processor(name, subscription):
        return None

    monkeypatch.setattr(service, "_process_messages", _noop_processor)
    assert await service.start() is True
    await asyncio.sleep(0)


async def test_shutdown_unsubscribes_and_closes():
    service = _make_service()
    client = _FakeNatsClient()
    service._client = client
    subscription = _FakeSubscription([])
    service._subscriptions["backtest-worker"] = subscription

    await service.shutdown()

    assert subscription.unsubscribe_count == 1
    assert client.closed is True
    assert service._subscriptions == {}
    assert service._client is None
    assert service._jetstream is None
    assert service.get_status() is ConsumerStatus.DISCONNECTED


async def test_shutdown_swallows_cleanup_errors():
    service = _make_service()

    class _BadSubscription:
        async def unsubscribe(self):
            raise RuntimeError("unsubscribe failed")

    class _BadClient:
        async def close(self):
            raise RuntimeError("close failed")

    service._subscriptions["backtest-worker"] = _BadSubscription()
    service._client = _BadClient()

    await service.shutdown()  # must not raise
    assert service._client is None


# --------------------------------------------------- module-level helpers


async def test_singleton_init_get_start_shutdown(monkeypatch):
    assert ebn.get_nats_consumer_service() is None

    # Disabled by env: start is a no-op that still returns the service
    service = ebn.init_nats_consumer_service()
    assert ebn.get_nats_consumer_service() is service
    returned = await ebn.start_nats_consumers()
    assert returned is service
    assert service.is_enabled() is False

    await ebn.shutdown_nats_consumers()

    # No service initialized: shutdown is a safe no-op
    ebn._consumer_service = None
    await ebn.shutdown_nats_consumers()


async def test_start_nats_consumers_enabled_starts_or_fails(monkeypatch):
    monkeypatch.setenv("NATS_ENABLED", "true")
    ebn._consumer_service = None

    # Connect failure: start() returns False without raising, and the helper
    # still returns the service so callers can inspect its status
    monkeypatch.setattr(ebn, "NatsClient", _FakeNatsClient)
    _FakeNatsClient.fail_connect = True
    service = await ebn.start_nats_consumers()
    assert service is not None
    assert service.get_status() is ConsumerStatus.ERROR

    # An exception inside start() maps to None (never propagates)
    real_start = NATSConsumerService.start

    async def _exploding_start(self):
        raise RuntimeError("start exploded")

    monkeypatch.setattr(NATSConsumerService, "start", _exploding_start)
    assert await ebn.start_nats_consumers() is None

    # Happy path: restore the real start, make the client connectable
    monkeypatch.setattr(NATSConsumerService, "start", real_start)
    _FakeNatsClient.fail_connect = False
    _FakeNatsClient.jetstream_instance = _FakeJetStream()
    service = await ebn.start_nats_consumers()
    assert service is not None
    assert service.get_status() is not ConsumerStatus.ERROR
    await asyncio.sleep(0)
