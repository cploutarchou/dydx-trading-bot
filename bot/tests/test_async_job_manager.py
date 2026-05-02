import asyncio

import src.infrastructure.use_cases.async_job_manager as job_manager_module
from internal.domain import Base
from internal.domain.models import Job, JobStatusEnum
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.infrastructure.use_cases.async_job_manager import AsyncJobManager


def _session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def test_supervised_task_failure_is_persisted(monkeypatch):
    SessionLocal = _session_factory()
    manager = AsyncJobManager()
    monkeypatch.setenv("BOT_DATABASE_URL", "sqlite://")

    monkeypatch.setattr(
        job_manager_module.db,
        "get_session",
        lambda: SessionLocal(),
    )

    async def _boom():
        raise RuntimeError("async failure")

    async def _run():
        task = manager.create_supervised_task(
            _boom(),
            job_type="backtest",
            job_id="job-failure",
            auto_complete=True,
        )
        await task

    try:
        asyncio.run(_run())
    except RuntimeError:
        pass

    session = SessionLocal()
    try:
        job = session.query(Job).filter(Job.job_id == "job-failure").one()
        assert job.status == JobStatusEnum.FAILED
        assert job.error_message == "async failure"
        assert "RuntimeError" in job.error_traceback
    finally:
        session.close()


def test_supervised_task_cancellation_is_persisted(monkeypatch):
    SessionLocal = _session_factory()
    manager = AsyncJobManager()
    monkeypatch.setenv("BOT_DATABASE_URL", "sqlite://")

    monkeypatch.setattr(
        job_manager_module.db,
        "get_session",
        lambda: SessionLocal(),
    )

    async def _long_running():
        await asyncio.sleep(10)

    async def _run():
        task = manager.create_supervised_task(
            _long_running(),
            job_type="strategy_worker",
            job_id="job-cancelled",
            auto_complete=True,
        )
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(_run())

    session = SessionLocal()
    try:
        job = session.query(Job).filter(Job.job_id == "job-cancelled").one()
        assert job.status == JobStatusEnum.CANCELLED
        assert job.cancellation_reason == "async task cancelled"
    finally:
        session.close()


def test_mark_progress_is_throttled(monkeypatch):
    manager = AsyncJobManager()

    # Make the throttling behavior deterministic for this test.
    manager._progress_min_interval_seconds = 60.0
    manager._progress_min_delta_pct = 20.0

    calls: list[object] = []

    def _capture_call(operation):
        calls.append(operation)
        return None

    monkeypatch.setattr(manager, "_with_uow", _capture_call)

    manager.mark_progress("job-throttle", 10.0)
    manager.mark_progress("job-throttle", 10.5)
    manager.mark_progress("job-throttle", 11.0)

    # First update persists, tiny deltas in the throttle window are skipped.
    assert len(calls) == 1

    # Terminal progress must always persist even inside the interval.
    manager.mark_progress("job-throttle", 100.0)
    assert len(calls) == 2

    metrics = manager.get_runtime_metrics()
    assert metrics["progress_updates_persisted"] == 2
    assert metrics["progress_updates_skipped"] == 2


def test_mark_failed_uses_fallback_message_for_empty_error(monkeypatch):
    manager = AsyncJobManager()

    captured: dict[str, str] = {}

    class _Jobs:
        @staticmethod
        def fail_job(job_id: str, error_message: str, error_traceback=None):
            captured["job_id"] = job_id
            captured["error_message"] = error_message

    class _UoW:
        jobs = _Jobs()

    def _execute_with_fake_uow(operation):
        return operation(_UoW())

    monkeypatch.setattr(manager, "_with_uow", _execute_with_fake_uow)

    manager.mark_failed("job-empty-error", RuntimeError(""))

    assert captured["job_id"] == "job-empty-error"
    assert captured["error_message"] == "RuntimeError"


def test_persistence_pool_overload_metrics_increment(monkeypatch):
    manager = AsyncJobManager()
    manager._pool_overload_threshold = 1
    manager._pool_overload_window_seconds = 60.0

    class _SessionFactoryRaises:
        def __call__(self):
            raise RuntimeError(
                "QueuePool limit of size 5 overflow 5 reached, connection timed out, "
                "timeout 5.00 (Background on this error at: https://sqlalche.me/e/20/3o7r)"
            )

    monkeypatch.setenv("BOT_DATABASE_URL", "sqlite://")
    monkeypatch.setattr(job_manager_module.db, "get_session", _SessionFactoryRaises())

    manager._with_uow(lambda _uow: None)

    metrics = manager.get_runtime_metrics()
    assert metrics["persistence_pool_overload_events_recent"] >= 1
    assert metrics["persistence_pool_overloaded"] is True
