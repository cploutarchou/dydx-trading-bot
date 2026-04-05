import asyncio

from src.bot_instance_manager import BotInstanceManager
from src.infrastructure.domain.bot_api_models import (
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
