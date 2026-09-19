import asyncio
import base64
import json
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, cast

import psutil
import pytest

import src.bot_instance_manager as bot_instance_manager_module
from src.bot_instance_manager import BotInstanceManager
from src.infrastructure.domain.bot_api_models import (
    BacktestingParameters,
    BotCredentials,
    BotInstanceConfig,
    BotInstanceState,
    BotStatus,
    TelegramConfig,
    TradingParameters,
)
from src.shared import credentials_cipher as cc


@pytest.fixture(autouse=True)
def _disable_db_persistence_by_default(monkeypatch):
    monkeypatch.setattr(
        BotInstanceManager,
        "_db_persistence_enabled",
        staticmethod(lambda: False),
    )


def _strategy_config(instance_id: str = "strategy-1-101") -> BotInstanceConfig:
    return BotInstanceConfig(
        instance_id=instance_id,
        instance_name="Runtime Strategy",
        credentials=BotCredentials(
            address="0x1234567890123456789012345678901234567890",
            mnemonic="alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
        ),
        trading_params=TradingParameters(
            is_testnet=True,
            place_trades=False,
            manage_exits=False,
            find_cointegrated_pairs=False,
            abort_all_positions=False,
            strategy="cointegration",
            max_positions=3,
            max_drawdown_pct=0.0,
            stop_loss_pct=1.2,
            take_profit_pct=4.5,
            trailing_stop_pct=0.0,
            rebalance_interval_hours=12,
            position_timeout_hours=36,
        ),
        backtesting_params=BacktestingParameters(
            candle_resolution="4HOUR",
            max_history_days=120,
            starting_balance=5000.0,
            transaction_fee=0.0007,
            slippage=0.0015,
            benchmark_symbol="ETH-USD",
            risk_free_rate=0.03,
        ),
    )


def test_strategy_status_snapshot_only_includes_strategy_instances(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))

    asyncio.run(manager.create_instance(_strategy_config("strategy-7-42")))
    asyncio.run(manager.create_instance(_strategy_config("manual-bot-1")))

    snapshot = manager.get_strategy_status_snapshot()

    assert len(snapshot) == 1
    assert snapshot[0]["strategyId"] == 42
    assert snapshot[0]["instance_id"] == "strategy-7-42"
    assert snapshot[0]["status"] == "stopped"
    assert snapshot[0]["network"] == "testnet"


def test_start_instance_marks_fast_exit_as_error_and_publishes_status(
    tmp_path, monkeypatch
):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    published = []

    async def _publisher(payload):
        published.append(payload)

    manager.set_status_event_publisher(_publisher)
    asyncio.run(manager.create_instance(_strategy_config()))

    class FakeProcess:
        pid = 321
        returncode = 7

        def poll(self):
            return self.returncode

        def terminate(self):
            return None

        def kill(self):
            return None

        def wait(self, timeout=None):
            return self.returncode

    monkeypatch.setattr(
        "src.bot_instance_manager.subprocess.Popen",
        lambda *args, **kwargs: FakeProcess(),
    )
    monkeypatch.setattr(
        manager,
        "_read_recent_log_tail",
        lambda instance_id, max_chars=500: "bot failed immediately",
    )

    result = asyncio.run(manager.start_instance("strategy-1-101"))

    assert result.success is False
    assert result.status == BotStatus.ERROR
    assert "exited during startup" in result.message
    assert manager.instances["strategy-1-101"].status == BotStatus.ERROR
    assert published[-1]["strategyId"] == 101
    assert published[-1]["status"] == "error"
    assert "bot failed immediately" in published[-1]["last_error"]


def test_start_instance_launches_from_bot_root_with_module_mode(tmp_path, monkeypatch):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config()))

    popen_calls = {}

    class FakeProcess:
        pid = 654

        def poll(self):
            return None

        def terminate(self):
            return None

        def kill(self):
            return None

        def wait(self, timeout=None):
            return 0

    def _fake_popen(*args, **kwargs):
        popen_calls["args"] = args
        popen_calls["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr("src.bot_instance_manager.subprocess.Popen", _fake_popen)

    result = asyncio.run(manager.start_instance("strategy-1-101"))

    assert result.success is True
    cmd = popen_calls["args"][0]
    kwargs = popen_calls["kwargs"]
    bot_root = Path(bot_instance_manager_module.__file__).resolve().parents[1]
    assert cmd[1:3] == ["-m", "src.main_instance"]
    assert "--config" not in cmd
    assert kwargs["cwd"] == bot_root
    assert "BOT_CONFIG_FILE" not in kwargs["env"]
    assert kwargs["env"]["PYTHONPATH"].split(os.pathsep)[0] == str(bot_root)


def test_cleanup_dead_processes_publishes_error_for_crashed_strategy(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    published = []

    async def _publisher(payload):
        published.append(payload)

    manager.set_status_event_publisher(_publisher)
    asyncio.run(manager.create_instance(_strategy_config()))

    instance = manager.instances["strategy-1-101"]
    instance.status = BotStatus.RUNNING
    instance.process_info = {"pid": 999}

    class DeadProcess:
        returncode = 9

        def poll(self):
            return self.returncode

    manager.processes["strategy-1-101"] = cast(Any, DeadProcess())

    asyncio.run(manager.cleanup_dead_processes())

    assert manager.instances["strategy-1-101"].status == BotStatus.ERROR
    assert published[-1]["strategyId"] == 101
    assert published[-1]["status"] == "error"


def test_cleanup_dead_processes_refreshes_live_worker_heartbeat_without_degrading(
    tmp_path,
):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config()))

    instance = manager.instances["strategy-1-101"]
    instance.status = BotStatus.RUNNING
    instance.process_info = {"pid": 1001}
    instance.last_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=120)
    instance.heartbeat_stale_seconds = 30

    class LiveProcess:
        pid = 1001

        def poll(self):
            return None

    manager.processes["strategy-1-101"] = cast(Any, LiveProcess())

    asyncio.run(manager.cleanup_dead_processes())

    refreshed = manager.instances["strategy-1-101"]
    assert refreshed.status == BotStatus.RUNNING
    assert refreshed.recovery_state is None
    assert refreshed.last_heartbeat is not None
    assert (datetime.now(timezone.utc) - refreshed.last_heartbeat).total_seconds() < 5


def test_degraded_live_worker_recovers_to_running_on_status_probe(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config()))

    instance = manager.instances["strategy-1-101"]
    instance.status = BotStatus.DEGRADED
    instance.recovery_state = "degraded"
    instance.recovery_reason = "Heartbeat stale for 120s"
    instance.process_info = {"pid": os.getpid()}

    class LiveProcess:
        pid = os.getpid()

        def poll(self):
            return None

    manager.processes["strategy-1-101"] = cast(Any, LiveProcess())

    status = asyncio.run(manager.get_instance_status("strategy-1-101"))

    assert status is not None
    assert status.status == BotStatus.RUNNING
    assert manager.instances["strategy-1-101"].recovery_state is None
    assert manager.instances["strategy-1-101"].recovery_reason is None


def test_status_probe_preserves_running_when_metrics_access_denied(
    tmp_path,
    monkeypatch,
):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config()))

    instance = manager.instances["strategy-1-101"]
    instance.status = BotStatus.RUNNING
    instance.process_info = {"pid": 1003}

    class LiveProcess:
        pid = 1003

        def poll(self):
            return None

    class MetricsDeniedProcess:
        def __init__(self, pid):
            self.pid = pid

        def cpu_percent(self):
            raise bot_instance_manager_module.psutil.AccessDenied(pid=self.pid)

    manager.processes["strategy-1-101"] = cast(Any, LiveProcess())
    monkeypatch.setattr(
        bot_instance_manager_module.psutil,
        "Process",
        lambda pid: MetricsDeniedProcess(pid),
    )

    status = asyncio.run(manager.get_instance_status("strategy-1-101"))

    assert status is not None
    assert status.status == BotStatus.RUNNING
    assert manager.instances["strategy-1-101"].last_heartbeat is not None


def test_start_instance_rejects_degraded_active_runtime_without_spawning(
    tmp_path,
    monkeypatch,
):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config()))
    manager.instances["strategy-1-101"].status = BotStatus.DEGRADED

    def fail_popen(*_args, **_kwargs):
        raise AssertionError("start_instance must not spawn duplicate degraded runtime")

    monkeypatch.setattr("src.bot_instance_manager.subprocess.Popen", fail_popen)

    result = asyncio.run(manager.start_instance("strategy-1-101"))

    assert result.success is False
    assert result.status == BotStatus.DEGRADED
    assert "already degraded" in result.message


def test_delete_instance_force_stops_degraded_runtime_before_cleanup(
    tmp_path, monkeypatch
):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config()))
    manager.instances["strategy-1-101"].status = BotStatus.DEGRADED

    stopped = {}

    async def fake_stop_locked(instance_id, force=False):
        stopped["instance_id"] = instance_id
        stopped["force"] = force
        manager.instances[instance_id].status = BotStatus.STOPPED
        return SimpleNamespace(success=True)

    monkeypatch.setattr(manager, "_stop_instance_locked", fake_stop_locked)

    result = asyncio.run(manager.delete_instance("strategy-1-101"))

    assert result.success is True
    assert stopped == {"instance_id": "strategy-1-101", "force": True}
    assert "strategy-1-101" not in manager.instances


def test_create_instance_keeps_runtime_config_in_db_contract_payload(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))

    result = asyncio.run(manager.create_instance(_strategy_config()))

    assert result.success is True

    config_path = tmp_path / "config_strategy-1-101.yaml"
    assert not config_path.exists()
    payload = manager._runtime_contract_payload(manager.instances["strategy-1-101"])
    assert payload["trading_params"]["strategy"] == "cointegration"
    assert payload["trading_params"]["max_positions"] == 3
    assert payload["backtesting_params"]["starting_balance"] == 5000.0
    assert payload["backtesting_params"]["benchmark_symbol"] == "ETH-USD"


