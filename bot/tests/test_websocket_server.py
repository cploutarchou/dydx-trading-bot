import asyncio
import time
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import WebSocketDisconnect

from src.api import websocket_server
from src.api.websocket_server import ConnectionManager, WebSocketEvents, WebSocketServer


class _DummyWebSocket:
    def __init__(self) -> None:
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


class _DummySession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FailingWebSocket:
    async def send_json(self, _message):
        raise RuntimeError("socket not connected")


class _DisconnectingWebSocket:
    async def send_json(self, _message):
        raise WebSocketDisconnect()


class _AcceptingDummyWebSocket:
    async def accept(self):
        return None


def test_send_initial_state_backtest_channel_emits_snapshot(monkeypatch):
    session = _DummySession()

    monkeypatch.setattr(websocket_server.db, "get_session", lambda: session)

    class _FakeRepository:
        def __init__(self, db_session):
            assert db_session is session

        def get_run_overview(self, run_id: str):
            assert run_id == "run-123"
            return {
                "status": "running",
                "progress_pct": 37.5,
                "current_pair": "BTC-USD/ETH-USD",
                "current_task": "scanning pairs",
                "updated_at": "2026-04-08T20:41:16Z",
            }

    monkeypatch.setattr(websocket_server, "BacktestRepository", _FakeRepository)

    ws = _DummyWebSocket()
    asyncio.run(
        websocket_server.WebSocketServer.send_initial_state(
            cast(Any, ws), "backtest-run-123"
        )
    )

    assert session.closed is True
    assert len(ws.messages) == 2

    progress_payload = ws.messages[0]
    assert progress_payload["type"] == "backtest_progress"
    assert progress_payload["run_id"] == "run-123"
    assert progress_payload["status"] == "running"
    assert progress_payload["progress_pct"] == 37.5
    assert progress_payload["progress"] == 37.5
    assert progress_payload["current_pair"] == "BTC-USD/ETH-USD"
    assert progress_payload["current_task"] == "scanning pairs"
    assert progress_payload["details"]["source"] == "initial_state"

    log_payload = ws.messages[1]
    assert log_payload["type"] == "backtest_log"
    assert log_payload["run_id"] == "run-123"
    assert log_payload["level"] == "info"
    assert log_payload["message"] == "scanning pairs: BTC-USD/ETH-USD"


def test_handle_message_request_status_uses_backtest_run_id(monkeypatch):
    calls = []

    async def _fake_send_backtest_status(websocket, run_id: str):
        calls.append((websocket, run_id))

    monkeypatch.setattr(
        websocket_server.WebSocketServer,
        "send_backtest_status",
        staticmethod(_fake_send_backtest_status),
    )

    ws = _DummyWebSocket()
    asyncio.run(
        websocket_server.WebSocketServer.handle_message(
            cast(Any, ws),
            "backtest-run-456",
            {"type": "request_status"},
        )
    )

    assert calls == [(ws, "run-456")]


def test_send_stats_resolves_string_instance_id_to_numeric_bot_id(monkeypatch):
    class _DummyStats:
        total_open_positions = 2
        total_unrealized_pnl = 11.5
        total_unrealized_pnl_pct = 0.7
        daily_pnl = 3.2
        daily_pnl_pct = 0.2
        daily_trades_opened = 1
        daily_trades_closed = 1
        daily_win_rate = 1.0
        max_drawdown_session = 0
        current_drawdown = 0

    class _FakeRealtimeUow:
        def __init__(self, _session):
            class _StatsRepo:
                def get_stats(self, bot_id):
                    assert bot_id == 42
                    return _DummyStats()

            self.stats = _StatsRepo()

    class _FakeCoreUow:
        def __init__(self, _session):
            class _BotsRepo:
                def get_by_instance_id(self, instance_id):
                    assert instance_id == "strategy-1-9"

                    class _Bot:
                        id = 42

                    return _Bot()

            self.bots = _BotsRepo()

    sent_messages = []

    async def _fake_send_personal_message(message, _websocket):
        sent_messages.append(message)

    monkeypatch.setattr(websocket_server.db, "get_session", lambda: _DummySession())
    monkeypatch.setattr(websocket_server, "UnitOfWork", _FakeCoreUow)
    monkeypatch.setattr(websocket_server, "UnitOfWorkRealtime", _FakeRealtimeUow)
    monkeypatch.setattr(
        websocket_server.manager, "send_personal_message", _fake_send_personal_message
    )

    ws = _DummyWebSocket()
    asyncio.run(
        websocket_server.WebSocketServer.send_stats(cast(Any, ws), "strategy-1-9")
    )

    assert len(sent_messages) == 1
    assert sent_messages[0]["type"] == "stats"
    assert sent_messages[0]["data"]["total_open_positions"] == 2
    assert sent_messages[0]["data"]["daily_trades_opened"] == 1


def test_send_backtest_status_tracks_per_run_send_failures(monkeypatch):
    session = _DummySession()
    websocket_server.manager.send_metrics.clear()
    monkeypatch.setenv("BACKTEST_WS_FAILURE_ALERT_THRESHOLD", "1")
    monkeypatch.setattr(websocket_server.db, "get_session", lambda: session)

    class _FakeRepository:
        def __init__(self, db_session):
            assert db_session is session

        def get_run_overview(self, run_id: str):
            assert run_id == "run-metrics"
            return {
                "status": "running",
                "progress_pct": 10.0,
                "current_pair": "BTC-USD/ETH-USD",
                "current_task": "processing pair",
                "updated_at": "2026-04-08T20:41:16Z",
            }

    monkeypatch.setattr(websocket_server, "BacktestRepository", _FakeRepository)

    ws = _FailingWebSocket()
    sent = asyncio.run(
        websocket_server.WebSocketServer.send_backtest_status(
            cast(Any, ws), "run-metrics"
        )
    )

    assert sent is False
    metrics = websocket_server.manager.get_backtest_send_failure_metrics("run-metrics")
    assert metrics["run_id"] == "run-metrics"
    assert metrics["metrics"]["total_send_failures"] >= 1
    assert metrics["metrics"]["consecutive_send_failures"] >= 1
    assert metrics["alert_recommended"] is True


