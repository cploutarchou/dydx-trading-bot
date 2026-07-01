"""Tests for the Celery worker metrics producer (Phase 1)."""

from __future__ import annotations

import unittest


class FakeWriter:
    """Captures record_task_metrics calls."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def record_task_metrics(self, **kwargs) -> None:  # noqa: ANN003
        self.calls.append(kwargs)


class TestRecordCeleryTaskMetric(unittest.TestCase):
    def setUp(self) -> None:
        from src.infrastructure.workers import celery_metrics

        self.module = celery_metrics
        # Pin a deterministic worker id so assertions are stable.
        self.module._worker_id = lambda: "test-host-123"

    def test_success_state_marks_success_true(self) -> None:
        writer = FakeWriter()
        self.module.record_celery_task_metric(
            task_id="t1",
            task_name="backtests.run",
            state="SUCCESS",
            duration_ms=1234.0,
            retries=0,
            queue_name="backtests",
            writer=writer,
        )
        self.assertEqual(len(writer.calls), 1)
        call = writer.calls[0]
        self.assertTrue(call["success"])
        self.assertEqual(call["task_name"], "backtests.run")
        self.assertEqual(call["duration_ms"], 1234.0)
        self.assertEqual(call["worker_type"], "celery")
        self.assertEqual(call["queue_name"], "backtests")
        self.assertEqual(call["worker_id"], "test-host-123")

    def test_failure_state_marks_success_false(self) -> None:
        writer = FakeWriter()
        self.module.record_celery_task_metric(
            task_id="t2",
            task_name="backtests.run",
            state="FAILURE",
            duration_ms=50.0,
            retries=2,
            queue_name="backtests",
            writer=writer,
        )
        self.assertFalse(writer.calls[0]["success"])
        self.assertEqual(writer.calls[0]["retry_count"], 2)

    def test_retry_state_is_not_success(self) -> None:
        writer = FakeWriter()
        self.module.record_celery_task_metric(
            task_id="t3",
            task_name="backtests.run",
            state="RETRY",
            duration_ms=10.0,
            retries=1,
            queue_name="backtests",
            writer=writer,
        )
        self.assertFalse(writer.calls[0]["success"])

    def test_empty_queue_falls_back_to_celery(self) -> None:
        writer = FakeWriter()
        self.module.record_celery_task_metric(
            task_id="t4",
            task_name="bot.sync_market_candles",
            state="SUCCESS",
            duration_ms=5.0,
            retries=0,
            queue_name="",
            writer=writer,
        )
        self.assertEqual(writer.calls[0]["queue_name"], "celery")

    def test_none_writer_is_noop(self) -> None:
        # Must not raise.
        self.module.record_celery_task_metric(
            task_id="t5",
            task_name="backtests.run",
            state="SUCCESS",
            duration_ms=1.0,
            retries=0,
            queue_name="backtests",
            writer=None,
        )

    def test_negative_duration_clamped_to_zero(self) -> None:
        writer = FakeWriter()
        self.module.record_celery_task_metric(
            task_id="t6",
            task_name="backtests.run",
            state="SUCCESS",
            duration_ms=-5.0,
            retries=0,
            queue_name="backtests",
            writer=writer,
        )
        self.assertEqual(writer.calls[0]["duration_ms"], 0.0)


class TestPrerunPostrunTiming(unittest.TestCase):
    """The prerun/postrun pair must measure duration end-to-end without raising."""

    def test_postrun_records_after_prerun(self) -> None:
        from src.infrastructure.workers import celery_metrics

        writer = FakeWriter()
        celery_metrics._worker_id = lambda: "test-host-456"

        # Force _resolve_writer to return our fake so the signal path is exercised.
        celery_metrics._resolve_writer = lambda: writer  # type: ignore[assignment]

        class FakeTask:
            name = "backtests.run"

            class request:  # noqa: N801
                retries = 0
                delivery_info = {"routing_key": "backtests"}

        celery_metrics._on_task_prerun(task_id="tid-1")
        celery_metrics._on_task_postrun(task_id="tid-1", task=FakeTask, state="SUCCESS")

        self.assertEqual(len(writer.calls), 1)
        self.assertTrue(writer.calls[0]["success"])
        self.assertGreaterEqual(writer.calls[0]["duration_ms"], 0.0)
        # Start time consumed.
        self.assertNotIn("tid-1", celery_metrics._task_start_times)

    def test_postrun_never_raises_on_writer_failure(self) -> None:
        from src.infrastructure.workers import celery_metrics

        def boom() -> None:
            raise RuntimeError("boom")

        celery_metrics._resolve_writer = boom  # type: ignore[assignment]

        class FakeTask:
            name = "backtests.run"

            class request:  # noqa: N801
                retries = 0
                delivery_info = {}

        # Must not raise even though writer resolution blows up.
        celery_metrics._on_task_postrun(task_id="tid-2", task=FakeTask, state="SUCCESS")


if __name__ == "__main__":
    unittest.main()