def test_dev_environment_defaults_to_unlimited_instances(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("BOT_MAX_INSTANCES", raising=False)

    manager = BotInstanceManager(state_dir=str(tmp_path))

    assert manager.max_instances == 0

    for idx in range(12):
        result = asyncio.run(
            manager.create_instance(_strategy_config(f"strategy-1-{100 + idx}"))
        )
        assert result.success is True


def test_production_environment_uses_default_limit(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("BOT_MAX_INSTANCES", raising=False)

    manager = BotInstanceManager(state_dir=str(tmp_path))

    assert manager.max_instances == 10

    for idx in range(10):
        result = asyncio.run(
            manager.create_instance(_strategy_config(f"strategy-2-{200 + idx}"))
        )
        assert result.success is True

    blocked = asyncio.run(manager.create_instance(_strategy_config("strategy-2-999")))
    assert blocked.success is False
    assert blocked.message == "Maximum instances limit reached (10)"


def test_runtime_contract_payload_uses_instance_config_only(monkeypatch, tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    config = _strategy_config()
    config.telegram = None
    config.backtesting_params = None

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "legacy-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "legacy-chat")
    monkeypatch.setenv("BACKTEST_BENCHMARK_SYMBOL", "LEGACY-USD")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    state = BotInstanceState(
        instance_id=config.instance_id,
        config=config,
        status=BotStatus.STOPPED,
        process_info={},
        trading_stats={},
        created_at=datetime.now(timezone.utc),
        last_update=datetime.now(timezone.utc),
    )
    payload = manager._runtime_contract_payload(state)

    assert payload["telegram"] == {}
    assert payload["backtesting_params"] == {}
    assert payload["trading_params"]["strategy"] == "cointegration"
    assert payload["credentials"]["address"] == config.credentials.address


def test_manager_recovers_instances_from_database_before_legacy_disk(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        BotInstanceManager,
        "_db_persistence_enabled",
        staticmethod(lambda: True),
    )
    legacy_state = tmp_path / "instances.json"
    legacy_state.write_text(
        """
        {
          "instances": [
            {
              "instance_id": "legacy-bot-1",
              "config": {
                "instance_id": "legacy-bot-1",
                "credentials": {
                  "address": "legacy-address",
                  "mnemonic": "legacy mnemonic words words words"
                },
                "trading_params": {
                  "is_testnet": true
                }
              },
              "created_at": "2026-01-01T00:00:00"
            }
          ]
        }
        """.strip(),
        encoding="utf-8",
    )

    now = datetime.now()
    base_strategy_config = _strategy_config()
    assert base_strategy_config.backtesting_params is not None
    persisted_record = SimpleNamespace(
        instance_id="strategy-1-101",
        network="testnet",
        strategy="cointegration",
        config={
            "instance_name": "Recovered Strategy",
            "credentials": {
                "chain_id": "dydx-testnet-4",
                "address": "dydx1recoveredaddress",
                "mnemonic": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
            },
            "telegram": {"token": "persisted-token", "chat_id": "persisted-chat"},
            "trading_params": base_strategy_config.trading_params.model_dump(),
            "backtesting_params": base_strategy_config.backtesting_params.model_dump(),
        },
        status=SimpleNamespace(value="running"),
        process_id=4321,
        created_at=now,
        updated_at=now,
    )

    class FakeBotsRepo:
        def get_all(self):
            return [persisted_record]

    class FakeUOW:
        def __init__(self, session):
            self.bots = FakeBotsRepo()

    class FakeSession:
        def execute(self, _query):
            return SimpleNamespace(mappings=lambda: [persisted_record.__dict__])

        def close(self):
            return None

    monkeypatch.setattr(
        bot_instance_manager_module.db, "get_session", lambda: FakeSession()
    )
    monkeypatch.setattr(bot_instance_manager_module, "UnitOfWork", FakeUOW)

    manager = BotInstanceManager(state_dir=str(tmp_path))

    assert set(manager.instances.keys()) == {"strategy-1-101"}
    recovered = manager.instances["strategy-1-101"]
    assert recovered.status == BotStatus.RUNNING
    assert recovered.process_info["pid"] == 4321
    assert recovered.config.instance_name == "Recovered Strategy"
    assert recovered.config.telegram is not None
    assert recovered.config.telegram.token == "persisted-token"


def test_save_instances_state_syncs_runtime_state_to_database(monkeypatch, tmp_path):
    monkeypatch.setattr(
        BotInstanceManager,
        "_db_persistence_enabled",
        staticmethod(lambda: True),
    )
    now = datetime.now()
    persisted_record = SimpleNamespace(
        instance_id="strategy-1-101",
        network="mainnet",
        strategy="legacy-strategy",
        config={
            "legacy": "value",
            "instance_name": "Persisted Strategy",
            "credentials": {
                "chain_id": "dydx-mainnet-1",
                "address": "dydx1persistedaddress",
                "mnemonic": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
            },
            "trading_params": _strategy_config().trading_params.model_dump(),
        },
        status=SimpleNamespace(value="running"),
        process_id=9999,
        created_at=now,
        updated_at=now,
    )

    class FakeBotsRepo:
        def get_all(self):
            return [persisted_record]

    class FakeUOW:
        def __init__(self, session):
            self.bots = FakeBotsRepo()

    class FakeSession:
        def __init__(self):
            self.commits = 0

        def execute(self, _query):
            return SimpleNamespace(mappings=lambda: [persisted_record.__dict__])

        def commit(self):
            self.commits += 1

        def rollback(self):
            return None

        def close(self):
            return None

    session = FakeSession()
    monkeypatch.setattr(bot_instance_manager_module.db, "get_session", lambda: session)
    monkeypatch.setattr(bot_instance_manager_module, "UnitOfWork", FakeUOW)

    manager = BotInstanceManager(state_dir=str(tmp_path))
    manager.instances["strategy-1-101"].status = BotStatus.STOPPED
    manager.instances["strategy-1-101"].process_info = {
        "last_error": "runtime crashed",
        "exit_code": 7,
    }
    manager.instances["strategy-1-101"].trading_stats = {"active_positions": 2}

    manager._save_instances_state()

    assert session.commits >= 1
    assert persisted_record.status.value == "stopped"
    assert persisted_record.process_id is None
    assert persisted_record.strategy == "cointegration"
    assert persisted_record.config["telegram"] == {}
    assert persisted_record.config["trading_params"]["strategy"] == "cointegration"
    assert persisted_record.config["config_meta"]["schema_version"] == 2
    assert persisted_record.config["config_meta"]["hash_algorithm"] == "sha256"
    assert len(persisted_record.config["config_meta"]["payload_hash"]) == 64
    assert persisted_record.config["runtime_state"]["status"] == "stopped"
    assert persisted_record.config["runtime_state"]["last_error"] == "runtime crashed"
    assert persisted_record.config["runtime_state"]["exit_code"] == 7
    assert (
        persisted_record.config["runtime_state"]["trading_stats"]["active_positions"]
        == 2
    )
    assert not (tmp_path / "instances.json").exists()


def test_save_instances_state_coerces_string_config_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(
        BotInstanceManager,
        "_db_persistence_enabled",
        staticmethod(lambda: True),
    )
    now = datetime.now()
    persisted_record = SimpleNamespace(
        instance_id="strategy-1-101",
        network="testnet",
        strategy="cointegration",
        config=json.dumps(
            {
                "instance_name": "Persisted Strategy",
                "credentials": {
                    "chain_id": "dydx-testnet-4",
                    "address": "dydx1persistedaddress",
                    "mnemonic": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
                },
                "trading_params": _strategy_config().trading_params.model_dump(),
            }
        ),
        status=SimpleNamespace(value="running"),
        process_id=9999,
        created_at=now,
        updated_at=now,
    )

    class FakeBotsRepo:
        def get_all(self):
            return [persisted_record]

    class FakeUOW:
        def __init__(self, session):
            self.bots = FakeBotsRepo()

    class FakeSession:
        def __init__(self):
            self.commits = 0

        def execute(self, _query):
            return SimpleNamespace(
                mappings=lambda: [
                    {
                        "instance_id": persisted_record.instance_id,
                        "network": persisted_record.network,
                        "strategy": persisted_record.strategy,
                        "config": persisted_record.config,
                        "process_id": persisted_record.process_id,
                        "created_at": persisted_record.created_at,
                        "updated_at": persisted_record.updated_at,
                        "status": "RUNNING",
                    }
                ]
            )

        def commit(self):
            self.commits += 1

        def rollback(self):
            return None

        def close(self):
            return None

    session = FakeSession()
    monkeypatch.setattr(bot_instance_manager_module.db, "get_session", lambda: session)
    monkeypatch.setattr(bot_instance_manager_module, "UnitOfWork", FakeUOW)

    manager = BotInstanceManager(state_dir=str(tmp_path))
    manager.instances["strategy-1-101"].status = BotStatus.STOPPED

    manager._save_instances_state()

    assert session.commits >= 1
    assert isinstance(persisted_record.config, dict)
    assert persisted_record.config["config_meta"]["schema_version"] == 2
    assert persisted_record.config["config_meta"]["hash_algorithm"] == "sha256"
    assert persisted_record.config["runtime_state"]["status"] == "stopped"


def test_mark_instance_error_records_runtime_event(monkeypatch, tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config()))

    recorded = {}

    def _fake_record_runtime_event(
        instance_id, event_type, severity, message, details=None
    ):
        recorded["instance_id"] = instance_id
        recorded["event_type"] = event_type
        recorded["severity"] = severity
        recorded["message"] = message
        recorded["details"] = details

    monkeypatch.setattr(manager, "_record_runtime_event", _fake_record_runtime_event)

    changed = manager._mark_instance_error(
        "strategy-1-101", "startup failed", exit_code=9
    )

    assert changed is True
    assert recorded["instance_id"] == "strategy-1-101"
    assert recorded["event_type"] == "bot_runtime_error"
    assert recorded["severity"] == "error"
    assert recorded["message"] == "startup failed"
    assert recorded["details"] == {"exit_code": 9}


def test_recovered_running_instance_is_marked_error_when_pid_is_dead(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        BotInstanceManager,
        "_db_persistence_enabled",
        staticmethod(lambda: True),
    )
    now = datetime.now()
    persisted_record = SimpleNamespace(
        instance_id="strategy-1-101",
        network="testnet",
        strategy="cointegration",
        config={
            "instance_name": "Recovered Strategy",
            "credentials": {
                "chain_id": "dydx-testnet-4",
                "address": "dydx1recoveredaddress",
                "mnemonic": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
            },
            "trading_params": _strategy_config().trading_params.model_dump(),
        },
        status=SimpleNamespace(value="running"),
        process_id=424242,
        created_at=now,
        updated_at=now,
    )

    class FakeBotsRepo:
        def get_all(self):
            return [persisted_record]

    class FakeUOW:
        def __init__(self, session):
            self.bots = FakeBotsRepo()

    class FakeSession:
        def execute(self, _query):
            return SimpleNamespace(mappings=lambda: [persisted_record.__dict__])

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    published = []

    async def _publisher(payload):
        published.append(payload)

    monkeypatch.setattr(
        bot_instance_manager_module.db, "get_session", lambda: FakeSession()
    )
    monkeypatch.setattr(bot_instance_manager_module, "UnitOfWork", FakeUOW)
    monkeypatch.setattr(
        bot_instance_manager_module.psutil,
        "Process",
        lambda pid: (_ for _ in ()).throw(
            bot_instance_manager_module.psutil.NoSuchProcess(pid)
        ),
    )

    manager = BotInstanceManager(state_dir=str(tmp_path))
    manager.set_status_event_publisher(_publisher)

    status = asyncio.run(manager.get_instance_status("strategy-1-101"))

    assert status is not None
    assert status.status == BotStatus.ERROR
    assert manager.instances["strategy-1-101"].status == BotStatus.ERROR
    assert published[-1]["status"] == "error"
    assert "no longer running" in published[-1]["last_error"]


def test_live_auto_recovery_marks_dead_active_runtime_error_by_default(
    monkeypatch, tmp_path
):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config()))
    instance = manager.instances["strategy-1-101"]
    instance.status = BotStatus.RUNNING
    instance.process_info = {"pid": 424242}

    monkeypatch.setattr(
        manager,
        "_resolve_external_runtime_process",
        lambda instance_id: (
            None,
            f"Runtime process for {instance_id} is no longer running",
        ),
    )

    report = asyncio.run(manager.auto_recover_live_runtimes())

    assert report["restart_enabled"] is False
    assert report["checked"] == 1
    assert report["restarted"] == []
    assert report["marked_error"][0]["instance_id"] == "strategy-1-101"
    assert manager.instances["strategy-1-101"].status == BotStatus.ERROR
    assert (
        "no longer running"
        in manager.instances["strategy-1-101"].process_info["last_error"]
    )


def test_live_auto_recovery_restarts_dead_testnet_runtime_when_enabled(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("BOT_AUTO_RECOVER_LIVE_RUNTIMES", "true")
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config()))
    instance = manager.instances["strategy-1-101"]
    instance.status = BotStatus.RUNNING
    instance.process_info = {"pid": 424242}

    monkeypatch.setattr(
        manager,
        "_resolve_external_runtime_process",
        lambda instance_id: (
            None,
            f"Runtime process for {instance_id} is no longer running",
        ),
    )

    async def _fake_start_locked(instance_id):
        manager.instances[instance_id].status = BotStatus.RUNNING
        manager.instances[instance_id].process_info = {
            "pid": 777,
            "started_at": datetime.now(timezone.utc),
        }
        return SimpleNamespace(
            success=True,
            message="started",
            instance_id=instance_id,
            status=BotStatus.RUNNING,
            error=None,
        )

    monkeypatch.setattr(manager, "_start_instance_locked", _fake_start_locked)

    report = asyncio.run(manager.auto_recover_live_runtimes())

    assert report["restart_enabled"] is True
    assert report["restarted"] == ["strategy-1-101"]
    assert report["marked_error"] == []
    assert manager.instances["strategy-1-101"].status == BotStatus.RUNNING
    assert manager.instances["strategy-1-101"].process_info["pid"] == 777
    assert manager.instances["strategy-1-101"].recovery_state is None


def test_live_auto_recovery_does_not_restart_mainnet_without_explicit_gate(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("BOT_AUTO_RECOVER_LIVE_RUNTIMES", "true")
    config = _strategy_config()
    config.trading_params.is_testnet = False
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(config))
    instance = manager.instances["strategy-1-101"]
    instance.status = BotStatus.RUNNING
    instance.process_info = {"pid": 424242}

    monkeypatch.setattr(
        manager,
        "_resolve_external_runtime_process",
        lambda instance_id: (
            None,
            f"Runtime process for {instance_id} is no longer running",
        ),
    )

    async def _fail_start_locked(instance_id):
        raise AssertionError(f"mainnet runtime {instance_id} must not auto-start")

    monkeypatch.setattr(manager, "_start_instance_locked", _fail_start_locked)

    report = asyncio.run(manager.auto_recover_live_runtimes())

    assert report["restart_enabled"] is True
    assert report["allow_mainnet"] is False
    assert report["restarted"] == []
    assert (
        report["marked_error"][0]["reason"]
        == "auto-restart disabled for mainnet runtime"
    )
    assert manager.instances["strategy-1-101"].status == BotStatus.ERROR