def test_send_backtest_status_expected_disconnect_does_not_raise_alert(monkeypatch):
    session = _DummySession()
    websocket_server.manager.send_metrics.clear()
    monkeypatch.setenv("BACKTEST_WS_FAILURE_ALERT_THRESHOLD", "1")
    monkeypatch.setattr(websocket_server.db, "get_session", lambda: session)

    class _FakeRepository:
        def __init__(self, db_session):
            assert db_session is session

        def get_run_overview(self, run_id: str):
            assert run_id == "run-disconnect"
            return {
                "status": "running",
                "progress_pct": 10.0,
                "current_pair": "BTC-USD/ETH-USD",
                "current_task": "processing pair",
                "updated_at": "2026-04-08T20:41:16Z",
            }

    monkeypatch.setattr(websocket_server, "BacktestRepository", _FakeRepository)

    ws = _DisconnectingWebSocket()
    sent = asyncio.run(
        websocket_server.WebSocketServer.send_backtest_status(
            cast(Any, ws), "run-disconnect"
        )
    )

    assert sent is False
    metrics = websocket_server.manager.get_backtest_send_failure_metrics(
        "run-disconnect"
    )
    assert metrics["metrics"]["total_send_failures"] == 0
    assert metrics["metrics"]["total_send_disconnects"] >= 1
    assert metrics["metrics"]["consecutive_send_failures"] == 0
    assert metrics["alert_recommended"] is False


def test_backtest_connect_resets_stale_consecutive_failures():
    websocket_server.manager.send_metrics.clear()
    run_id = "run-connect-reset"
    channel_id = f"backtest-{run_id}"

    websocket_server.manager._record_send_failure(
        channel_id,
        RuntimeError("boom"),
        operation="test",
    )
    websocket_server.manager._record_send_failure(
        channel_id,
        RuntimeError("boom"),
        operation="test",
    )

    before = websocket_server.manager.get_backtest_send_failure_metrics(run_id)
    assert before["metrics"]["consecutive_send_failures"] >= 2

    ws = _AcceptingDummyWebSocket()
    asyncio.run(websocket_server.manager.connect(cast(Any, ws), channel_id))

    after = websocket_server.manager.get_backtest_send_failure_metrics(run_id)
    assert after["metrics"]["consecutive_send_failures"] == 0


# ---------------------------------------------------------------------------
# Sender-family unit coverage (connection lifecycle, realtime loaders,
# event broadcasters, backtest senders, failure metrics)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_module_manager_state():
    """Keep the module-global ConnectionManager deterministic per test."""
    for attr in ("active_connections", "user_subscriptions", "send_metrics"):
        getattr(websocket_server.manager, attr).clear()
    yield
    for attr in ("active_connections", "user_subscriptions", "send_metrics"):
        getattr(websocket_server.manager, attr).clear()


class _ScriptedWebSocket:
    """WebSocket double with scripted incoming frames and per-send errors.

    ``send_errors`` entries are consumed one per ``send_json`` call; ``None``
    means "this send succeeds", anything else is raised for that send.
    """

    def __init__(self, *, incoming=(), send_errors=()):
        self.incoming = list(incoming)
        self.send_errors = list(send_errors)
        self.sent = []
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        if self.send_errors:
            error = self.send_errors.pop(0)
            if error is not None:
                raise error
        self.sent.append(message)

    async def receive_text(self):
        if not self.incoming:
            raise WebSocketDisconnect(code=1000)
        item = self.incoming.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class _BotsRepo:
    def __init__(self, bot=None, error=None):
        self.bot = bot
        self.error = error
        self.calls = []

    def get_by_instance_id(self, instance_id):
        self.calls.append(instance_id)
        if self.error is not None:
            raise self.error
        return self.bot


class _PositionsRepo:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def get_open_positions(self, bot_id):
        self.calls.append(bot_id)
        return self.rows


class _MarketDataRepo:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def get_all_market_data(self, bot_id):
        self.calls.append(bot_id)
        return self.rows


class _StatsRepo:
    def __init__(self, stats):
        self.stats = stats
        self.calls = []

    def get_stats(self, bot_id):
        self.calls.append(bot_id)
        return self.stats


