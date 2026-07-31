import asyncio
import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, cast

import pytest

import src.bot_instance_manager as bot_instance_manager_module
from src.bot_instance_manager import BotInstanceManager
from src.shared import credentials_cipher as cc
from src.infrastructure.domain.bot_api_models import (
    BacktestingParameters,
    BotCredentials,
    BotInstanceConfig,
    BotInstanceState,
    BotStatus,
    TradingParameters,
)


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

    async def fake_stop_instance(instance_id, force=False):
        stopped["instance_id"] = instance_id
        stopped["force"] = force
        manager.instances[instance_id].status = BotStatus.STOPPED
        return SimpleNamespace(success=True)

    monkeypatch.setattr(manager, "stop_instance", fake_stop_instance)

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