def test_dev_recovery_deletes_invalid_non_mainnet_bot_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(
        BotInstanceManager,
        "_db_persistence_enabled",
        staticmethod(lambda: True),
    )
    monkeypatch.setenv("ENVIRONMENT", "development")

    invalid_record = {
        "instance_id": "api-test-bot-855356f2",
        "network": "testnet",
        "strategy": "cointegration",
        "config": {"trading_params": _strategy_config().trading_params.model_dump()},
        "process_id": None,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "status": "STOPPED",
    }

    class FakeSession:
        def __init__(self):
            self.deleted = []
            self.commits = 0

        def execute(self, query, params=None):
            query_text = str(query)
            if "DELETE FROM bot_instances" in query_text:
                delete_params = cast(Dict[str, Any], params)
                self.deleted.append(delete_params["instance_id"])
                return None
            if query_text.lstrip().upper().startswith("DELETE"):
                return None
            return SimpleNamespace(mappings=lambda: [invalid_record])

        def commit(self):
            self.commits += 1

        def rollback(self):
            return None

        def close(self):
            return None

    session = FakeSession()
    monkeypatch.setattr(bot_instance_manager_module.db, "get_session", lambda: session)

    manager = BotInstanceManager(state_dir=str(tmp_path))

    assert manager.instances == {}
    assert session.deleted == ["api-test-bot-855356f2"]
    assert manager.recovery_diagnostics["skipped"] == 1


def test_production_recovery_does_not_delete_invalid_bot_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(
        BotInstanceManager,
        "_db_persistence_enabled",
        staticmethod(lambda: True),
    )
    monkeypatch.setenv("ENVIRONMENT", "production")

    invalid_record = {
        "instance_id": "prod-bot-with-bad-config",
        "network": "testnet",
        "strategy": "cointegration",
        "config": {"trading_params": _strategy_config().trading_params.model_dump()},
        "process_id": None,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "status": "STOPPED",
    }

    class FakeSession:
        def __init__(self):
            self.deleted = []

        def execute(self, query, params=None):
            query_text = str(query)
            if "DELETE FROM bot_instances" in query_text:
                delete_params = cast(Dict[str, Any], params)
                self.deleted.append(delete_params["instance_id"])
                return None
            if query_text.lstrip().upper().startswith("DELETE"):
                return None
            return SimpleNamespace(mappings=lambda: [invalid_record])

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    session = FakeSession()
    monkeypatch.setattr(bot_instance_manager_module.db, "get_session", lambda: session)

    manager = BotInstanceManager(state_dir=str(tmp_path))

    assert manager.instances == {}
    assert session.deleted == []
    assert manager.recovery_diagnostics["skipped"] == 1


def test_dev_recovery_deletes_invalid_mainnet_test_fixture_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(
        BotInstanceManager,
        "_db_persistence_enabled",
        staticmethod(lambda: True),
    )
    monkeypatch.setenv("ENVIRONMENT", "development")

    invalid_record = {
        "instance_id": "lifecycle-test-bot-855356f2",
        "network": "mainnet",
        "strategy": "cointegration",
        "config": {"trading_params": _strategy_config().trading_params.model_dump()},
        "process_id": None,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "status": "STOPPED",
    }

    class FakeSession:
        def __init__(self):
            self.deleted = []

        def execute(self, query, params=None):
            query_text = str(query)
            if "DELETE FROM bot_instances" in query_text:
                delete_params = cast(Dict[str, Any], params)
                self.deleted.append(delete_params["instance_id"])
                return None
            if query_text.lstrip().upper().startswith("DELETE"):
                return None
            return SimpleNamespace(mappings=lambda: [invalid_record])

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    session = FakeSession()
    monkeypatch.setattr(bot_instance_manager_module.db, "get_session", lambda: session)

    manager = BotInstanceManager(state_dir=str(tmp_path))

    assert manager.instances == {}
    assert session.deleted == ["lifecycle-test-bot-855356f2"]
    assert manager.recovery_diagnostics["skipped"] == 1


# ============================================================================
# Credential encryption integration (bot_instances.config at-rest encryption)
# ============================================================================

_CIPHER_KEY_A = base64.b64encode(bytes(range(32))).decode()


@pytest.fixture
def cipher_key(monkeypatch):
    """Provision a credential encryption key and reset the cipher cache."""
    monkeypatch.setenv(cc.ENV_KEY, _CIPHER_KEY_A)
    cc._key_cache = None
    cc._no_key_warned_for.clear()
    yield
    monkeypatch.delenv(cc.ENV_KEY, raising=False)
    cc._key_cache = None
    cc._no_key_warned_for.clear()


def _sealed_strategy_record(now, *, sealed: bool):
    """Return a persisted-record SimpleNamespace with sealed or plaintext creds."""
    plain_credentials = {
        "chain_id": "dydx-testnet-4",
        "address": "dydx1recoveredaddress",
        "mnemonic": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
    }
    base_payload = {
        "instance_name": "Recovered Strategy",
        "credentials": plain_credentials,
        "telegram": {"token": "persisted-token", "chat_id": "persisted-chat"},
        "trading_params": _strategy_config().trading_params.model_dump(),
        "backtesting_params": (
            _strategy_config().backtesting_params.model_dump()
            if _strategy_config().backtesting_params
            else {}
        ),
    }
    config = cc.seal_config_secrets(base_payload) if sealed else dict(base_payload)
    return SimpleNamespace(
        instance_id="strategy-1-101",
        network="testnet",
        strategy="cointegration",
        config=config,
        status=SimpleNamespace(value="running"),
        process_id=4321,
        created_at=now,
        updated_at=now,
    )


def _wire_fake_db(monkeypatch, record):
    class FakeBotsRepo:
        def get_all(self):
            return [record]

    class FakeUOW:
        def __init__(self, session):
            self.bots = FakeBotsRepo()

    class FakeSession:
        def execute(self, _query):
            return SimpleNamespace(mappings=lambda: [record.__dict__])

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(
        bot_instance_manager_module.db, "get_session", lambda: FakeSession()
    )
    monkeypatch.setattr(bot_instance_manager_module, "UnitOfWork", FakeUOW)


def test_persist_instances_to_db_seals_credentials_when_key_set(
    monkeypatch, tmp_path, cipher_key
):
    """With a key provisioned, DB sync seals credentials at rest."""
    monkeypatch.setattr(
        BotInstanceManager, "_db_persistence_enabled", staticmethod(lambda: True)
    )
    now = datetime.now()
    record = _sealed_strategy_record(now, sealed=False)  # start plaintext
    _wire_fake_db(monkeypatch, record)

    manager = BotInstanceManager(state_dir=str(tmp_path))
    manager.instances["strategy-1-101"].status = BotStatus.STOPPED
    manager._save_instances_state()

    stored = record.config
    assert "credentials_sealed" in stored
    assert "credentials" not in stored
    # Plaintext mnemonic must not appear anywhere in the stored payload.
    assert "alpha beta gamma" not in json.dumps(stored)
    # config_meta hash was computed over plaintext (stable), schema bumped to 2.
    assert stored["config_meta"]["schema_version"] == 2


def test_recovery_decrypts_sealed_credentials(monkeypatch, tmp_path, cipher_key):
    """Recovery reads a sealed row and restores plaintext credentials."""
    monkeypatch.setattr(
        BotInstanceManager, "_db_persistence_enabled", staticmethod(lambda: True)
    )
    now = datetime.now()
    record = _sealed_strategy_record(now, sealed=True)
    _wire_fake_db(monkeypatch, record)

    manager = BotInstanceManager(state_dir=str(tmp_path))

    assert set(manager.instances.keys()) == {"strategy-1-101"}
    recovered = manager.instances["strategy-1-101"]
    assert (
        recovered.config.credentials.mnemonic
        == "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
    )
    assert recovered.config.credentials.address == "dydx1recoveredaddress"
    assert recovered.config.telegram.token == "persisted-token"


def test_recovery_handles_legacy_plaintext_when_key_set(
    monkeypatch, tmp_path, cipher_key
):
    """A legacy plaintext row still recovers even with a key provisioned."""
    monkeypatch.setattr(
        BotInstanceManager, "_db_persistence_enabled", staticmethod(lambda: True)
    )
    now = datetime.now()
    record = _sealed_strategy_record(now, sealed=False)
    _wire_fake_db(monkeypatch, record)

    manager = BotInstanceManager(state_dir=str(tmp_path))

    recovered = manager.instances["strategy-1-101"]
    assert (
        recovered.config.credentials.mnemonic
        == "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
    )


# ---------------------------------------------------------------------------
# Coverage-ratchet pass 4 (2026-08-19): stop/lifecycle seams, external psutil
# liveness, auto-recovery, DB-load/dev-cleanup paths, and DB-sync backoff.
# All fakes are local: no real subprocesses, no real psutil probes, no DB.
# ---------------------------------------------------------------------------


class _FakeJobManager:
    """Record-only stand-in for the module-level async_job_manager."""

    def __init__(self, *, fail_on=()):
        self.created = []
        self.running = []
        self.completed = []
        self.failed = []
        self._fail_on = set(fail_on)

    def create_job(
        self,
        *,
        job_type,
        bot_instance_id=None,
        job_id=None,
        parameters=None,
        metadata=None,
    ):
        resolved = job_id or f"{job_type}-{len(self.created) + 1}"
        self.created.append(
            {
                "job_id": resolved,
                "job_type": job_type,
                "bot_instance_id": bot_instance_id,
                "parameters": parameters,
                "metadata": metadata,
            }
        )
        if "create_job" in self._fail_on:
            raise RuntimeError("job create failed")
        return resolved

    def mark_running(self, job_id, *, process_id=None):
        self.running.append((job_id, process_id))
        if "mark_running" in self._fail_on:
            raise RuntimeError("mark running failed")

    def mark_completed(self, job_id, *, result=None, execution_time_ms=None):
        self.completed.append((job_id, result))
        if "mark_completed" in self._fail_on:
            raise RuntimeError("mark completed failed")

    def mark_failed(self, job_id, error, *, traceback_summary=None):
        self.failed.append((job_id, str(error)))


class _FakeSubprocess:
    """Popen stand-in: poll/terminate/kill/wait with optional failures."""

    def __init__(self, *, pid=9001, exit_code=None, wait_error=None):
        self.pid = pid
        self.returncode = exit_code
        self._wait_error = wait_error
        self.terminated = 0
        self.killed = 0
        self.wait_timeouts = []

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated += 1

    def kill(self):
        self.killed += 1

    def wait(self, timeout=None):
        self.wait_timeouts.append(timeout)
        if self._wait_error is not None:
            raise self._wait_error
        return self.returncode if self.returncode is not None else 0


class _FakeExternalProcess:
    """psutil.Process stand-in for recovered-runtime probes."""

    def __init__(
        self,
        *,
        pid=7001,
        cmdline=None,
        running=True,
        zombie=False,
        cmdline_access_denied=False,
        liveness_access_denied=False,
        metrics_access_denied=False,
        metrics_gone=False,
        wait_error=None,
        terminate_error=None,
    ):
        self.pid = pid
        self._cmdline = (
            cmdline
            if cmdline is not None
            else [
                "python",
                "-m",
                "src.main_instance",
                "--instance-id",
                "ext-bot-1",
            ]
        )
        self._running = running
        self._zombie = zombie
        self._cmdline_access_denied = cmdline_access_denied
        self._liveness_access_denied = liveness_access_denied
        self._metrics_access_denied = metrics_access_denied
        self._metrics_gone = metrics_gone
        self._wait_error = wait_error
        self._terminate_error = terminate_error
        self.terminated = 0
        self.killed = 0

    def cmdline(self):
        if self._cmdline_access_denied:
            raise psutil.AccessDenied(pid=self.pid)
        return list(self._cmdline)

    def is_running(self):
        if self._liveness_access_denied:
            raise psutil.AccessDenied(pid=self.pid)
        return self._running

    def status(self):
        return psutil.STATUS_ZOMBIE if self._zombie else "running"

    def cpu_percent(self):
        if self._metrics_gone:
            raise psutil.NoSuchProcess(pid=self.pid)
        if self._metrics_access_denied:
            raise psutil.AccessDenied(pid=self.pid)
        return 7.5

    def memory_info(self):
        if self._metrics_gone:
            raise psutil.NoSuchProcess(pid=self.pid)
        if self._metrics_access_denied:
            raise psutil.AccessDenied(pid=self.pid)
        return SimpleNamespace(rss=64 * 1024 * 1024)

    def terminate(self):
        if self._terminate_error is not None:
            raise self._terminate_error
        self.terminated += 1

    def kill(self):
        self.killed += 1

    def wait(self, timeout=None):
        if self._wait_error is not None:
            raise self._wait_error
        return 0