def _position_row(**overrides):
    base = {
        "position_id": "pos-1",
        "pair1": "BTC-USD",
        "pair2": "ETH-USD",
        "status": SimpleNamespace(value="open"),
        "side1": "BUY",
        "side2": "SELL",
        "entry_price1": 100.0,
        "entry_price2": 50.0,
        "current_price1": 101.5,
        "current_price2": 49.5,
        "current_size1": 0.1,
        "current_size2": 0.2,
        "unrealized_pnl": 12.5,
        "unrealized_pnl_pct": 2.5,
        "z_score_entry": 1.9,
        "z_score_current": 0.4,
        "entry_time": SimpleNamespace(isoformat=lambda: "2026-08-19T10:00:00+00:00"),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _market_row(**overrides):
    base = {
        "symbol": "BTC-USD",
        "current_price": 100.0,
        "bid_price": 99.5,
        "ask_price": 100.5,
        "volume_24h": 1234.5,
        "volatility_24h": 0.42,
        "rsi": None,
        "macd": None,
        "funding_rate": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _stats_row(**overrides):
    base = {
        "total_open_positions": 2,
        "total_unrealized_pnl": 15.5,
        "total_unrealized_pnl_pct": 3.1,
        "daily_pnl": 5.25,
        "daily_pnl_pct": 1.05,
        "daily_trades_opened": 3,
        "daily_trades_closed": 1,
        "daily_win_rate": 66.6,
        "max_drawdown_session": 8.8,
        "current_drawdown": 1.2,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _wire_realtime(
    monkeypatch,
    *,
    positions=(),
    market_data=(),
    stats=None,
    resolve_bot=True,
    bots_error=None,
    session_error=None,
):
    """Patch the websocket_server realtime seams.

    ``resolve_bot=False`` makes non-numeric instance ids unresolvable (bots
    lookup miss) so sender loaders take their "unknown bot" branches. Numeric
    instance ids bypass the bots repo entirely.
    """
    session = _DummySession()

    def _get_session():
        if session_error is not None:
            raise session_error
        return session

    monkeypatch.setattr(websocket_server.db, "get_session", _get_session)

    positions_repo = _PositionsRepo(list(positions))
    market_repo = _MarketDataRepo(list(market_data))
    stats_repo = _StatsRepo(stats)
    bots_repo = _BotsRepo(
        bot=SimpleNamespace(id=42) if resolve_bot else None, error=bots_error
    )

    class _RealtimeUow:
        def __init__(self, db_session):
            assert db_session is session
            self.positions = positions_repo
            self.market_data = market_repo
            self.stats = stats_repo

    class _CoreUow:
        def __init__(self, db_session):
            self.bots = bots_repo

    monkeypatch.setattr(websocket_server, "UnitOfWorkRealtime", _RealtimeUow)
    monkeypatch.setattr(websocket_server, "UnitOfWork", _CoreUow)
    return SimpleNamespace(
        session=session,
        positions=positions_repo,
        market_data=market_repo,
        stats=stats_repo,
        bots=bots_repo,
    )


def _wire_backtest_overview(monkeypatch, overview, *, session=None):
    session = session or _DummySession()

    class _FakeRepository:
        def __init__(self, db_session):
            assert db_session is session

        def get_run_overview(self, run_id: str):
            return overview

    monkeypatch.setattr(websocket_server.db, "get_session", lambda: session)
    monkeypatch.setattr(websocket_server, "BacktestRepository", _FakeRepository)
    return session


# --- ConnectionManager: env helpers and failure metrics ---------------------


def test_positive_env_helpers_parse_clamp_and_fallback(monkeypatch):
    monkeypatch.delenv("WS_UNIT_TEST_INT", raising=False)
    monkeypatch.delenv("WS_UNIT_TEST_FLOAT", raising=False)
    assert ConnectionManager._positive_int_env("WS_UNIT_TEST_INT", 5) == 5
    assert ConnectionManager._positive_float_env("WS_UNIT_TEST_FLOAT", 2.5) == 2.5

    monkeypatch.setenv("WS_UNIT_TEST_INT", "7")
    assert ConnectionManager._positive_int_env("WS_UNIT_TEST_INT", 5) == 7
    monkeypatch.setenv("WS_UNIT_TEST_FLOAT", "3.5")
    assert ConnectionManager._positive_float_env("WS_UNIT_TEST_FLOAT", 2.5) == 3.5

    monkeypatch.setenv("WS_UNIT_TEST_INT", "")
    assert ConnectionManager._positive_int_env("WS_UNIT_TEST_INT", 5) == 5
    monkeypatch.setenv("WS_UNIT_TEST_FLOAT", "")
    assert ConnectionManager._positive_float_env("WS_UNIT_TEST_FLOAT", 2.5) == 2.5

    monkeypatch.setenv("WS_UNIT_TEST_INT", "abc")
    assert ConnectionManager._positive_int_env("WS_UNIT_TEST_INT", 5) == 5
    monkeypatch.setenv("WS_UNIT_TEST_FLOAT", "bogus")
    assert ConnectionManager._positive_float_env("WS_UNIT_TEST_FLOAT", 2.5) == 2.5

    monkeypatch.setenv("WS_UNIT_TEST_INT", "0")
    assert ConnectionManager._positive_int_env("WS_UNIT_TEST_INT", 5) == 1
    monkeypatch.setenv("WS_UNIT_TEST_FLOAT", "0.25")
    assert ConnectionManager._positive_float_env("WS_UNIT_TEST_FLOAT", 2.5) == 1.0


def test_connect_reset_ignores_non_backtest_channels():
    manager = ConnectionManager()
    manager._record_backtest_connect("bot-1")
    manager._record_backtest_connect("backtest-")
    assert manager.send_metrics == {}


def test_record_send_success_scoped_to_backtest_channels():
    manager = ConnectionManager()
    manager._record_send_success("backtest-run-ok")
    bucket = manager.send_metrics["run-ok"]
    assert bucket["total_send_attempts"] == 1
    assert bucket["total_send_successes"] == 1
    assert bucket["consecutive_send_failures"] == 0
    assert bucket["last_success_at"] is not None

    for channel in (None, "bot-1", "backtest-"):
        manager._record_send_success(channel)
    assert set(manager.send_metrics) == {"run-ok"}


def test_record_send_failure_ignores_non_backtest_channels():
    manager = ConnectionManager()
    for channel in (None, "bot-1", "backtest-"):
        manager._record_send_failure(channel, RuntimeError("boom"), operation="test")
    assert manager.send_metrics == {}


def test_failure_metrics_prune_window_and_recent_count_alert(monkeypatch):
    monkeypatch.setenv("BACKTEST_WS_FAILURE_ALERT_THRESHOLD", "2")
    manager = ConnectionManager()
    bucket = manager._run_metrics_bucket("run-prune")
    stale = time.time() - 9999.0
    fresh = time.time()
    bucket["recent_failure_timestamps"] = [stale, fresh]
    bucket["consecutive_send_failures"] = 0

    metrics = manager.get_backtest_send_failure_metrics("run-prune")
    assert metrics["metrics"]["recent_send_failures"] == 1
    assert metrics["alert_recommended"] is False

    bucket["recent_failure_timestamps"] = [time.time(), time.time()]
    metrics = manager.get_backtest_send_failure_metrics("run-prune")
    assert metrics["metrics"]["recent_send_failures"] == 2
    assert metrics["alert_recommended"] is True
    assert metrics["metrics"]["consecutive_send_failures"] == 0


def test_failure_metrics_empty_run_id_returns_null_metrics(monkeypatch):
    monkeypatch.setenv("BACKTEST_WS_FAILURE_ALERT_THRESHOLD", "3")
    monkeypatch.setenv("BACKTEST_WS_FAILURE_ALERT_WINDOW_SECONDS", "120")
    manager = ConnectionManager()
    payload = manager.get_backtest_send_failure_metrics("")
    assert payload["run_id"] == ""
    assert payload["alert_threshold"] == 3
    assert payload["alert_window_seconds"] == 120.0
    assert payload["metrics"] is None


def test_failure_metrics_unknown_run_returns_zeroed_block():
    manager = ConnectionManager()
    payload = manager.get_backtest_send_failure_metrics("run-never")
    assert payload["metrics"] == {
        "total_send_attempts": 0,
        "total_send_successes": 0,
        "total_send_failures": 0,
        "consecutive_send_failures": 0,
        "recent_send_failures": 0,
        "last_error_type": None,
        "last_error_repr": None,
        "last_failure_at": None,
        "last_success_at": None,
        "updated_at": None,
    }
    assert payload["alert_recommended"] is False


def test_failure_summary_aggregates_tracked_runs(monkeypatch):
    manager = ConnectionManager()
    assert manager.get_backtest_send_failure_summary()["tracked_runs"] == 0

    manager._record_send_success("backtest-run-ok")
    manager._record_send_failure(
        "backtest-run-bad", RuntimeError("x"), operation="test"
    )
    manager._record_send_failure(
        "backtest-run-bad", RuntimeError("y"), operation="test"
    )

    summary = manager.get_backtest_send_failure_summary()
    assert summary["tracked_runs"] == 2
    assert summary["total_send_failures"] == 2
    assert summary["runs_with_alerts"] == []

    monkeypatch.setenv("BACKTEST_WS_FAILURE_ALERT_THRESHOLD", "2")
    summary = manager.get_backtest_send_failure_summary()
    assert summary["runs_with_alerts"] == ["run-bad"]


# --- ConnectionManager: lifecycle and delivery -------------------------------


def test_connect_and_disconnect_lifecycle():
    manager = ConnectionManager()
    first, second = _ScriptedWebSocket(), _ScriptedWebSocket()

    asyncio.run(manager.connect(cast(Any, first), "bot-c"))
    asyncio.run(manager.connect(cast(Any, second), "bot-c"))
    assert first.accepted and second.accepted
    assert manager.active_connections == {"bot-c": {first, second}}
    assert manager.user_subscriptions[first] == {"bot-c"}

    manager.disconnect(first, "bot-c")
    assert manager.active_connections == {"bot-c": {second}}
    assert first not in manager.user_subscriptions

    manager.disconnect(second, "bot-c")
    assert manager.active_connections == {}
    manager.disconnect(second, "never-seen")  # unknown channel: no-op


def test_drop_connection_removes_socket_from_all_channels():
    manager = ConnectionManager()
    socket, other = _ScriptedWebSocket(), _ScriptedWebSocket()
    manager.active_connections["chan-a"] = {socket}
    manager.active_connections["chan-b"] = {socket, other}
    manager.user_subscriptions[socket] = {"chan-a", "chan-b", "chan-missing"}

    manager._drop_connection(socket)
    assert manager.active_connections == {"chan-b": {other}}
    assert socket not in manager.user_subscriptions


def test_deliver_local_noop_for_unknown_and_empty_channels():
    manager = ConnectionManager()
    socket = _ScriptedWebSocket()
    asyncio.run(manager._deliver_local("unknown-channel", {"type": "x"}))
    manager.active_connections["bot-empty"] = set()
    asyncio.run(manager._deliver_local("bot-empty", {"type": "x"}))
    assert socket.sent == []


def test_broadcast_mixed_send_outcomes_drop_failed_connections():
    manager = ConnectionManager()
    ok = _ScriptedWebSocket()
    disconnecting = _ScriptedWebSocket(send_errors=[WebSocketDisconnect(code=1000)])
    failing = _ScriptedWebSocket(send_errors=[RuntimeError("socket gone")])
    manager.active_connections["backtest-run-bc"] = {ok, disconnecting, failing}
    manager.user_subscriptions[ok] = {"backtest-run-bc"}
    manager.user_subscriptions[disconnecting] = {"backtest-run-bc"}
    manager.user_subscriptions[failing] = {"backtest-run-bc"}

    asyncio.run(manager.broadcast_to_bot("backtest-run-bc", {"type": "tick"}))

    assert ok.sent == [{"type": "tick"}]
    assert manager.active_connections == {"backtest-run-bc": {ok}}
    assert disconnecting not in manager.user_subscriptions
    assert failing not in manager.user_subscriptions

    metrics = manager.get_backtest_send_failure_metrics("run-bc")["metrics"]
    assert metrics["total_send_attempts"] == 3
    assert metrics["total_send_successes"] == 1
    assert metrics["total_send_disconnects"] == 1
    assert metrics["total_send_failures"] == 1


def test_send_personal_message_outcomes_drop_failed_sockets():
    manager = ConnectionManager()
    healthy = _ScriptedWebSocket()
    failing = _ScriptedWebSocket(send_errors=[RuntimeError("broken")])
    dropping = _ScriptedWebSocket(send_errors=[WebSocketDisconnect(code=1000)])
    for socket in (healthy, failing, dropping):
        manager.active_connections.setdefault("bot-p", set()).add(socket)
        manager.user_subscriptions[socket] = {"bot-p"}

    assert asyncio.run(manager.send_personal_message({"type": "x"}, cast(Any, healthy)))
    assert (
        asyncio.run(
            manager.send_personal_message(
                {"type": "x"}, cast(Any, failing), channel_id="backtest-run-p"
            )
        )
        is False
    )
    assert (
        asyncio.run(
            manager.send_personal_message(
                {"type": "x"}, cast(Any, dropping), channel_id="backtest-run-p"
            )
        )
        is False
    )

    assert manager.active_connections == {"bot-p": {healthy}}
    assert healthy.sent == [{"type": "x"}]
    assert failing not in manager.user_subscriptions
    metrics = manager.get_backtest_send_failure_metrics("run-p")["metrics"]
    assert metrics["total_send_attempts"] == 2
    assert metrics["total_send_failures"] == 1
    assert metrics["total_send_disconnects"] == 1


# --- WebSocketEvents and module broadcast helpers ----------------------------


def test_websocket_events_broadcast_message_shapes():
    socket = _ScriptedWebSocket()
    websocket_server.manager.active_connections["7"] = {socket}

    asyncio.run(WebSocketEvents.handle_position_opened("7", {"position_id": "p1"}))
    asyncio.run(WebSocketEvents.handle_position_updated("7", {"pnl": 1.0}))
    asyncio.run(WebSocketEvents.handle_position_closed("7", {"exit": "done"}))
    asyncio.run(WebSocketEvents.handle_market_data("7", {"price": 100.0}))
    asyncio.run(WebSocketEvents.handle_stats_updated("7", {"wins": 3}))

    types = [message["type"] for message in socket.sent]
    assert types == [
        "position_opened",
        "position_updated",
        "position_closed",
        "market_data",
        "stats_updated",
    ]
    for message in socket.sent:
        assert message["bot_instance_id"] == "7"
        assert "timestamp" in message
    assert socket.sent[0]["data"] == {"position_id": "p1"}


def test_websocket_events_alert_defaults_and_overrides():
    socket = _ScriptedWebSocket()
    websocket_server.manager.active_connections["8"] = {socket}

    asyncio.run(WebSocketEvents.handle_alert("8", {}))
    asyncio.run(
        WebSocketEvents.handle_alert("8", {"severity": "critical", "message": "marg"})
    )

    assert socket.sent[0]["type"] == "alert"
    assert socket.sent[0]["severity"] == "info"
    assert socket.sent[0]["message"] == ""
    assert socket.sent[1]["severity"] == "critical"
    assert socket.sent[1]["message"] == "marg"


def test_module_broadcast_helpers_route_to_string_channels():
    helpers = [
        (websocket_server.broadcast_position_opened, "position_opened"),
        (websocket_server.broadcast_position_update, "position_updated"),
        (websocket_server.broadcast_position_closed, "position_closed"),
        (websocket_server.broadcast_market_update, "market_data"),
        (websocket_server.broadcast_stats_update, "stats_updated"),
    ]
    for helper, expected_type in helpers:
        socket = _ScriptedWebSocket()
        websocket_server.manager.active_connections["9"] = {socket}
        asyncio.run(helper(9, {"x": 1}))
        assert socket.sent[0]["type"] == expected_type
        assert socket.sent[0]["bot_instance_id"] == "9"

    alert_socket = _ScriptedWebSocket()
    websocket_server.manager.active_connections["9"] = {alert_socket}
    asyncio.run(websocket_server.broadcast_alert(9, {"severity": "warning"}))
    assert alert_socket.sent[0]["type"] == "alert"
    assert alert_socket.sent[0]["bot_instance_id"] == "9"
    assert alert_socket.sent[0]["severity"] == "warning"


def test_broadcast_strategy_status_and_snapshot_builder():
    socket = _ScriptedWebSocket()
    websocket_server.manager.active_connections["strategies"] = {socket}

    asyncio.run(websocket_server.broadcast_strategy_status({"id": 5, "status": "run"}))
    # The status payload is published verbatim; only the snapshot builder
    # wraps payloads in a strategy_status_snapshot envelope.
    assert socket.sent == [{"id": 5, "status": "run"}]

    snapshot = websocket_server.build_strategy_snapshot_message([{"id": 1}, {"id": 2}])
    assert snapshot["type"] == "strategy_status_snapshot"
    assert snapshot["count"] == 2
    assert snapshot["data"] == [{"id": 1}, {"id": 2}]
    assert "timestamp" in snapshot


# --- WebSocketServer: id resolution and message builders ---------------------


def test_resolve_realtime_bot_id_matrix(monkeypatch):
    session = _DummySession()
    assert WebSocketServer._resolve_realtime_bot_id(session, "") is None
    assert WebSocketServer._resolve_realtime_bot_id(session, "   ") is None
    # Numeric ids never touch the bots repo.
    assert WebSocketServer._resolve_realtime_bot_id(session, "42") == 42

    bots_repo = _BotsRepo(bot=SimpleNamespace(id=7))
    monkeypatch.setattr(
        websocket_server,
        "UnitOfWork",
        lambda _session: SimpleNamespace(bots=bots_repo),
    )
    assert WebSocketServer._resolve_realtime_bot_id(session, "strategy-1-2") == 7
    assert bots_repo.calls == ["strategy-1-2"]

    bots_repo = _BotsRepo(bot=None)
    monkeypatch.setattr(
        websocket_server,
        "UnitOfWork",
        lambda _session: SimpleNamespace(bots=bots_repo),
    )
    assert WebSocketServer._resolve_realtime_bot_id(session, "strategy-1-2") is None

    bots_repo = _BotsRepo(error=RuntimeError("db down"))
    monkeypatch.setattr(
        websocket_server,
        "UnitOfWork",
        lambda _session: SimpleNamespace(bots=bots_repo),
    )
    assert WebSocketServer._resolve_realtime_bot_id(session, "strategy-1-2") is None


def test_build_backtest_status_message_full_and_defaults():
    message = WebSocketServer._build_backtest_status_message(
        "run-1",
        {
            "status": "running",
            "progress_pct": "12.5",
            "current_pair": "BTC-USD/ETH-USD",
            "current_task": "simulating",
            "eta_seconds": 90,
            "total_pnl": "10.5",
            "total_trades": "3",
            "win_rate": "55.0",
            "sharpe_ratio": "1.2",
            "max_drawdown_pct": "4.5",
            "profit_factor": "1.8",
            "updated_at": "2026-08-19T00:00:00Z",
        },
    )
    assert message["type"] == "backtest_progress"
    assert message["run_id"] == "run-1"
    assert message["status"] == "running"
    assert message["progress_pct"] == 12.5
    assert message["progress"] == 12.5
    assert message["total_trades"] == 3
    assert message["message"] == "simulating"
    assert message["details"] == {
        "source": "initial_state",
        "updated_at": "2026-08-19T00:00:00Z",
    }

    empty = WebSocketServer._build_backtest_status_message("run-2", {})
    assert empty["status"] == "pending"
    assert empty["progress_pct"] == 0.0
    assert empty["total_pnl"] == 0.0
    assert empty["current_pair"] is None
    assert empty["message"] == "backtest_status"


def test_build_backtest_log_message_matrix():
    cases = [
        ({"status": "completed"}, "Backtest completed", "info"),
        ({"current_task": "complete"}, "Backtest completed", "info"),
        ({"status": " failed "}, "Backtest failed", "error"),
        ({"current_task": "failed", "error_message": "boom"}, "boom", "error"),
        (
            {"current_task": "failed", "error": "fallback error"},
            "fallback error",
            "error",
        ),
        ({"status": "cancelled"}, "Backtest cancelled", "warning"),
        ({"current_task": "cancelled"}, "Backtest cancelled", "warning"),
        (
            {"current_task": "simulating", "current_pair": "BTC-USD/ETH-USD"},
            "simulating: BTC-USD/ETH-USD",
            "info",
        ),
        ({"current_pair": "BTC-USD/ETH-USD"}, "Scanning: BTC-USD/ETH-USD", "info"),
        ({"current_task": "loading data"}, "loading data", "info"),
        ({"status": "paused"}, "Status: paused", "info"),
    ]
    for data, expected_message, expected_level in cases:
        message = WebSocketServer._build_backtest_log_message("run-x", data)
        assert message is not None, data
        assert message["message"] == expected_message, data
        assert message["level"] == expected_level, data
        assert message["type"] == "backtest_log"
        assert message["run_id"] == "run-x"

    assert WebSocketServer._build_backtest_log_message("run-x", {}) is None


# --- WebSocketServer: handle_connection and handle_message -------------------


def test_handle_connection_full_lifecycle(monkeypatch):
    _wire_realtime(
        monkeypatch,
        positions=[_position_row()],
        market_data=[_market_row()],
        stats=_stats_row(),
    )
    socket = _ScriptedWebSocket(
        incoming=['{"type": "ping"}', '{"type": "request_positions"}']
    )

    asyncio.run(WebSocketServer.handle_connection(cast(Any, socket), "42"))

    assert socket.accepted is True
    assert [message["type"] for message in socket.sent] == [
        "initial_state",
        "pong",
        "positions_list",
    ]
    assert socket.sent[0]["data"]["positions"][0]["position_id"] == "pos-1"
    assert "42" not in websocket_server.manager.active_connections
    assert socket not in websocket_server.manager.user_subscriptions


def test_handle_connection_initial_state_failure_closes_without_receiving(monkeypatch):
    _wire_realtime(monkeypatch, stats=_stats_row())
    socket = _ScriptedWebSocket(
        incoming=['{"type": "ping"}'], send_errors=[RuntimeError("closed early")]
    )

    asyncio.run(WebSocketServer.handle_connection(cast(Any, socket), "42"))

    assert socket.accepted is True
    assert socket.sent == []
    assert socket.incoming == ['{"type": "ping"}']  # receive loop never entered
    assert "42" not in websocket_server.manager.active_connections


def test_handle_connection_invalid_json_disconnects(monkeypatch):
    _wire_realtime(monkeypatch, stats=_stats_row())
    socket = _ScriptedWebSocket(incoming=["not-json"])

    asyncio.run(WebSocketServer.handle_connection(cast(Any, socket), "42"))

    assert [message["type"] for message in socket.sent] == ["initial_state"]
    assert "42" not in websocket_server.manager.active_connections


def test_handle_message_dispatch_matrix(monkeypatch):
    calls = {}

    async def _positions(websocket, bot_id):
        calls["positions"] = bot_id

    async def _stats(websocket, bot_id):
        calls["stats"] = bot_id

    async def _market_data(websocket, bot_id):
        calls["market_data"] = bot_id

    async def _status(websocket, run_id):
        calls["status"] = run_id
        return True

    monkeypatch.setattr(WebSocketServer, "send_positions", staticmethod(_positions))
    monkeypatch.setattr(WebSocketServer, "send_stats", staticmethod(_stats))
    monkeypatch.setattr(WebSocketServer, "send_market_data", staticmethod(_market_data))
    monkeypatch.setattr(WebSocketServer, "send_backtest_status", staticmethod(_status))

    socket = _ScriptedWebSocket()
    asyncio.run(
        WebSocketServer.handle_message(cast(Any, socket), "bot-7", {"type": "ping"})
    )
    assert socket.sent[-1]["type"] == "pong"

    asyncio.run(
        WebSocketServer.handle_message(
            cast(Any, socket), "bot-7", {"type": "request_positions"}
        )
    )
    asyncio.run(
        WebSocketServer.handle_message(
            cast(Any, socket), "bot-7", {"type": "request_stats"}
        )
    )
    asyncio.run(
        WebSocketServer.handle_message(
            cast(Any, socket), "bot-7", {"type": "request_market_data"}
        )
    )
    assert calls == {"positions": "bot-7", "stats": "bot-7", "market_data": "bot-7"}

    # Unknown type and non-backtest request_status both fall through silently.
    asyncio.run(
        WebSocketServer.handle_message(cast(Any, socket), "bot-7", {"type": "mystery"})
    )
    asyncio.run(
        WebSocketServer.handle_message(
            cast(Any, socket), "bot-7", {"type": "request_status"}
        )
    )
    assert "status" not in calls
    assert len(socket.sent) == 1  # only the pong


def test_handle_message_backtest_status_failure_raises(monkeypatch):
    async def _failing_status(websocket, run_id):
        return False

    monkeypatch.setattr(
        WebSocketServer, "send_backtest_status", staticmethod(_failing_status)
    )
    with pytest.raises(RuntimeError, match="status send failed"):
        asyncio.run(
            WebSocketServer.handle_message(
                cast(Any, _ScriptedWebSocket()),
                "backtest-run-x",
                {"type": "request_status"},
            )
        )


# --- WebSocketServer: realtime senders ----------------------------------------


def test_send_initial_state_realtime_full_snapshot(monkeypatch):
    wiring = _wire_realtime(
        monkeypatch,
        positions=[_position_row(unrealized_pnl=7.5)],
        market_data=[_market_row()],
        stats=_stats_row(),
    )
    socket = _ScriptedWebSocket()

    sent = asyncio.run(WebSocketServer.send_initial_state(cast(Any, socket), "42"))

    assert sent is True
    message = socket.sent[0]
    assert message["type"] == "initial_state"
    assert message["data"]["positions"][0]["position_id"] == "pos-1"
    assert message["data"]["positions"][0]["status"] == "open"
    assert message["data"]["positions"][0]["unrealized_pnl"] == 7.5
    assert message["data"]["market_data"][0]["volatility_24h"] == 0.42
    assert message["data"]["stats"]["total_open_positions"] == 2
    assert message["data"]["stats"]["daily_win_rate"] == 66.6
    # The initial-state block intentionally carries only daily_win_rate from
    # the risk fields; full risk fields go through send_stats.
    assert "max_drawdown" not in message["data"]["stats"]
    assert wiring.session.closed is True
    assert wiring.bots.calls == []  # numeric id: no bots lookup


def test_send_initial_state_stats_missing_uses_zero_defaults(monkeypatch):
    _wire_realtime(monkeypatch, positions=[], market_data=[], stats=None)
    socket = _ScriptedWebSocket()

    sent = asyncio.run(WebSocketServer.send_initial_state(cast(Any, socket), "42"))

    assert sent is True
    stats = socket.sent[0]["data"]["stats"]
    assert stats == {
        "total_open_positions": 0,
        "total_unrealized_pnl": 0,
        "total_unrealized_pnl_pct": 0,
        "daily_pnl": 0,
        "daily_pnl_pct": 0,
        "daily_trades_opened": 0,
        "daily_trades_closed": 0,
        "daily_win_rate": 0,
    }


def test_send_initial_state_unknown_bot_warns(monkeypatch):
    _wire_realtime(monkeypatch, resolve_bot=False)
    socket = _ScriptedWebSocket()

    sent = asyncio.run(
        WebSocketServer.send_initial_state(cast(Any, socket), "strategy-zz")
    )

    assert sent is True
    message = socket.sent[0]
    assert message["type"] == "initial_state"
    assert message["data"] == {"positions": [], "market_data": [], "stats": {}}
    assert message["warning"] == "Unknown bot instance id: strategy-zz"


def test_send_initial_state_loader_error_returns_false(monkeypatch):
    _wire_realtime(monkeypatch, session_error=RuntimeError("db down"))
    socket = _ScriptedWebSocket()

    sent = asyncio.run(WebSocketServer.send_initial_state(cast(Any, socket), "42"))

    assert sent is False
    assert socket.sent == []


def test_send_positions_rows_unknown_bot_and_error(monkeypatch):
    _wire_realtime(monkeypatch, positions=[_position_row()])
    socket = _ScriptedWebSocket()
    asyncio.run(WebSocketServer.send_positions(cast(Any, socket), "42"))
    message = socket.sent[0]
    assert message["type"] == "positions_list"
    assert message["data"] == [
        {
            "position_id": "pos-1",
            "pair1": "BTC-USD",
            "pair2": "ETH-USD",
            "unrealized_pnl": 12.5,
            "unrealized_pnl_pct": 2.5,
        }
    ]

    _wire_realtime(monkeypatch, resolve_bot=False)
    unknown_socket = _ScriptedWebSocket()
    asyncio.run(
        WebSocketServer.send_positions(cast(Any, unknown_socket), "strategy-zz")
    )
    assert unknown_socket.sent[0]["data"] == []

    _wire_realtime(monkeypatch, session_error=RuntimeError("db down"))
    error_socket = _ScriptedWebSocket()
    asyncio.run(WebSocketServer.send_positions(cast(Any, error_socket), "42"))
    assert error_socket.sent == []


def test_send_stats_unknown_bot_missing_and_error(monkeypatch):
    _wire_realtime(monkeypatch, resolve_bot=False)
    unknown_socket = _ScriptedWebSocket()
    asyncio.run(WebSocketServer.send_stats(cast(Any, unknown_socket), "strategy-zz"))
    assert unknown_socket.sent[0]["type"] == "stats"
    assert unknown_socket.sent[0]["data"] == {}

    _wire_realtime(monkeypatch, stats=None)
    missing_socket = _ScriptedWebSocket()
    asyncio.run(WebSocketServer.send_stats(cast(Any, missing_socket), "42"))
    assert missing_socket.sent[0]["data"] == {}

    _wire_realtime(monkeypatch, session_error=RuntimeError("db down"))
    error_socket = _ScriptedWebSocket()
    asyncio.run(WebSocketServer.send_stats(cast(Any, error_socket), "42"))
    assert error_socket.sent == []


def test_send_market_data_rows_unknown_bot_and_error(monkeypatch):
    _wire_realtime(
        monkeypatch,
        market_data=[
            _market_row(rsi=55.5, macd=None, funding_rate=0.001),
            _market_row(),
        ],
    )
    socket = _ScriptedWebSocket()
    asyncio.run(WebSocketServer.send_market_data(cast(Any, socket), "42"))
    rows = socket.sent[0]["data"]
    assert socket.sent[0]["type"] == "market_data"
    assert len(rows) == 2
    assert rows[0]["symbol"] == "BTC-USD"
    assert rows[0]["rsi"] == 55.5
    assert rows[0]["macd"] is None
    assert rows[0]["funding_rate"] == 0.001
    assert "volatility_24h" not in rows[0]  # realtime market data excludes it

    _wire_realtime(monkeypatch, resolve_bot=False)
    unknown_socket = _ScriptedWebSocket()
    asyncio.run(
        WebSocketServer.send_market_data(cast(Any, unknown_socket), "strategy-zz")
    )
    assert unknown_socket.sent[0]["data"] == []

    _wire_realtime(monkeypatch, session_error=RuntimeError("db down"))
    error_socket = _ScriptedWebSocket()
    asyncio.run(WebSocketServer.send_market_data(cast(Any, error_socket), "42"))
    assert error_socket.sent == []


# --- WebSocketServer: backtest sender -----------------------------------------


def test_send_backtest_status_not_found(monkeypatch):
    session = _wire_backtest_overview(monkeypatch, None)
    socket = _ScriptedWebSocket()

    sent = asyncio.run(
        WebSocketServer.send_backtest_status(cast(Any, socket), "run-404")
    )

    assert sent is True
    assert len(socket.sent) == 1  # no log message for missing runs
    message = socket.sent[0]
    assert message["type"] == "backtest_progress"
    assert message["status"] == "not_found"
    assert message["progress_pct"] == 0.0
    assert message["message"] == "backtest_not_found"
    assert session.closed is True


def test_send_backtest_status_completed_sends_log(monkeypatch):
    _wire_backtest_overview(
        monkeypatch,
        {
            "status": "completed",
            "progress_pct": 100.0,
            "total_pnl": 25.0,
            "total_trades": 6,
            "current_pair": None,
            "current_task": None,
        },
    )
    socket = _ScriptedWebSocket()

    sent = asyncio.run(
        WebSocketServer.send_backtest_status(cast(Any, socket), "run-done")
    )

    assert sent is True
    progress, log = socket.sent
    assert progress["type"] == "backtest_progress"
    assert progress["status"] == "completed"
    assert progress["progress_pct"] == 100.0
    assert log["type"] == "backtest_log"
    assert log["message"] == "Backtest completed"
    assert log["level"] == "info"


def test_send_backtest_status_log_send_failure_returns_false(monkeypatch):
    _wire_backtest_overview(
        monkeypatch,
        {
            "status": "running",
            "progress_pct": 10.0,
            "current_pair": "BTC-USD/ETH-USD",
            "current_task": "processing pair",
        },
    )
    socket = _ScriptedWebSocket(send_errors=[None, RuntimeError("log send failed")])

    sent = asyncio.run(
        WebSocketServer.send_backtest_status(cast(Any, socket), "run-log")
    )

    assert sent is False
    assert len(socket.sent) == 1  # progress delivered, log failed
    metrics = websocket_server.manager.get_backtest_send_failure_metrics("run-log")[
        "metrics"
    ]
    assert metrics["total_send_attempts"] == 2
    assert metrics["total_send_successes"] == 1


def test_send_backtest_status_loader_error_returns_false(monkeypatch):
    session = _DummySession()

    def _get_session():
        raise RuntimeError("db down")

    monkeypatch.setattr(websocket_server.db, "get_session", _get_session)
    socket = _ScriptedWebSocket()

    sent = asyncio.run(
        WebSocketServer.send_backtest_status(cast(Any, socket), "run-err")
    )

    assert sent is False
    assert socket.sent == []
