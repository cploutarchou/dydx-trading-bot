from src.infrastructure.workers.celery_monitor import (
    _task_from_backtest,
    build_progress_meta,
    celery_state_from_backtest,
    redact_payload,
)


def test_flower_script_uses_discovered_celery_app_path():
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts" / "celery-flower.sh"
    content = script.read_text(encoding="utf-8")

    assert "src.infrastructure.workers.celery_app:celery_app" in content
    assert "FLOWER_BASIC_AUTH is required" in content
    assert '--basic_auth="${FLOWER_BASIC_AUTH}"' in content


def test_redact_payload_hides_sensitive_task_fields():
    payload = {
        "strategy_id": 7,
        "api_key": "secret-key",
        "nested": {"broker_url": "redis://:password@localhost:6379/0", "safe": "ok"},
        "pairs": ["BTC-USD", "ETH-USD"],
    }

    redacted = redact_payload(payload)

    assert redacted["strategy_id"] == 7
    assert redacted["api_key"] == "redacted"
    assert redacted["nested"]["broker_url"] == "redacted"
    assert redacted["nested"]["safe"] == "ok"
    assert redacted["pairs"] == ["BTC-USD", "ETH-USD"]


def test_build_progress_meta_includes_debug_context():
    meta = build_progress_meta(
        run_id="run-1",
        progress_percent=42.123,
        current_pair="BTC-USD/ETH-USD",
        current_step="processing pair",
        total_pairs=10,
        completed_pairs=4,
        current_phase="simulation",
        eta_seconds=120,
        strategy_id=3,
        bot_id="bot-1",
        environment="testnet",
        selected_pairs=["BTC-USD", "ETH-USD"],
    )

    assert meta["task_id"] == "run-1"
    assert meta["task_name"] == "backtests.run"
    assert meta["status"] == "PROGRESS"
    assert meta["progress_percent"] == 42.12
    assert meta["current_pair"] == "BTC-USD/ETH-USD"
    assert meta["total_pairs"] == 10
    assert meta["completed_pairs"] == 4
    assert meta["strategy_id"] == 3
    assert meta["bot_id"] == "bot-1"
    assert meta["environment"] == "testnet"
    assert meta["selected_pairs"] == ["BTC-USD", "ETH-USD"]
    assert meta["last_heartbeat_at"]


def test_celery_state_from_backtest_maps_app_statuses():
    assert celery_state_from_backtest("completed") == "SUCCESS"
    assert celery_state_from_backtest("failed") == "FAILURE"
    assert celery_state_from_backtest("cancelled") == "REVOKED"
    assert celery_state_from_backtest("running") == "STARTED"
    assert celery_state_from_backtest("queued") == "PENDING"


def test_task_from_backtest_uses_persisted_request_context_when_summary_fields_are_missing():
    task = _task_from_backtest(
        {
            "run_id": "run-ctx-1",
            "worker_task_id": "run-ctx-1",
            "status": "running",
            "progress_pct": 37.5,
            "current_task": "processing pair",
            "current_pair": "BTC-USD/ETH-USD",
            "request": {
                "strategy_id": 11,
                "pairs": ["BTC-USD", "ETH-USD", "SOL-USD"],
                "selected_pairs": ["BTC-USD/ETH-USD", "ETH-USD/SOL-USD"],
                "_task_context": {
                    "strategy_id": 11,
                    "selected_pairs": ["BTC-USD/ETH-USD", "ETH-USD/SOL-USD"],
                    "bot_id": "bot-7",
                    "environment": "development",
                    "source": "ui",
                    "strategy_name": "Desk Strategy",
                    "payload_hash": "abc123",
                    "metadata": {
                        "strategy_name": "Desk Strategy",
                        "pair_count": 2,
                        "payload_hash": "abc123",
                        "source": "ui",
                    },
                    "worker_hostname": "worker-a",
                    "retry_count": 1,
                },
            },
        }
    )

    assert task["strategy_id"] == 11
    assert task["selected_pairs"] == ["BTC-USD/ETH-USD", "ETH-USD/SOL-USD"]
    assert task["bot_id"] == "bot-7"
    assert task["environment"] == "development"
    assert task["worker_hostname"] == "worker-a"
    assert task["retry_count"] == 1
    assert task["metadata"]["strategy_name"] == "Desk Strategy"
    assert task["metadata"]["payload_hash"] == "abc123"