class _SessionStub:
    """SQLAlchemy session stand-in for raw-execute recovery/sync paths."""

    def __init__(self, *, mapping_rows=None, delete_error=False, commit_error=None):
        self.executed = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0
        self._mapping_rows = list(mapping_rows or [])
        self._delete_error = delete_error
        self._commit_error = commit_error

    def execute(self, query, params=None):
        self.executed.append((str(query), params))
        if self._delete_error and str(query).strip().upper().startswith("DELETE"):
            raise RuntimeError("delete exploded")
        return SimpleNamespace(
            mappings=lambda: [dict(row) for row in self._mapping_rows]
        )

    def commit(self):
        self.commits += 1
        if self._commit_error is not None:
            raise self._commit_error

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed += 1


class _BotsRepoStub:
    def __init__(
        self, *, records=None, stats=None, create_error=None, lookup_error=None
    ):
        self.records = list(records or [])
        self._stats = stats
        self._create_error = create_error
        self._lookup_error = lookup_error
        self.created = []

    def get_all(self):
        return list(self.records)

    def get_by_instance_id(self, instance_id):
        if self._lookup_error is not None:
            raise self._lookup_error
        return next((r for r in self.records if r.instance_id == instance_id), None)

    def create_bot(self, **kwargs):
        if self._create_error is not None:
            raise self._create_error
        self.created.append(kwargs)

    def get_statistics(self, instance_id):
        if isinstance(self._stats, Exception):
            raise self._stats
        return dict(self._stats or {})


class _EventsRepoStub:
    def __init__(self):
        self.logged = []

    def log_event(self, *args, **kwargs):
        self.logged.append((args, kwargs))


def _wire_db(
    monkeypatch,
    *,
    mapping_rows=None,
    records=None,
    stats=None,
    create_error=None,
    lookup_error=None,
    session=None,
):
    """Re-enable DB persistence for one test and route it through fakes."""
    monkeypatch.setattr(
        BotInstanceManager, "_db_persistence_enabled", staticmethod(lambda: True)
    )
    sess = session if session is not None else _SessionStub(mapping_rows=mapping_rows)
    uow = SimpleNamespace(
        bots=_BotsRepoStub(
            records=records,
            stats=stats,
            create_error=create_error,
            lookup_error=lookup_error,
        ),
        events=_EventsRepoStub(),
    )
    monkeypatch.setattr(bot_instance_manager_module.db, "get_session", lambda: sess)
    monkeypatch.setattr(bot_instance_manager_module, "UnitOfWork", lambda s: uow)
    return sess, uow


def _manager_with_running_process(
    tmp_path,
    instance_id="strategy-3-5",
    *,
    exit_code=None,
    wait_error=None,
    pid=9001,
):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config(instance_id)))
    instance = manager.instances[instance_id]
    instance.status = BotStatus.RUNNING
    instance.process_info = {
        "pid": pid,
        "started_at": datetime.now(timezone.utc),
    }
    process = _FakeSubprocess(pid=pid, exit_code=exit_code, wait_error=wait_error)
    manager.processes[instance_id] = process
    return manager, process


def _live_config(instance_id: str, *, is_testnet: bool = True) -> BotInstanceConfig:
    config = _strategy_config(instance_id)
    config.trading_params.is_testnet = is_testnet
    return config


# --- env / backoff helpers -------------------------------------------------


def test_read_positive_float_env_variants(monkeypatch):
    read = BotInstanceManager._read_positive_float_env
    monkeypatch.delenv("BOT_TEST_FLOAT", raising=False)
    assert read("BOT_TEST_FLOAT", 1.5) == 1.5
    monkeypatch.setenv("BOT_TEST_FLOAT", "")
    assert read("BOT_TEST_FLOAT", 2.0) == 2.0
    monkeypatch.setenv("BOT_TEST_FLOAT", "  ")
    assert read("BOT_TEST_FLOAT", 2.0) == 2.0
    monkeypatch.setenv("BOT_TEST_FLOAT", "garbage")
    assert read("BOT_TEST_FLOAT", 2.5) == 2.5
    monkeypatch.setenv("BOT_TEST_FLOAT", "-3")
    assert read("BOT_TEST_FLOAT", 2.5) == 0.0
    monkeypatch.setenv("BOT_TEST_FLOAT", "4.75")
    assert read("BOT_TEST_FLOAT", 2.5) == 4.75


def test_looks_like_pool_overload_matches_only_overload_errors():
    check = BotInstanceManager._looks_like_pool_overload
    assert check(RuntimeError("QueuePool limit of size 5 overflow 10 reached")) is True
    assert (
        check(
            RuntimeError("connection timed out; see sqlalche.me/e/20/3o7r for details")
        )
        is True
    )
    assert check(RuntimeError("connection timed out to host")) is False
    assert check(ValueError("ordinary failure")) is False


def test_db_sync_backoff_activation_skips_and_recovers(monkeypatch, tmp_path):
    monkeypatch.setenv("BOT_DB_SYNC_COOLDOWN_SECONDS", "30")
    monkeypatch.setenv("BOT_DB_SYNC_BACKOFF_LOG_EVERY_SECONDS", "15")
    manager = BotInstanceManager(state_dir=str(tmp_path))
    sessions = []
    _wire_db(monkeypatch, session=None)
    monkeypatch.setattr(
        bot_instance_manager_module.db,
        "get_session",
        lambda: sessions.append(_SessionStub()) or sessions[-1],
    )

    manager._activate_db_sync_backoff(RuntimeError("QueuePool limit reached"))
    assert manager._db_sync_backoff_active() is True
    diagnostics = manager.get_db_sync_backoff_diagnostics()
    assert diagnostics["active"] is True
    assert 0 < diagnostics["remaining_seconds"] <= 30
    assert diagnostics["cooldown_seconds"] == 30.0

    # While the cooldown is active, sync short-circuits without opening a session.
    manager._persist_instances_to_db()
    assert sessions == []

    # Notice-window elapsed: the throttled warning path still skips the sync.
    manager._db_sync_backoff_notice_after_monotonic = time.monotonic() - 1
    manager._persist_instances_to_db()
    assert sessions == []

    # Cooldown expiry clears the flag on the next successful sync.
    manager._db_sync_backoff_until_monotonic = time.monotonic() - 1
    assert manager._db_sync_backoff_active() is False
    manager._persist_instances_to_db()
    assert len(sessions) == 1
    assert manager._db_sync_backoff_until_monotonic == 0.0


def test_db_sync_pool_overload_failure_activates_backoff(monkeypatch, tmp_path):
    monkeypatch.setattr(
        BotInstanceManager, "_db_persistence_enabled", staticmethod(lambda: True)
    )
    manager = BotInstanceManager(state_dir=str(tmp_path))

    def _boom():
        raise RuntimeError("QueuePool limit of size 5 overflow 10 reached")

    monkeypatch.setattr(bot_instance_manager_module.db, "get_session", _boom)
    manager._persist_instances_to_db()
    assert manager._db_sync_backoff_active() is True


def test_db_sync_failure_rolls_back_without_backoff(monkeypatch, tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("strategy-1-101")))
    manager.instances["strategy-1-101"].status = BotStatus.RUNNING

    session = _SessionStub(commit_error=RuntimeError("commit failed"))
    record = SimpleNamespace(
        instance_id="strategy-1-101",
        network="testnet",
        strategy="cointegration",
        config={},
        process_id=None,
        status=SimpleNamespace(value="stopped"),
    )
    _wire_db(monkeypatch, records=[record], session=session)

    manager._persist_instances_to_db()

    assert session.rollbacks == 1
    assert manager._db_sync_backoff_active() is False


