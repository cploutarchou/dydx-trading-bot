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


def test_send_initial_state_backtest_channel_emits_snapshot(monkeypatch):
    session = _DummySession()

    monkeypatch.setattr(websocket_server.db, "get_session", lambda: session)

    class _FakeRepository:
        def __init__(self, db_session):
            assert db_session is session

        def get_run(self, run_id: str):
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
    asyncio.run(websocket_server.WebSocketServer.send_initial_state(ws, "backtest-run-123"))

    assert session.closed is True
    assert len(ws.messages) == 1
    payload = ws.messages[0]
    assert payload["type"] == "backtest_progress"
    assert payload["run_id"] == "run-123"
    assert payload["status"] == "running"
    assert payload["progress_pct"] == 37.5
    assert payload["progress"] == 37.5
    assert payload["current_pair"] == "BTC-USD/ETH-USD"
    assert payload["current_task"] == "scanning pairs"
    assert payload["details"]["source"] == "initial_state"


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
