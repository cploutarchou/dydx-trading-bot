"""Real-NATS integration tests for the durable backtest event emitter (Phase 2).

Runs only when NATS_TEST_URL points at a live NATS server. Proves the bot emits
canonical envelopes on backtest.event.<action> with a stable terminal Msg-Id,
and that the backend-shaped envelope decodes cleanly.

    NATS_TEST_URL=nats://localhost:4222 \
      .venv/bin/python -m pytest tests/test_backtest_event_emitter.py -v
"""

from __future__ import annotations

import asyncio
import json
import os
import unittest


def _nats_url() -> str:
    return os.getenv("NATS_TEST_URL", "nats://localhost:4222")


async def _fetch_last_event(subject: str = "backtest.event.>"):
    import nats  # type: ignore[import-untyped]

    nc = await nats.connect(servers=[_nats_url()], connect_timeout=5)
    try:
        js = nc.jetstream()
        info = await js.stream_info("BACKTEST_EVENTS")
        msg = await js.get_msg("BACKTEST_EVENTS", info.state.last_seq)
        return msg
    finally:
        await nc.drain()


@unittest.skipUnless(os.getenv("NATS_TEST_URL"), "NATS_TEST_URL not set")
class TestBacktestEventEmitter(unittest.TestCase):
    def setUp(self) -> None:
        # NATS code-level default is false (deployment configs enable it); the
        # emission tests need it on.
        import os as _os

        self._orig_nats = _os.environ.get("NATS_ENABLED")
        _os.environ["NATS_ENABLED"] = "true"

        async def _wipe() -> None:
            import nats  # type: ignore[import-untyped]

            nc = await nats.connect(servers=[_nats_url()], connect_timeout=5)
            try:
                js = nc.jetstream()
                try:
                    await js.delete_stream("BACKTEST_EVENTS")
                except Exception:
                    pass
            finally:
                await nc.drain()

        asyncio.run(_wipe())

    def tearDown(self) -> None:
        import os as _os

        if self._orig_nats is None:
            _os.environ.pop("NATS_ENABLED", None)
        else:
            _os.environ["NATS_ENABLED"] = self._orig_nats

    def test_emit_completed_publishes_canonical_envelope(self) -> None:
        from src.infrastructure.workers.backtest_event_emitter import emit_backtest_event_sync

        msg_id = emit_backtest_event_sync(
            run_id="run-emit-1", status="completed", progress=100.0
        )
        self.assertIsNotNone(msg_id)

        msg = asyncio.run(_fetch_last_event())
        self.assertEqual(msg.subject, "backtest.event.completed")
        self.assertEqual(msg.headers.get("Msg-Id"), msg_id)
        # Terminal events use a stable Msg-Id (dedup-safe on retry/redelivery).
        self.assertEqual(msg_id, "backtest:run-emit-1:completed")

        env = json.loads(msg.data.decode())
        self.assertEqual(env["subject"], "backtest.event.completed")
        self.assertEqual(env["owner_type"], "backtest")
        self.assertEqual(env["owner_id"], "run-emit-1")
        self.assertEqual(env["payload"]["event"], "completed")
        self.assertEqual(env["payload"]["run_id"], "run-emit-1")
        self.assertEqual(env["payload"]["progress"], 100.0)

    def test_emit_failed_requires_and_carries_error_code(self) -> None:
        from src.infrastructure.workers.backtest_event_emitter import emit_backtest_event_sync

        msg_id = emit_backtest_event_sync(
            run_id="run-emit-2",
            status="failed",
            error_code="BACKTEST_EXECUTION_FAILED",
            error_message="boom",
        )
        self.assertEqual(msg_id, "backtest:run-emit-2:failed")

        msg = asyncio.run(_fetch_last_event())
        env = json.loads(msg.data.decode())
        self.assertEqual(env["payload"]["event"], "failed")
        self.assertEqual(env["payload"]["error_code"], "BACKTEST_EXECUTION_FAILED")
        self.assertEqual(env["payload"]["error_message"], "boom")

    def test_emit_unknown_status_is_noop(self) -> None:
        from src.infrastructure.workers.backtest_event_emitter import emit_backtest_event_sync

        # Unknown statuses map to nothing and must not publish.
        self.assertIsNone(emit_backtest_event_sync(run_id="run-x", status="bogus"))

    def test_emit_disabled_is_noop(self) -> None:
        import os as _os

        from src.infrastructure.workers import backtest_event_emitter as em

        # The emitter treats either flag as enabled (mirrors the consumer), so
        # disable both.
        orig_nats = _os.environ.get("NATS_ENABLED")
        orig_bus = _os.environ.get("BOT_COMMAND_BUS_ENABLED")
        _os.environ["NATS_ENABLED"] = "false"
        _os.environ["BOT_COMMAND_BUS_ENABLED"] = "false"
        try:
            self.assertIsNone(em.emit_backtest_event_sync(run_id="run-x", status="started"))
        finally:
            for key, val in (("NATS_ENABLED", orig_nats), ("BOT_COMMAND_BUS_ENABLED", orig_bus)):
                if val is None:
                    _os.environ.pop(key, None)
                else:
                    _os.environ[key] = val


if __name__ == "__main__":
    unittest.main()