def test_resolve_max_instances_env_and_garbage(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("BOT_MAX_INSTANCES", raising=False)
    manager = BotInstanceManager(state_dir=str(tmp_path), max_instances=4)
    assert manager.max_instances == 4

    monkeypatch.setenv("BOT_MAX_INSTANCES", "6")
    assert BotInstanceManager(state_dir=str(tmp_path / "s2")).max_instances == 6

    monkeypatch.setenv("BOT_MAX_INSTANCES", "not-a-number")
    assert BotInstanceManager(state_dir=str(tmp_path / "s3")).max_instances == 10

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("BOT_MAX_INSTANCES", raising=False)
    assert BotInstanceManager(state_dir=str(tmp_path / "s4")).max_instances == 0


# --- persistence seams ------------------------------------------------------


def test_ensure_instance_record_creates_sealed_row_when_missing(monkeypatch, tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    session, uow = _wire_db(monkeypatch)
    instance = BotInstanceState(
        instance_id="strategy-8-1",
        config=_strategy_config("strategy-8-1"),
        status=BotStatus.STOPPED,
        process_info={},
        trading_stats={},
        created_at=datetime.now(timezone.utc),
        last_update=datetime.now(timezone.utc),
    )

    manager._ensure_instance_record(instance)

    assert len(uow.bots.created) == 1
    created = uow.bots.created[0]
    assert created["instance_id"] == "strategy-8-1"
    assert created["network"] == "testnet"
    assert created["config"]["config_meta"]["schema_version"] == 2
    assert created["config"]["config_meta"]["hash_algorithm"] == "sha256"
    assert created["config"]["credentials"]["address"]


def test_ensure_instance_record_skips_existing_and_survives_failure(
    monkeypatch, tmp_path
):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    record = SimpleNamespace(
        instance_id="strategy-8-2",
        network="testnet",
        strategy="cointegration",
        config={},
        process_id=None,
        status=SimpleNamespace(value="stopped"),
    )
    session, uow = _wire_db(monkeypatch, records=[record])
    state = BotInstanceState(
        instance_id="strategy-8-2",
        config=_strategy_config("strategy-8-2"),
        status=BotStatus.STOPPED,
        process_info={},
        trading_stats={},
        created_at=datetime.now(timezone.utc),
        last_update=datetime.now(timezone.utc),
    )

    manager._ensure_instance_record(state)
    assert uow.bots.created == []

    session_rollbacks = _SessionStub()
    _wire_db(monkeypatch, session=session_rollbacks, create_error=RuntimeError("nope"))
    manager._ensure_instance_record(state)
    assert session_rollbacks.rollbacks == 1
    assert session_rollbacks.closed == 1


def test_record_runtime_event_paths(monkeypatch, tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    record = SimpleNamespace(
        id=41,
        instance_id="strategy-8-3",
        network="testnet",
        strategy="cointegration",
        config={},
        process_id=None,
        status=SimpleNamespace(value="running"),
    )
    session, uow = _wire_db(monkeypatch, records=[record])

    manager._record_runtime_event(
        "strategy-8-3", "bot_runtime_error", "error", "worker crashed"
    )
    assert len(uow.events.logged) == 1
    args, kwargs = uow.events.logged[0]
    assert args[0] == 41
    assert args[1:] == ("bot_runtime_error", "error", "worker crashed")

    # Unknown instance id: no bot row, nothing logged.
    manager._record_runtime_event("ghost", "bot_runtime_error", "error", "x")
    assert len(uow.events.logged) == 1

    # Lookup failure: rollback, no raise.
    failure_session = _SessionStub()
    _wire_db(monkeypatch, session=failure_session, lookup_error=RuntimeError("db down"))
    manager._record_runtime_event(
        "strategy-8-3", "bot_runtime_error", "error", "worker crashed"
    )
    assert failure_session.rollbacks == 1


def test_persist_instances_to_db_syncs_runtime_state(monkeypatch, tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    record = SimpleNamespace(
        instance_id="strategy-1-101",
        network="mainnet",
        strategy="old-strategy",
        config={"legacy": True},
        process_id=None,
        status=SimpleNamespace(value="running"),
    )
    session, _uow = _wire_db(monkeypatch, records=[record])
    asyncio.run(manager.create_instance(_strategy_config("strategy-1-101")))
    instance = manager.instances["strategy-1-101"]
    instance.status = BotStatus.RUNNING
    instance.process_info = {
        "pid": 555,
        "started_at": datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc),
        "last_error": None,
        "exit_code": None,
    }
    instance.trading_stats = {"total_trades": 2}

    manager._save_instances_state()

    assert session.commits >= 1
    assert record.network == "testnet"
    assert record.strategy == "cointegration"
    assert record.process_id == 555
    assert record.status.name == "RUNNING"
    runtime_state = record.config["runtime_state"]
    assert runtime_state["status"] == "running"
    assert runtime_state["process_id"] == 555
    assert runtime_state["started_at"] == "2026-08-19T12:00:00+00:00"
    assert runtime_state["trading_stats"] == {"total_trades": 2}
    assert record.config["config_meta"]["schema_version"] == 2
    assert record.config["legacy"] is True


def test_update_instance_trading_stats_merges_database_stats(monkeypatch, tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("bot-stats-1")))

    _wire_db(monkeypatch, stats={"total_trades": 4, "win_rate": 0.5})
    manager._update_instance_trading_stats("bot-stats-1")
    assert manager.instances["bot-stats-1"].trading_stats["total_trades"] == 4
    assert manager.instances["bot-stats-1"].trading_stats["source"] == "database"

    _wire_db(monkeypatch, stats={})
    manager.instances["bot-stats-1"].trading_stats.pop("source", None)
    manager._update_instance_trading_stats("bot-stats-1")
    assert "source" not in manager.instances["bot-stats-1"].trading_stats

    failing_session = _SessionStub()
    _wire_db(
        monkeypatch,
        stats=RuntimeError("stats query failed"),
        session=failing_session,
    )
    manager._update_instance_trading_stats("bot-stats-1")
    assert failing_session.rollbacks == 1


def test_save_instances_state_writes_legacy_snapshot_when_enabled(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("BOT_WRITE_LEGACY_STATE_SNAPSHOT", "true")
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("bot-snap-1")))

    manager._save_instances_state()

    snapshot = json.loads((tmp_path / "instances.json").read_text())
    assert snapshot["instances"][0]["instance_id"] == "bot-snap-1"
    assert snapshot["instances"][0]["config"]["instance_id"] == "bot-snap-1"
    assert "last_saved" in snapshot

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(json, "dump", _boom)
    manager._save_instances_state()  # must not raise


# --- DB recovery paths ------------------------------------------------------


def test_load_existing_instances_marks_source_unavailable_on_db_error(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        BotInstanceManager, "_db_persistence_enabled", staticmethod(lambda: True)
    )

    def _boom():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(bot_instance_manager_module.db, "get_session", _boom)
    manager = BotInstanceManager(state_dir=str(tmp_path))

    diagnostics = manager.get_recovery_diagnostics()
    assert diagnostics["source"] == "database_unavailable"
    assert diagnostics["last_error"] == "connection refused"
    assert diagnostics["loaded"] == 0


def test_load_existing_instances_from_db_hydrates_rows(monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    full_row = {
        "instance_id": "strategy-6-1",
        "network": "testnet",
        "strategy": "cointegration",
        "config": {
            "credentials": {
                "chain_id": "dydx-testnet-4",
                "address": "dydx1fullrow",
                "mnemonic": "alpha beta gamma delta epsilon zeta eta theta",
            },
            "trading_params": {"strategy": "cointegration"},
            "runtime_state": {
                "last_error": "boom",
                "exit_code": 3,
                "trading_stats": {"total_trades": 9},
            },
        },
        "process_id": 4321,
        "created_at": now,
        "updated_at": now,
        "status": SimpleNamespace(value="running"),
    }
    legacy_status_row = dict(full_row)
    legacy_status_row = {
        **full_row,
        "instance_id": "strategy-6-2",
        "process_id": None,
        "status": "error",
        "config": {
            "credentials": {
                "address": "dydx1legacy",
                "mnemonic": "alpha beta gamma delta epsilon zeta eta theta",
            },
        },
    }
    session, _uow = _wire_db(monkeypatch, mapping_rows=[full_row, legacy_status_row])
    manager = BotInstanceManager(state_dir=str(tmp_path))

    assert set(manager.instances) == {"strategy-6-1", "strategy-6-2"}
    first = manager.instances["strategy-6-1"]
    assert first.status == BotStatus.RUNNING
    assert first.process_info == {"pid": 4321, "last_error": "boom", "exit_code": 3}
    assert first.trading_stats == {"total_trades": 9}
    assert manager.instances["strategy-6-2"].status == BotStatus.ERROR
    assert manager.instances["strategy-6-2"].process_info == {}
    diagnostics = manager.get_recovery_diagnostics()
    assert diagnostics["source"] == "database"
    assert diagnostics["attempted"] == 2
    assert diagnostics["loaded"] == 2
    assert session.closed >= 1


def test_load_existing_instances_from_db_deletes_invalid_dev_rows(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("BOT_DEV_CLEAN_INVALID_BOT_ROWS", "true")
    now = datetime.now(timezone.utc)
    invalid_row = {
        "instance_id": "fixture-bot-broken",
        "network": "testnet",
        "strategy": "cointegration",
        "config": {"credentials": {"address": "", "mnemonic": "secret"}},
        "process_id": None,
        "created_at": now,
        "updated_at": now,
        "status": "stopped",
    }
    session, _uow = _wire_db(monkeypatch, mapping_rows=[invalid_row])
    manager = BotInstanceManager(state_dir=str(tmp_path))

    assert manager.instances == {}
    diagnostics = manager.get_recovery_diagnostics()
    assert diagnostics["skipped"] == 1
    assert diagnostics["skipped_instances"][0]["instance_id"] == "fixture-bot-broken"
    deletes = [
        q for q, _p in session.executed if q.strip().upper().startswith("DELETE")
    ]
    assert len(deletes) == 8  # 7 dependent tables + bot_instances
    assert session.commits >= 1

    # Mainnet rows without a test marker are never purged.
    monkeypatch.setenv("BOT_DEV_CLEAN_INVALID_BOT_ROWS", "true")
    mainnet_row = dict(invalid_row, instance_id="prod-live-9", network="mainnet")
    guarded_session, _uow2 = _wire_db(monkeypatch, mapping_rows=[mainnet_row])
    BotInstanceManager(state_dir=str(tmp_path / "m2"))
    deletes = [
        q
        for q, _p in guarded_session.executed
        if q.strip().upper().startswith("DELETE")
    ]
    assert deletes == []

    # A delete failure rolls back but does not abort recovery.
    failing_session = _SessionStub(mapping_rows=[invalid_row], delete_error=True)
    _wire_db(monkeypatch, session=failing_session)
    manager3 = BotInstanceManager(state_dir=str(tmp_path / "m3"))
    assert manager3.instances == {}
    assert failing_session.rollbacks >= 1


def test_dev_invalid_recovery_cleanup_gates(monkeypatch):
    check = BotInstanceManager._dev_invalid_recovery_cleanup_enabled
    record = SimpleNamespace(network="testnet", instance_id="bot-1")

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("BOT_DEV_CLEAN_INVALID_BOT_ROWS", "false")
    assert check(record) is False

    monkeypatch.setenv("BOT_DEV_CLEAN_INVALID_BOT_ROWS", "true")
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert check(record) is False

    monkeypatch.setenv("ENVIRONMENT", "development")
    assert check(record) is True
    assert check(SimpleNamespace(network="mainnet", instance_id="prod-1")) is False
    assert check(SimpleNamespace(network="mainnet", instance_id="prod-test-1")) is True


def test_load_existing_instances_from_disk_snapshot_and_corruption(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    config_dump = _strategy_config("bot-disk-1").model_dump()
    snapshot = {
        "instances": [
            {
                "instance_id": "bot-disk-1",
                "config": config_dump,
                "trading_stats": {"wins": 1},
                "created_at": "2026-08-01T10:00:00+00:00",
            }
        ]
    }
    (tmp_path / "instances.json").write_text(json.dumps(snapshot))

    manager._load_existing_instances_from_disk()

    assert "bot-disk-1" in manager.instances
    assert manager.instances["bot-disk-1"].status == BotStatus.STOPPED
    assert manager.instances["bot-disk-1"].trading_stats == {"wins": 1}

    (tmp_path / "instances.json").write_text("{not json")
    manager2 = BotInstanceManager(state_dir=str(tmp_path / "second"))
    (tmp_path / "second" / "instances.json").write_text("{not json")
    manager2._load_existing_instances_from_disk()
    assert manager2.instances == {}
    assert manager2.recovery_diagnostics["last_error"]


def test_coerce_record_config_payload_variants(monkeypatch):
    coerce = BotInstanceManager._coerce_record_config_payload
    assert coerce(None) == {}
    assert coerce("") == {}
    assert coerce("   ") == {}
    assert coerce("not-json{") == {}
    assert coerce("[1,2,3]") == {}
    assert coerce('{"a": 1}') == {"a": 1}
    assert coerce({"b": 2}) == {"b": 2}

    def _boom(payload):
        raise cc.CredentialDecryptionError("key mismatch")

    monkeypatch.setattr(bot_instance_manager_module, "open_config_secrets", _boom)
    assert coerce({"c": 3}) == {"c": 3}


def test_build_instance_config_from_record_defaults_and_skips(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    now = datetime.now(timezone.utc)

    missing_address = SimpleNamespace(
        instance_id="bot-x",
        network="testnet",
        strategy="cointegration",
        config={"credentials": {"mnemonic": "alpha beta"}},
        created_at=now,
        updated_at=now,
    )
    assert manager._build_instance_config_from_record(missing_address) is None
    assert manager.get_recovery_diagnostics()["skipped"] == 1

    missing_mnemonic = SimpleNamespace(
        instance_id="bot-x",
        network="testnet",
        strategy="cointegration",
        config={"credentials": {"address": "dydx1abc"}},
        created_at=now,
        updated_at=now,
    )
    assert manager._build_instance_config_from_record(missing_mnemonic) is None
    assert manager.get_recovery_diagnostics()["skipped"] == 2

    mainnet_default = SimpleNamespace(
        instance_id="bot-y",
        network="mainnet",
        strategy="pair-trade",
        config={
            "credentials": {
                "address": "dydx1main",
                "mnemonic": "alpha beta gamma",
            },
            "trading_params": {"strategy": ""},
            "telegram": {"token": "tok", "chat_id": "chat"},
            "backtesting_params": {"max_history_days": 60},
        },
        created_at=now,
        updated_at=now,
    )
    config = manager._build_instance_config_from_record(mainnet_default)
    assert config is not None
    assert config.trading_params.is_testnet is False
    assert config.trading_params.strategy == "pair-trade"
    assert config.telegram is not None and config.telegram.token == "tok"
    assert config.backtesting_params is not None
    assert config.backtesting_params.max_history_days == 60


def test_coerce_record_status_variants():
    manager = BotInstanceManager.__new__(BotInstanceManager)
    assert manager._coerce_record_status("running") == BotStatus.RUNNING
    assert (
        manager._coerce_record_status(SimpleNamespace(value="error")) == BotStatus.ERROR
    )
    assert manager._coerce_record_status(BotStatus.DEGRADED) == BotStatus.DEGRADED
    assert manager._coerce_record_status("total-nonsense") == BotStatus.STOPPED


# --- liveness / psutil seams ------------------------------------------------


def test_resolve_external_runtime_process_branches(tmp_path, monkeypatch):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("ext-bot-1")))

    assert manager._resolve_external_runtime_process("ghost") == (None, None)

    manager.processes["ext-bot-1"] = _FakeSubprocess()
    assert manager._resolve_external_runtime_process("ext-bot-1") == (None, None)
    del manager.processes["ext-bot-1"]

    instance = manager.instances["ext-bot-1"]
    instance.process_info.pop("pid", None)
    _process, error = manager._resolve_external_runtime_process("ext-bot-1")
    assert _process is None and "not attached" in error

    instance.process_info["pid"] = "not-a-number"
    _process, error = manager._resolve_external_runtime_process("ext-bot-1")
    assert _process is None and "invalid" in error

    def _no_such_process(pid):
        raise psutil.NoSuchProcess(pid=pid)

    monkeypatch.setattr(psutil, "Process", _no_such_process)
    instance.process_info["pid"] = 12345
    _process, error = manager._resolve_external_runtime_process("ext-bot-1")
    assert _process is None and "no longer running" in error

    fake = _FakeExternalProcess(
        pid=12345,
        cmdline=["python", "somewhere-else", "--serve", "http"],
    )
    monkeypatch.setattr(psutil, "Process", lambda pid: fake)
    _process, error = manager._resolve_external_runtime_process("ext-bot-1")
    assert _process is None and "different process" in error

    fake_ok = _FakeExternalProcess(pid=12345, cmdline_access_denied=True)
    monkeypatch.setattr(psutil, "Process", lambda pid: fake_ok)
    process, error = manager._resolve_external_runtime_process("ext-bot-1")
    assert process is fake_ok and error is None


def test_mark_instance_liveness_verified_transitions(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    assert manager._mark_instance_liveness_verified("ghost") is False

    asyncio.run(manager.create_instance(_strategy_config("bot-live-1")))
    instance = manager.instances["bot-live-1"]
    instance.status = BotStatus.DEGRADED
    instance.recovery_state = "degraded"
    instance.recovery_reason = "stale heartbeat"

    assert manager._mark_instance_liveness_verified("bot-live-1", process_id=77) is True
    assert instance.status == BotStatus.RUNNING
    assert instance.recovery_state is None
    assert instance.recovery_reason is None
    assert instance.last_heartbeat is not None
    assert instance.process_info["pid"] == 77


def test_refresh_instance_liveness_external_branches(tmp_path, monkeypatch):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("ext-bot-2")))
    instance = manager.instances["ext-bot-2"]
    instance.status = BotStatus.RUNNING
    instance.process_info["pid"] = 7002

    alive = _fake_external_for("ext-bot-2", 7002)
    monkeypatch.setattr(psutil, "Process", lambda pid: alive)
    assert manager._refresh_instance_liveness_from_process("ext-bot-2") is True
    assert instance.last_heartbeat is not None

    zombie = _fake_external_for("ext-bot-2", 7002, zombie=True)
    monkeypatch.setattr(psutil, "Process", lambda pid: zombie)
    assert manager._refresh_instance_liveness_from_process("ext-bot-2") is False

    denied = _fake_external_for("ext-bot-2", 7002, liveness_access_denied=True)
    monkeypatch.setattr(psutil, "Process", lambda pid: denied)
    assert manager._refresh_instance_liveness_from_process("ext-bot-2") is True

    def _gone(pid):
        raise psutil.NoSuchProcess(pid=pid)

    monkeypatch.setattr(psutil, "Process", _gone)
    assert manager._refresh_instance_liveness_from_process("ext-bot-2") is False

    instance.process_info.pop("pid", None)
    assert manager._refresh_instance_liveness_from_process("ext-bot-2") is False


def test_mark_instance_error_transitions_and_event_recording(monkeypatch, tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    assert manager._mark_instance_error("ghost", "missing") is False

    record = SimpleNamespace(
        id=77,
        instance_id="bot-err-1",
        network="testnet",
        strategy="cointegration",
        config={},
        process_id=None,
        status=SimpleNamespace(value="running"),
    )
    session, uow = _wire_db(monkeypatch, records=[record])
    asyncio.run(manager.create_instance(_strategy_config("bot-err-1")))
    manager.processes["bot-err-1"] = _FakeSubprocess()
    manager._open_instance_log("bot-err-1")

    changed = manager._mark_instance_error("bot-err-1", "worker crashed", exit_code=11)
    assert changed is True
    instance = manager.instances["bot-err-1"]
    assert instance.status == BotStatus.ERROR
    assert instance.process_info["exit_code"] == 11
    assert instance.process_info["last_error"] == "worker crashed"
    assert "pid" not in instance.process_info
    assert "bot-err-1" not in manager.processes
    assert "bot-err-1" not in manager.log_handles
    assert len(uow.events.logged) == 1
    assert uow.events.logged[0][0][3] == "worker crashed"

    assert manager._mark_instance_error("bot-err-1", "again") is False
    assert len(uow.events.logged) == 1


# --- lifecycle: create / start ----------------------------------------------


def test_create_instance_duplicate_limit_and_risk_rejection(tmp_path, monkeypatch):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    first = asyncio.run(manager.create_instance(_strategy_config("bot-c-1")))
    assert first.success is True

    duplicate = asyncio.run(manager.create_instance(_strategy_config("bot-c-1")))
    assert duplicate.success is False
    assert "already exists" in duplicate.message

    capped = BotInstanceManager(state_dir=str(tmp_path / "cap"), max_instances=1)
    asyncio.run(capped.create_instance(_strategy_config("bot-c-2")))
    over = asyncio.run(capped.create_instance(_strategy_config("bot-c-3")))
    assert over.success is False
    assert "Maximum instances limit reached (1)" in over.message

    def _reject(payload):
        raise ValueError("unsupported live risk controls")

    monkeypatch.setattr(
        bot_instance_manager_module,
        "assert_supported_live_risk_controls",
        _reject,
    )
    rejected = asyncio.run(manager.create_instance(_strategy_config("bot-c-4")))
    assert rejected.success is False
    assert "Error creating instance" in rejected.message


def test_start_instance_rejects_when_lifecycle_lock_held(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("bot-lock-1")))

    async def _scenario():
        lock = manager._get_instance_lock("bot-lock-1")
        async with lock:
            return await manager.start_instance("bot-lock-1")

    result = asyncio.run(_scenario())
    assert result.success is False
    assert "lifecycle operation in progress" in result.message


def test_start_instance_not_found_and_already_active(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    result = asyncio.run(manager.start_instance("ghost"))
    assert result.success is False
    assert "not found" in result.message

    asyncio.run(manager.create_instance(_strategy_config("bot-a-1")))
    manager.instances["bot-a-1"].status = BotStatus.RUNNING
    active = asyncio.run(manager.start_instance("bot-a-1"))
    assert active.success is False
    assert "already running" in active.message


def test_start_instance_success_job_lifecycle_and_telegram_env(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_STARTUP_GRACE_SECONDS", "0")
    manager = BotInstanceManager(state_dir=str(tmp_path))
    config = _strategy_config("strategy-2-9")
    config.telegram = TelegramConfig(token="tok-123", chat_id="chat-9")
    asyncio.run(manager.create_instance(config))

    jobs = _FakeJobManager()
    monkeypatch.setattr(bot_instance_manager_module, "async_job_manager", jobs)
    process = _FakeSubprocess(pid=777)
    popen_kwargs = {}

    def _fake_popen(*args, **kwargs):
        popen_kwargs.update(kwargs)
        return process

    monkeypatch.setattr(bot_instance_manager_module.subprocess, "Popen", _fake_popen)

    result = asyncio.run(manager.start_instance("strategy-2-9"))

    assert result.success is True
    assert result.data == {"process_id": 777}
    assert popen_kwargs["env"]["TELEGRAM_BOT_TOKEN"] == "tok-123"
    assert popen_kwargs["env"]["TELEGRAM_CHAT_ID"] == "chat-9"
    assert popen_kwargs["env"]["BOT_INSTANCE_ID"] == "strategy-2-9"
    assert jobs.created[0]["job_type"] == "live_runtime"
    assert jobs.created[0]["parameters"] == {"action": "start"}
    assert jobs.running == [(jobs.created[0]["job_id"], 777)]
    assert jobs.completed == [
        (jobs.created[0]["job_id"], {"process_id": 777, "status": "running"})
    ]
    assert jobs.failed == []
    instance = manager.instances["strategy-2-9"]
    assert instance.status == BotStatus.RUNNING
    assert instance.process_info["pid"] == 777
    assert instance.process_info["cmd"].endswith("--instance-id strategy-2-9")


def test_start_instance_popen_failure_marks_error(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_STARTUP_GRACE_SECONDS", "0")
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("strategy-2-10")))
    published = []

    async def _publisher(payload):
        published.append(payload)

    manager.set_status_event_publisher(_publisher)
    jobs = _FakeJobManager()
    monkeypatch.setattr(bot_instance_manager_module, "async_job_manager", jobs)

    def _popen_boom(*args, **kwargs):
        raise OSError("spawn denied")

    monkeypatch.setattr(bot_instance_manager_module.subprocess, "Popen", _popen_boom)

    result = asyncio.run(manager.start_instance("strategy-2-10"))

    assert result.success is False
    assert "spawn denied" in result.message
    assert manager.instances["strategy-2-10"].status == BotStatus.ERROR
    assert jobs.failed and "spawn denied" in jobs.failed[0][1]
    assert published[-1]["event"] == "error"


def test_start_instance_job_completion_failure_fails_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_STARTUP_GRACE_SECONDS", "0")
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("bot-jf-1")))
    jobs = _FakeJobManager(fail_on={"mark_completed"})
    monkeypatch.setattr(bot_instance_manager_module, "async_job_manager", jobs)
    monkeypatch.setattr(
        bot_instance_manager_module.subprocess,
        "Popen",
        lambda *a, **k: _FakeSubprocess(pid=778),
    )

    result = asyncio.run(manager.start_instance("bot-jf-1"))

    assert result.success is False
    assert manager.instances["bot-jf-1"].status == BotStatus.ERROR
    assert jobs.failed and "mark completed failed" in jobs.failed[0][1]


def test_start_instance_fast_exit_without_log_tail(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_STARTUP_GRACE_SECONDS", "0")
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("bot-fe-1")))
    monkeypatch.setattr(
        bot_instance_manager_module.subprocess,
        "Popen",
        lambda *a, **k: _FakeSubprocess(pid=779, exit_code=2),
    )

    result = asyncio.run(manager.start_instance("bot-fe-1"))

    assert result.success is False
    assert "exit_code=2" in result.message
    assert manager.instances["bot-fe-1"].process_info["exit_code"] == 2


