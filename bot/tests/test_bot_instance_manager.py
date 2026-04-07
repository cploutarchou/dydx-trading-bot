import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import yaml

import src.bot_instance_manager as bot_instance_manager_module
from src.bot_instance_manager import BotInstanceManager
from src.infrastructure.domain.bot_api_models import (
    BacktestingParameters,
    BotCredentials,
    BotInstanceConfig,
    BotStatus,
    TradingParameters,
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
            max_drawdown_pct=8.0,
            stop_loss_pct=1.2,
            take_profit_pct=4.5,
            trailing_stop_pct=0.8,
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


def test_start_instance_marks_fast_exit_as_error_and_publishes_status(tmp_path, monkeypatch):
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

    monkeypatch.setattr("src.bot_instance_manager.subprocess.Popen", lambda *args, **kwargs: FakeProcess())
    monkeypatch.setattr(manager, "_read_recent_log_tail", lambda instance_id, max_chars=500: "bot failed immediately")

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
    assert kwargs["cwd"] == bot_root
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

    manager.processes["strategy-1-101"] = DeadProcess()

    asyncio.run(manager.cleanup_dead_processes())

    assert manager.instances["strategy-1-101"].status == BotStatus.ERROR
    assert published[-1]["strategyId"] == 101
    assert published[-1]["status"] == "error"


def test_create_instance_persists_runtime_and_backtest_parameters_to_yaml(tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))

    result = asyncio.run(manager.create_instance(_strategy_config()))

    assert result.success is True

    config_path = tmp_path / "config_strategy-1-101.yaml"
    contents = config_path.read_text(encoding="utf-8")

    assert "strategy: cointegration" in contents
    assert "maxPositions: 3" in contents
    assert "startingBalance: 5000.0" in contents
    assert "benchmarkSymbol: ETH-USD" in contents


def test_instance_config_uses_structured_defaults_instead_of_legacy_env(monkeypatch, tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    config = _strategy_config()
    config.telegram = None
    config.backtesting_params = None

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "legacy-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "legacy-chat")
    monkeypatch.setenv("BACKTEST_BENCHMARK_SYMBOL", "LEGACY-USD")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    monkeypatch.setattr(
        bot_instance_manager_module,
        "load_app_config",
        lambda: SimpleNamespace(
            environment="development",
            telegram=SimpleNamespace(token="run-token", chat_id="run-chat"),
            backtesting=SimpleNamespace(
                candleResolution="4HOUR",
                maxHistoryDays=180,
                startingBalance=2500.0,
                transactionFee=0.0009,
                slippage=0.0025,
                benchmarkSymbol="SOL-USD",
                riskFreeRate=0.04,
            ),
            logging=SimpleNamespace(
                level="WARNING",
                loki=SimpleNamespace(
                    enabled=True,
                    url="http://loki.example",
                    username="loki-user",
                    password="loki-pass",
                    labels={"source": "run-json"},
                ),
            ),
        ),
    )

    config_path = manager._create_instance_config_file("strategy-1-101", config)
    parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert parsed["telegram"]["token"] == "run-token"
    assert parsed["telegram"]["chat_id"] == "run-chat"
    assert parsed["backtesting"]["benchmarkSymbol"] == "SOL-USD"
    assert parsed["backtesting"]["startingBalance"] == 2500.0
    assert parsed["logging"]["level"] == "WARNING"
    assert parsed["logging"]["loki"]["labels"]["source"] == "run-json"
    assert parsed["logging"]["loki"]["labels"]["instance"] == "strategy-1-101"


def test_manager_recovers_instances_from_database_before_legacy_disk(monkeypatch, tmp_path):
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
            "trading_params": _strategy_config().trading_params.model_dump(),
            "backtesting_params": _strategy_config().backtesting_params.model_dump(),
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

    monkeypatch.setattr(bot_instance_manager_module.db, "get_session", lambda: FakeSession())
    monkeypatch.setattr(bot_instance_manager_module, "UnitOfWork", FakeUOW)

    manager = BotInstanceManager(state_dir=str(tmp_path))

    assert set(manager.instances.keys()) == {"strategy-1-101"}
    recovered = manager.instances["strategy-1-101"]
    assert recovered.status == BotStatus.RUNNING
    assert recovered.process_info["pid"] == 4321
    assert recovered.config.instance_name == "Recovered Strategy"
    assert recovered.config.telegram.token == "persisted-token"


def test_save_instances_state_syncs_runtime_state_to_database(monkeypatch, tmp_path):
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
    assert persisted_record.config["runtime_state"]["status"] == "stopped"
    assert persisted_record.config["runtime_state"]["last_error"] == "runtime crashed"
    assert persisted_record.config["runtime_state"]["exit_code"] == 7
    assert persisted_record.config["runtime_state"]["trading_stats"]["active_positions"] == 2
    assert (tmp_path / "instances.json").exists()


def test_save_instances_state_coerces_string_config_payload(monkeypatch, tmp_path):
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
    assert persisted_record.config["runtime_state"]["status"] == "stopped"


def test_mark_instance_error_records_runtime_event(monkeypatch, tmp_path):
    manager = BotInstanceManager(state_dir=str(tmp_path))
    asyncio.run(manager.create_instance(_strategy_config()))

    recorded = {}

    def _fake_record_runtime_event(instance_id, event_type, severity, message, details=None):
        recorded["instance_id"] = instance_id
        recorded["event_type"] = event_type
        recorded["severity"] = severity
        recorded["message"] = message
        recorded["details"] = details

    monkeypatch.setattr(manager, "_record_runtime_event", _fake_record_runtime_event)

    changed = manager._mark_instance_error("strategy-1-101", "startup failed", exit_code=9)

    assert changed is True
    assert recorded["instance_id"] == "strategy-1-101"
    assert recorded["event_type"] == "bot_runtime_error"
    assert recorded["severity"] == "error"
    assert recorded["message"] == "startup failed"
    assert recorded["details"] == {"exit_code": 9}


def test_recovered_running_instance_is_marked_error_when_pid_is_dead(monkeypatch, tmp_path):
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

    monkeypatch.setattr(bot_instance_manager_module.db, "get_session", lambda: FakeSession())
    monkeypatch.setattr(bot_instance_manager_module, "UnitOfWork", FakeUOW)
    monkeypatch.setattr(
        bot_instance_manager_module.psutil,
        "Process",
        lambda pid: (_ for _ in ()).throw(bot_instance_manager_module.psutil.NoSuchProcess(pid)),
    )

    manager = BotInstanceManager(state_dir=str(tmp_path))
    manager.set_status_event_publisher(_publisher)

    status = asyncio.run(manager.get_instance_status("strategy-1-101"))

    assert status is not None
    assert status.status == BotStatus.ERROR
    assert manager.instances["strategy-1-101"].status == BotStatus.ERROR
    assert published[-1]["status"] == "error"
    assert "no longer running" in published[-1]["last_error"]
