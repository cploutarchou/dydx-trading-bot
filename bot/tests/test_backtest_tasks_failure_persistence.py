from __future__ import annotations

from typing import Any, Dict

from src.infrastructure.workers import backtest_tasks


class _DummySession:
    def close(self) -> None:
        return None


class _FakeRepository:
    last_instance: "_FakeRepository | None" = None

    def __init__(self, _session: Any):
        self.updated_payload: Dict[str, Any] | None = None
        _FakeRepository.last_instance = self

    def get_run_overview(self, run_id: str) -> Dict[str, Any]:
        return {
            "run_id": run_id,
            "status": "running",
            "request": {"pairs": ["BTC-USD/ETH-USD"]},
        }

    def update_run_progress(self, run_data: Dict[str, Any]) -> bool:
        self.updated_payload = dict(run_data)
        return True


class _FakeService:
    def __init__(self, _repository: Any):
        pass

    @staticmethod
    def _task_context_from_request(_request_payload: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    @staticmethod
    def _build_task_context(_request_payload: Dict[str, Any], **merged: Any) -> Dict[str, Any]:
        return dict(merged)

    @staticmethod
    def _error_code_from_message(_message: str, fallback: str) -> str:
        return fallback

    @staticmethod
    def _set_task_context(request_payload: Dict[str, Any], _task_context: Dict[str, Any]) -> Dict[str, Any]:
        return dict(request_payload)

    @staticmethod
    def _set_task_failure(request_payload: Dict[str, Any], failure_payload: Dict[str, Any]) -> Dict[str, Any]:
        updated = dict(request_payload)
        updated["task_failure"] = dict(failure_payload)
        return updated

    @staticmethod
    def _set_runtime_control(run_data: Dict[str, Any], **updates: Any) -> Dict[str, Any]:
        request = dict(run_data.get("request") or {})
        request["_runtime_control"] = dict(updates)
        run_data["request"] = request
        return run_data


def test_mark_worker_failure_uses_lightweight_progress_update(monkeypatch):
    monkeypatch.setattr(backtest_tasks.db, "get_session", lambda: _DummySession())
    monkeypatch.setattr(backtest_tasks, "BacktestRepository", _FakeRepository)
    monkeypatch.setattr(backtest_tasks, "BacktestService", _FakeService)

    backtest_tasks._mark_worker_failure(
        run_id="run-lightweight-failure",
        message="simulated worker failure",
        error_code="BACKTEST_EXECUTION_FAILED",
        traceback_text="traceback",
        worker_hostname="worker-1",
        retry_count=1,
    )

    repository = _FakeRepository.last_instance
    assert repository is not None
    assert repository.updated_payload is not None
    assert repository.updated_payload["status"] == "failed"
    assert repository.updated_payload["current_task"] == "failed"
    assert repository.updated_payload["error"] == "simulated worker failure"
    assert repository.updated_payload["error_message"] == "simulated worker failure"
    assert "trades" not in repository.updated_payload
    assert "position_snapshots" not in repository.updated_payload
    assert "daily_pnl" not in repository.updated_payload