# --- lifecycle: stop ---------------------------------------------------------


def test_stop_instance_not_found_already_stopped_and_locked(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    missing = asyncio.run(manager.stop_instance("ghost"))
    assert missing.success is False
    assert "not found" in missing.message

    asyncio.run(manager.create_instance(_strategy_config("bot-s-1")))
    stopped = asyncio.run(manager.stop_instance("bot-s-1"))
    assert stopped.success is False
    assert "already stopped" in stopped.message

    async def _scenario():
        lock = manager._get_instance_lock("bot-s-1")
        async with lock:
            return await manager.stop_instance("bot-s-1")

    busy = asyncio.run(_scenario())
    assert busy.success is False
    assert "lifecycle operation in progress" in busy.message


def test_stop_instance_graceful_attached_process(tmp_path, monkeypatch):
    manager, process = _manager_with_running_process(tmp_path)
    jobs = _FakeJobManager()
    monkeypatch.setattr(bot_instance_manager_module, "async_job_manager", jobs)
    manager._open_instance_log("strategy-3-5")

    result = asyncio.run(manager.stop_instance("strategy-3-5"))

    assert result.success is True
    assert result.status == BotStatus.STOPPED
    assert process.terminated == 1
    assert process.killed == 0
    instance = manager.instances["strategy-3-5"]
    assert instance.status == BotStatus.STOPPED
    assert "pid" not in instance.process_info
    assert "stopped_at" in instance.process_info
    assert "strategy-3-5" not in manager.processes
    assert "strategy-3-5" not in manager.log_handles
    assert jobs.completed == [
        (jobs.created[0]["job_id"], {"status": "stopped", "force": False})
    ]


def test_stop_instance_force_kills_attached_process(tmp_path, monkeypatch):
    manager, process = _manager_with_running_process(tmp_path)
    monkeypatch.setattr(
        bot_instance_manager_module, "async_job_manager", _FakeJobManager()
    )

    result = asyncio.run(manager.stop_instance("strategy-3-5", force=True))

    assert result.success is True
    assert process.terminated == 0
    assert process.killed == 1


def test_stop_instance_graceful_timeout_escalates_to_kill(tmp_path, monkeypatch):
    manager, process = _manager_with_running_process(
        tmp_path,
        wait_error=subprocess.TimeoutExpired(cmd="bot", timeout=30),
    )
    monkeypatch.setattr(
        bot_instance_manager_module, "async_job_manager", _FakeJobManager()
    )

    result = asyncio.run(manager.stop_instance("strategy-3-5"))

    assert result.success is True
    assert process.terminated == 1
    assert process.killed == 1
    assert process.wait_timeouts == [30, 10]
    assert manager.instances["strategy-3-5"].status == BotStatus.STOPPED


def test_stop_instance_force_timeout_does_not_reap(tmp_path, monkeypatch):
    manager, process = _manager_with_running_process(
        tmp_path,
        wait_error=subprocess.TimeoutExpired(cmd="bot", timeout=10),
    )
    monkeypatch.setattr(
        bot_instance_manager_module, "async_job_manager", _FakeJobManager()
    )

    result = asyncio.run(manager.stop_instance("strategy-3-5", force=True))

    assert result.success is True
    assert process.killed == 1
    assert process.wait_timeouts == [10]


def test_stop_instance_attached_process_already_exited(tmp_path, monkeypatch):
    manager, process = _manager_with_running_process(tmp_path, exit_code=0)
    monkeypatch.setattr(
        bot_instance_manager_module, "async_job_manager", _FakeJobManager()
    )

    result = asyncio.run(manager.stop_instance("strategy-3-5"))

    assert result.success is True
    assert process.terminated == 0
    assert process.killed == 0
    assert manager.instances["strategy-3-5"].status == BotStatus.STOPPED


def _fake_external_for(instance_id, pid, **kwargs):
    """Build a psutil fake whose cmdline passes the manager identity check."""
    return _FakeExternalProcess(
        pid=pid,
        cmdline=["python", "-m", "src.main_instance", "--instance-id", instance_id],
        **kwargs,
    )


def _manager_with_external_runtime(tmp_path, external, instance_id="ext-bot-3"):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config(instance_id)))
    instance = manager.instances[instance_id]
    instance.status = BotStatus.RUNNING
    instance.process_info = {
        "pid": external.pid,
        "started_at": datetime.now(timezone.utc),
    }
    return manager


