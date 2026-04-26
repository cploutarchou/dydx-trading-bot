import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.infrastructure.use_cases.async_job_manager as job_manager_module
from internal.domain import Base
from internal.domain.models import Job, JobStatusEnum
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
