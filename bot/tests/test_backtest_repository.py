from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from internal.domain import Base
from src.infrastructure.persistence.repository_backtest import BacktestRepository


class _MariaDbRecordChanged:
    args = (1020, "Record has changed since last read in table 'backtest_runtime_runs'")

    def __str__(self) -> str:
        return self.args[1]


def test_save_run_rolls_back_and_retries_mariadb_record_changed(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'runs.sqlite'}", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    real_commit = session.commit
    calls = {"commit": 0}

    def flaky_commit():
        calls["commit"] += 1
        if calls["commit"] == 1:
            raise OperationalError("UPDATE backtest_runtime_runs", {}, _MariaDbRecordChanged())
        return real_commit()

    monkeypatch.setattr(session, "commit", flaky_commit)
    repository = BacktestRepository(session)

    persisted = repository.save_run(
        {
            "run_id": "run-retry-1020",
            "name": "retry",
            "status": "running",
            "progress_pct": 12.5,
            "current_pair": "BTC-USD/ETH-USD",
            "current_task": "processing pair",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "request": {"pairs": ["BTC-USD", "ETH-USD"]},
        }
    )

    assert persisted["run_id"] == "run-retry-1020"
    assert persisted["status"] == "running"
    assert calls["commit"] == 2
    assert repository.get_run("run-retry-1020")["current_task"] == "processing pair"

    session.close()