def test_stop_instance_external_runtime_graceful_and_force(tmp_path, monkeypatch):
    external = _fake_external_for("ext-bot-3", 7100)
    manager = _manager_with_external_runtime(tmp_path, external)
    monkeypatch.setattr(psutil, "Process", lambda pid: external)
    monkeypatch.setattr(
        bot_instance_manager_module, "async_job_manager", _FakeJobManager()
    )

    result = asyncio.run(manager.stop_instance("ext-bot-3"))

    assert result.success is True
    assert external.terminated == 1
    assert external.killed == 0
    assert manager.instances["ext-bot-3"].status == BotStatus.STOPPED

    force_external = _fake_external_for("ext-bot-4", 7101)
    force_manager = _manager_with_external_runtime(
        tmp_path / "force", force_external, instance_id="ext-bot-4"
    )
    monkeypatch.setattr(psutil, "Process", lambda pid: force_external)

    force_result = asyncio.run(force_manager.stop_instance("ext-bot-4", force=True))

    assert force_result.success is True
    assert force_external.killed == 1
    assert force_external.terminated == 0


def test_stop_instance_external_runtime_timeout_escalates(tmp_path, monkeypatch):
    external = _fake_external_for(
        "ext-bot-3", 7102, wait_error=psutil.TimeoutExpired(30)
    )
    manager = _manager_with_external_runtime(tmp_path, external)
    monkeypatch.setattr(psutil, "Process", lambda pid: external)
    monkeypatch.setattr(
        bot_instance_manager_module, "async_job_manager", _FakeJobManager()
    )

    result = asyncio.run(manager.stop_instance("ext-bot-3"))

    assert result.success is True
    assert external.terminated == 1
    assert external.killed == 1
    assert manager.instances["ext-bot-3"].status == BotStatus.STOPPED


def test_stop_instance_external_runtime_exited_during_stop(tmp_path, monkeypatch):
    external = _fake_external_for(
        "ext-bot-3", 7103, terminate_error=psutil.NoSuchProcess(pid=7103)
    )
    manager = _manager_with_external_runtime(tmp_path, external)
    monkeypatch.setattr(psutil, "Process", lambda pid: external)
    monkeypatch.setattr(
        bot_instance_manager_module, "async_job_manager", _FakeJobManager()
    )

    result = asyncio.run(manager.stop_instance("ext-bot-3"))

    assert result.success is True
    assert manager.instances["ext-bot-3"].status == BotStatus.STOPPED


def test_stop_instance_without_any_process_still_stops(tmp_path, monkeypatch):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("bot-np-1")))
    manager.instances["bot-np-1"].status = BotStatus.STARTING
    monkeypatch.setattr(
        bot_instance_manager_module, "async_job_manager", _FakeJobManager()
    )

    result = asyncio.run(manager.stop_instance("bot-np-1"))

    assert result.success is True
    assert manager.instances["bot-np-1"].status == BotStatus.STOPPED


def test_stop_instance_failure_marks_error(tmp_path, monkeypatch):
    manager, _process = _manager_with_running_process(tmp_path)
    jobs = _FakeJobManager(fail_on={"mark_completed"})
    monkeypatch.setattr(bot_instance_manager_module, "async_job_manager", jobs)

    result = asyncio.run(manager.stop_instance("strategy-3-5"))

    assert result.success is False
    assert "Error stopping instance" in result.message
    assert manager.instances["strategy-3-5"].status == BotStatus.ERROR
    assert jobs.failed and "mark completed failed" in jobs.failed[0][1]


# --- lifecycle: delete / status / list ---------------------------------------


def test_delete_instance_force_stops_and_removes_files(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_STARTUP_GRACE_SECONDS", "0")
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("bot-del-1")))
    manager.instances["bot-del-1"].status = BotStatus.RUNNING
    process = _FakeSubprocess(pid=9101)
    manager.processes["bot-del-1"] = process
    state_files = manager._get_instance_state_files("bot-del-1")
    for file_path in state_files.values():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("stale")
    monkeypatch.setattr(
        bot_instance_manager_module, "async_job_manager", _FakeJobManager()
    )

    result = asyncio.run(manager.delete_instance("bot-del-1"))

    assert result.success is True
    assert process.killed == 1
    assert "bot-del-1" not in manager.instances
    assert "bot-del-1" not in manager.processes
    assert "bot-del-1" not in manager.instance_locks
    assert not any(path.exists() for path in state_files.values())


def test_delete_instance_cleanup_failure_returns_error(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("bot-del-2")))
    # A directory where a state file is expected makes unlink() raise.
    (tmp_path / "bot_agents_bot-del-2.json").mkdir()
    (tmp_path / "cointegrated_pairs_bot-del-2.json").write_text("x")
    (tmp_path / "bot_bot-del-2.log").write_text("x")

    result = asyncio.run(manager.delete_instance("bot-del-2"))

    assert result.success is False
    assert "Error deleting instance" in result.message


def test_get_instance_status_marks_attached_dead_process(tmp_path):
    manager, _process = _manager_with_running_process(tmp_path, exit_code=9)
    published = []

    async def _publisher(payload):
        published.append(payload)

    manager.set_status_event_publisher(_publisher)

    status = asyncio.run(manager.get_instance_status("strategy-3-5"))

    assert status is not None
    assert status.status == BotStatus.ERROR
    assert manager.instances["strategy-3-5"].process_info["exit_code"] == 9
    assert published and published[-1]["event"] == "error"
    assert "exit_code=9" in published[-1]["last_error"]


def test_get_instance_status_attached_alive_collects_metrics(tmp_path, monkeypatch):
    manager, process = _manager_with_running_process(tmp_path, pid=9201)
    external = _fake_external_for("strategy-3-5", 9201)
    monkeypatch.setattr(psutil, "Process", lambda pid: external)

    status = asyncio.run(manager.get_instance_status("strategy-3-5"))

    assert status.status == BotStatus.RUNNING
    assert status.process_id == 9201
    instance = manager.instances["strategy-3-5"]
    assert instance.process_info["cpu_usage"] == 7.5
    assert instance.process_info["memory_usage_mb"] == 64.0
    assert instance.last_heartbeat is not None

    denied = _fake_external_for("strategy-3-5", 9201, metrics_access_denied=True)
    monkeypatch.setattr(psutil, "Process", lambda pid: denied)
    status = asyncio.run(manager.get_instance_status("strategy-3-5"))
    assert status.status == BotStatus.RUNNING

    def _gone(pid):
        raise psutil.NoSuchProcess(pid=pid)

    monkeypatch.setattr(psutil, "Process", _gone)
    status = asyncio.run(manager.get_instance_status("strategy-3-5"))
    assert status.status == BotStatus.ERROR
    assert "disappeared" in manager.instances["strategy-3-5"].process_info["last_error"]


def test_get_instance_status_external_runtime_probes(tmp_path, monkeypatch):
    external = _fake_external_for("ext-bot-3", 7300)
    manager = _manager_with_external_runtime(tmp_path, external)
    monkeypatch.setattr(psutil, "Process", lambda pid: external)

    status = asyncio.run(manager.get_instance_status("ext-bot-3"))
    assert status.status == BotStatus.RUNNING
    assert manager.instances["ext-bot-3"].process_info["pid"] == 7300
    assert manager.instances["ext-bot-3"].last_heartbeat is not None

    denied = _fake_external_for("ext-bot-4", 7301, metrics_access_denied=True)
    manager2 = _manager_with_external_runtime(tmp_path / "m2", denied, "ext-bot-4")
    monkeypatch.setattr(psutil, "Process", lambda pid: denied)
    status2 = asyncio.run(manager2.get_instance_status("ext-bot-4"))
    assert status2.status == BotStatus.RUNNING

    gone = _fake_external_for("ext-bot-5", 7302, metrics_gone=True)
    manager3 = _manager_with_external_runtime(tmp_path / "m3", gone, "ext-bot-5")
    monkeypatch.setattr(psutil, "Process", lambda pid: gone)
    status3 = asyncio.run(manager3.get_instance_status("ext-bot-5"))
    assert status3.status == BotStatus.ERROR
    assert "no longer running" in manager3.instances["ext-bot-5"].process_info.get(
        "last_error", ""
    )

    unattached = BotInstanceManager(state_dir=str(tmp_path / "m4"))
    asyncio.run(unattached.create_instance(_strategy_config("ext-bot-6")))
    unattached.instances["ext-bot-6"].status = BotStatus.RUNNING
    status4 = asyncio.run(unattached.get_instance_status("ext-bot-6"))
    assert status4.status == BotStatus.ERROR
    assert "not attached" in unattached.instances["ext-bot-6"].process_info.get(
        "last_error", ""
    )


def test_get_instance_status_missing_instance_returns_none(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    assert asyncio.run(manager.get_instance_status("ghost")) is None


def test_list_instances_returns_api_statuses(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("bot-l-1")))
    asyncio.run(manager.create_instance(_strategy_config("bot-l-2")))

    statuses = asyncio.run(manager.list_instances())

    assert {status.instance_id for status in statuses} == {"bot-l-1", "bot-l-2"}
    assert all(status.status == BotStatus.STOPPED for status in statuses)


# --- auto-recovery / liveness monitoring ------------------------------------


def test_auto_recover_verified_running_and_locked_skip(tmp_path):
    manager, _process = _manager_with_running_process(tmp_path)

    report = asyncio.run(manager.auto_recover_live_runtimes())

    assert report["checked"] == 1
    assert report["verified_running"] == ["strategy-3-5"]
    assert report["marked_error"] == []
    assert manager.instances["strategy-3-5"].status == BotStatus.RUNNING
    assert manager.instances["strategy-3-5"].last_heartbeat is not None

    async def _locked_scenario():
        # Drop the worker reference so the pre-lock liveness probe fails and
        # the reconciliation reaches the lock check while we hold it.
        manager.processes.pop("strategy-3-5", None)
        manager.instances["strategy-3-5"].process_info.pop("pid", None)
        lock = manager._get_instance_lock("strategy-3-5")
        async with lock:
            return await manager.auto_recover_live_runtimes()

    locked_report = asyncio.run(_locked_scenario())
    assert locked_report["skipped"] == [
        {"instance_id": "strategy-3-5", "reason": "lifecycle operation in progress"}
    ]


def test_auto_recover_second_probe_under_lock_verifies(tmp_path, monkeypatch):
    manager, _process = _manager_with_running_process(tmp_path)
    calls = {"count": 0}

    def _flaky_refresh(instance_id):
        calls["count"] += 1
        return calls["count"] >= 2

    manager._refresh_instance_liveness_from_process = _flaky_refresh

    report = asyncio.run(manager.auto_recover_live_runtimes())

    assert calls["count"] == 2
    assert report["verified_running"] == ["strategy-3-5"]


def test_auto_recover_missing_worker_marked_error_when_disabled(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("strategy-4-1")))
    manager.instances["strategy-4-1"].status = BotStatus.RUNNING
    published = []

    async def _publisher(payload):
        published.append(payload)

    manager.set_status_event_publisher(_publisher)

    report = asyncio.run(manager.auto_recover_live_runtimes())

    assert report["marked_error"] == [
        {"instance_id": "strategy-4-1", "reason": "auto-restart disabled"}
    ]
    assert manager.instances["strategy-4-1"].status == BotStatus.ERROR
    assert (
        "auto-restart disabled"
        in manager.instances["strategy-4-1"].process_info["last_error"]
    )
    assert published and published[-1]["event"] == "error"


def test_auto_recover_restarts_missing_testnet_worker(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_STARTUP_GRACE_SECONDS", "0")
    monkeypatch.setenv("BOT_AUTO_RECOVER_LIVE_RUNTIMES", "true")
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("strategy-4-2")))
    manager.instances["strategy-4-2"].status = BotStatus.RUNNING
    jobs = _FakeJobManager()
    monkeypatch.setattr(bot_instance_manager_module, "async_job_manager", jobs)
    monkeypatch.setattr(
        bot_instance_manager_module.subprocess,
        "Popen",
        lambda *a, **k: _FakeSubprocess(pid=9301),
    )

    report = asyncio.run(manager.auto_recover_live_runtimes())

    assert report["restarted"] == ["strategy-4-2"]
    assert manager.instances["strategy-4-2"].status == BotStatus.RUNNING
    assert manager.instances["strategy-4-2"].process_info["pid"] == 9301
    assert manager.instances["strategy-4-2"].last_heartbeat is not None
    assert manager.recovery_diagnostics["live_auto_recovery"]["restarted"] == [
        "strategy-4-2"
    ]


