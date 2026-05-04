import asyncio

from src.api import websocket_server


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
        websocket_server.WebSocketServer.send_initial_state(ws, "backtest-run-123")
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
            ws,
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
    asyncio.run(websocket_server.WebSocketServer.send_stats(ws, "strategy-1-9"))

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
        websocket_server.WebSocketServer.send_backtest_status(ws, "run-metrics")
    )

    assert sent is False
    metrics = websocket_server.manager.get_backtest_send_failure_metrics("run-metrics")
    assert metrics["run_id"] == "run-metrics"
    assert metrics["metrics"]["total_send_failures"] >= 1
    assert metrics["metrics"]["consecutive_send_failures"] >= 1
    assert metrics["alert_recommended"] is True