def test_auto_recover_mainnet_requires_explicit_allowance(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_AUTO_RECOVER_LIVE_RUNTIMES", "true")
    monkeypatch.delenv("BOT_AUTO_RECOVER_LIVE_MAINNET", raising=False)
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_live_config("strategy-4-3", is_testnet=False)))
    manager.instances["strategy-4-3"].status = BotStatus.RUNNING

    report = asyncio.run(manager.auto_recover_live_runtimes())

    assert report["marked_error"] == [
        {
            "instance_id": "strategy-4-3",
            "reason": "auto-restart disabled for mainnet runtime",
        }
    ]
    assert manager.instances["strategy-4-3"].status == BotStatus.ERROR


def test_auto_recover_failed_restart_marks_error(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_AUTO_RECOVER_LIVE_RUNTIMES", "true")
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("strategy-4-4")))
    manager.instances["strategy-4-4"].status = BotStatus.RUNNING
    monkeypatch.setattr(
        bot_instance_manager_module, "async_job_manager", _FakeJobManager()
    )

    def _popen_boom(*args, **kwargs):
        raise OSError("spawn denied")

    monkeypatch.setattr(bot_instance_manager_module.subprocess, "Popen", _popen_boom)

    report = asyncio.run(manager.auto_recover_live_runtimes())

    assert report["restarted"] == []
    assert report["marked_error"][0]["instance_id"] == "strategy-4-4"
    assert "spawn denied" in report["marked_error"][0]["reason"]
    assert manager.instances["strategy-4-4"].status == BotStatus.ERROR


def test_check_liveness_and_degrade_transitions(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("strategy-6-30")))
    instance = manager.instances["strategy-6-30"]
    published = []

    async def _publisher(payload):
        published.append(payload)

    manager.set_status_event_publisher(_publisher)

    # No heartbeat yet: only a refresh attempt, no degradation.
    instance.status = BotStatus.RUNNING
    asyncio.run(manager._check_liveness_and_degrade())
    assert instance.status == BotStatus.RUNNING

    # Fresh heartbeat: unchanged.
    instance.last_heartbeat = datetime.now(timezone.utc)
    asyncio.run(manager._check_liveness_and_degrade())
    assert instance.status == BotStatus.RUNNING

    # Stale heartbeat with no live process: degraded + published.
    instance.last_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=120)
    asyncio.run(manager._check_liveness_and_degrade())
    assert instance.status == BotStatus.DEGRADED
    assert instance.recovery_state == "degraded"
    assert instance.recovery_reason.startswith("Heartbeat stale")
    assert published and published[-1]["event"] == "degraded"

    # Recovering instances are left alone.
    instance.status = BotStatus.RUNNING
    instance.recovery_state = "recovering"
    instance.last_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=120)
    asyncio.run(manager._check_liveness_and_degrade())
    assert instance.status == BotStatus.RUNNING
    assert instance.recovery_state == "recovering"


def test_shutdown_stops_active_instances_and_closes_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(
        bot_instance_manager_module, "async_job_manager", _FakeJobManager()
    )
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("bot-sd-1")))
    manager.instances["bot-sd-1"].status = BotStatus.RUNNING
    manager._open_instance_log("bot-sd-1")

    asyncio.run(manager.shutdown(stop_active=True))

    assert manager.instances["bot-sd-1"].status == BotStatus.STOPPED
    assert manager.log_handles == {}


# --- strategy status payloads / misc helpers ---------------------------------


def test_strategy_id_and_job_metadata_helpers(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    assert manager._strategy_id_from_instance_id("strategy-3-17") == 17
    assert manager._strategy_id_from_instance_id("strategy-3") is None
    assert manager._strategy_id_from_instance_id("strategy-a-b") is None
    assert manager._strategy_id_from_instance_id("bot-1") is None

    assert manager._job_metadata("ghost") == {"bot_instance_id": "ghost"}

    asyncio.run(manager.create_instance(_strategy_config("strategy-5-9")))
    metadata = manager._job_metadata("strategy-5-9")
    assert metadata == {
        "bot_instance_id": "strategy-5-9",
        "strategy_id": 9,
        "strategy": "cointegration",
        "runtime_mode": "live",
        "environment": "testnet",
        "subaccount": 0,
    }

    mainnet = _live_config("strategy-5-8", is_testnet=False)
    asyncio.run(manager.create_instance(mainnet))
    assert manager._job_metadata("strategy-5-8")["environment"] == "mainnet"


def test_strategy_status_payload_edge_cases(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    assert manager._build_strategy_status_payload("ghost") is None

    asyncio.run(manager.create_instance(_strategy_config("bot-plain-1")))
    assert manager._build_strategy_status_payload("bot-plain-1") is None

    asyncio.run(manager.create_instance(_strategy_config("strategy-5-10")))
    instance = manager.instances["strategy-5-10"]
    instance.status = BotStatus.DEGRADED
    instance.process_info = {"pid": 4141, "last_error": "lagging"}

    payload = manager._build_strategy_status_payload("strategy-5-10")
    assert payload["strategyId"] == 10
    assert payload["status"] == "degraded"
    assert payload["process_id"] == 4141
    assert payload["lastError"] == "lagging"
    assert payload["network"] == "testnet"
    assert payload["event"] == "status"

    # Raw string status (no enum) is stringified.
    instance.status = "running"
    payload = manager._build_strategy_status_payload("strategy-5-10")
    assert payload["status"] == "running"


def test_publish_strategy_status_survives_publisher_failure(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config("strategy-5-11")))

    async def _boom(payload):
        raise RuntimeError("websocket exploded")

    manager.set_status_event_publisher(_boom)
    asyncio.run(manager._publish_strategy_status("strategy-5-11", event="created"))
    # Heartbeat events mark liveness even without a publisher.
    asyncio.run(manager._publish_strategy_status("strategy-5-11", event="heartbeat"))
    assert manager.instances["strategy-5-11"].last_heartbeat is not None


def test_instance_log_handle_and_tail_readers(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))

    assert manager._read_recent_log_tail("bot-log-1") == ""

    log_path = manager._get_instance_state_files("bot-log-1")["log"]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("x" * 400 + "\n" + "y" * 200)

    tail = manager._read_recent_log_tail("bot-log-1", max_chars=100)
    assert tail == "y" * 100

    handle = manager._open_instance_log("bot-log-1")
    assert "bot-log-1" in manager.log_handles
    replacement = manager._open_instance_log("bot-log-1")
    assert handle.closed is True
    manager._close_instance_log("bot-log-1")
    assert replacement.closed is True
    manager._close_instance_log("bot-log-1")  # double close is a no-op

    class _BadHandle:
        def flush(self):
            raise OSError("flush failed")

        def close(self):
            raise OSError("close failed")

    manager.log_handles["bot-log-1"] = _BadHandle()
    manager._close_instance_log("bot-log-1")  # must not raise
    assert "bot-log-1" not in manager.log_handles

    # A directory where the log file belongs makes the tail read fail cleanly.
    (tmp_path / "bot_bot-log-2.log").mkdir()
    assert manager._read_recent_log_tail("bot-log-2") == ""


def test_start_instance_injects_per_instance_trading_params_env(tmp_path, monkeypatch):
    """Per-instance trading params must reach the worker as BOT_* env vars.

    Regression for audit F7: the live trading core reads BotSettings.from_env()
    at import time inside the worker; without this injection operators'
    per-instance usdPerTrade / maxPositions / stopLossPct / subaccountNumber
    were silently replaced by the global structured-config values.
    """
    monkeypatch.setenv("BOT_STARTUP_GRACE_SECONDS", "0")
    manager = BotInstanceManager(state_dir=str(tmp_path))
    config = _strategy_config("strategy-params-1")
    config.trading_params.subaccount_number = 2
    config.trading_params.usd_per_trade = 42.5
    config.trading_params.max_positions = 7
    config.trading_params.stop_loss_pct = 3.25
    config.trading_params.take_profit_pct = 9.5
    config.trading_params.stats_window = 33
    config.trading_params.zscore_threshold = 2.1
    config.trading_params.position_timeout_hours = 48
    config.trading_params.close_at_zscore_cross = False
    config.trading_params.selected_markets = ["BTC-USD", "ETH-USD"]
    asyncio.run(manager.create_instance(config))

    monkeypatch.setattr(
        bot_instance_manager_module, "async_job_manager", _FakeJobManager()
    )
    process = _FakeSubprocess(pid=999)
    popen_kwargs = {}

    def _fake_popen(*args, **kwargs):
        popen_kwargs.update(kwargs)
        return process

    monkeypatch.setattr(bot_instance_manager_module.subprocess, "Popen", _fake_popen)

    result = asyncio.run(manager.start_instance("strategy-params-1"))

    assert result.success is True
    env = popen_kwargs["env"]
    assert env["BOT_SUBACCOUNT_NUMBER"] == "2"
    assert env["BOT_USD_PER_TRADE"] == "42.5"
    assert env["BOT_MAX_POSITIONS"] == "7"
    assert env["BOT_STOP_LOSS_PCT"] == "3.25"
    assert env["BOT_TAKE_PROFIT_PCT"] == "9.5"
    assert env["BOT_STATS_WINDOW"] == "33"
    assert env["BOT_ZSCORE_THRESHOLD"] == "2.1"
    assert env["BOT_POSITION_TIMEOUT_HOURS"] == "48"
    assert env["BOT_CLOSE_AT_ZSCORE_CROSS"] == "false"
    assert env["BOT_SELECTED_MARKETS"] == "BTC-USD,ETH-USD"
    assert env["BOT_MANAGE_EXITS"] == "false"
    assert env["BOT_PLACE_TRADES"] == "false"
    # Network selection stays with the credentials path: the injection map
    # itself must never carry IS_TESTNET (inherited parent values are a
    # separate, pre-existing concern).
    assert "IS_TESTNET" not in bot_instance_manager_module.trading_params_env(
        config.trading_params
    )


def test_trading_params_env_round_trips_through_bot_settings_from_env(
    tmp_path, monkeypatch
):
    """The injected env must parse back into BotSettings unchanged."""
    from config.config import BotSettings

    config = _strategy_config("strategy-params-2")
    config.trading_params.usd_per_trade = 17.25
    config.trading_params.max_positions = 4
    config.trading_params.subaccount_number = 1
    config.trading_params.stop_loss_pct = 1.5
    config.trading_params.stats_window = 26
    config.trading_params.zscore_threshold = 1.75
    config.trading_params.selected_markets = ["SOL-USD"]

    for key, value in bot_instance_manager_module.trading_params_env(
        config.trading_params
    ).items():
        monkeypatch.setenv(key, value)

    parsed = BotSettings.from_env()

    assert parsed.usdPerTrade == pytest.approx(17.25)
    assert parsed.maxPositions == 4
    assert parsed.subaccountNumber == 1
    assert parsed.stopLossPct == pytest.approx(1.5)
    assert parsed.statsWindow == 26
    assert parsed.ZScoreThreshold == pytest.approx(1.75)
    assert parsed.selectedMarkets == ["SOL-USD"]
    assert parsed.closeAtZscoreCross == config.trading_params.close_at_zscore_cross


# --- API status view must never carry credentials ---------------------------


def test_api_status_view_never_exposes_mnemonic_or_telegram_token():
    config = _strategy_config("strategy-9-1")
    secret_mnemonic = "unit-test-mnemonic-value-not-a-real-seed"
    secret_token = "unit-test-telegram-token"
    config = config.model_copy(
        update={
            "credentials": config.credentials.model_copy(
                update={"mnemonic": secret_mnemonic}
            ),
            "telegram": TelegramConfig(token=secret_token, chat_id="42"),
        }
    )
    state = BotInstanceState(
        instance_id="strategy-9-1",
        config=config,
        status=BotStatus.STOPPED,
        process_info={},
        trading_stats={},
        created_at=datetime.now(timezone.utc),
        last_update=datetime.now(timezone.utc),
    )

    payload = state.to_api_status().model_dump(mode="json")
    serialized = json.dumps(payload)

    assert secret_mnemonic not in serialized
    assert secret_token not in serialized
    assert "mnemonic" not in payload["config"]["credentials"]
    assert "token" not in payload["config"]["telegram"]
    assert payload["config"]["credentials"]["mnemonic_configured"] is True
    assert payload["config"]["telegram"]["token_configured"] is True
    assert payload["config"]["telegram"]["chat_id"] == "42"
    assert payload["config"]["credentials"]["address"]
    # The internal config object is untouched: the runtime still has its key.
    assert state.config.credentials.mnemonic == secret_mnemonic
