"""Real-schema integration tests for the NATS backtest consumer SQL.

Validates the Phase 0 acceptance criterion that every SQL statement in
nats_backtest_consumer.py matches the authoritative task-table schema
(migrations 000063..000067). These previously targeted nonexistent columns
(task_runs.requested_by_user_id, task_attempts.status) and inserted string ids
into UUID columns.

Runs only when ``NATS_CONSUMER_TEST_DSN`` points at a PostgreSQL database that
has migrations 000063..000067 applied, so it never breaks the normal suite::

    NATS_CONSUMER_TEST_DSN='postgres://user:pass@localhost:5432/dydx_task_test' \
      .venv/bin/python -m pytest tests/test_nats_consumer_sql_integration.py -v

The handler methods are async but perform only synchronous DB work, so the test
drives them through asyncio.run() in a plain unittest.TestCase (the repo's
IsolatedAsyncioTestCase harness deadlocks when mixing blocking psycopg2 calls
with its event loop).
"""

from __future__ import annotations

import asyncio
import os
import unittest
import uuid
from types import SimpleNamespace

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DSN_ENV = "NATS_CONSUMER_TEST_DSN"


def _normalize_dsn(raw: str) -> str:
    """Map a bare postgres:// URL to the SQLAlchemy psycopg2 driver form."""
    if raw.startswith("postgres://"):
        return "postgresql+psycopg2://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg2://" + raw[len("postgresql://"):]
    return raw


@unittest.skipUnless(
    os.getenv(DSN_ENV),
    f"{DSN_ENV} not set; skipping consumer SQL integration test",
)
class TestBacktestConsumerSQLIntegration(unittest.TestCase):
    """Exercises the consumer's DB writes against the real task-table schema."""

    def setUp(self):
        self.engine = create_engine(
            _normalize_dsn(os.environ[DSN_ENV]),
            future=True,
            connect_args={"connect_timeout": 5},
        )
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)

        # Track every session handed out by the stub so we can close them before
        # TRUNCATE. The handler commits but does not always close its session
        # (e.g. the idempotent "found existing run" path returns after a SELECT),
        # which would otherwise leave an idle-in-transaction connection holding a
        # lock that blocks the teardown TRUNCATE.
        self._handed_out_sessions = []

        def _new_session():
            session = self.session_factory()
            self._handed_out_sessions.append(session)
            return session

        # Pre-stub the database singleton BEFORE importing the consumer module so
        # the consumer's `from src.infrastructure.database import db` binds to a
        # stub pointed at the throwaway DB. This prevents the real DatabaseManager
        # from initializing against a shared dev database as an import side-effect.
        import src.infrastructure.database as database_mod

        self._database_mod = database_mod
        self._orig_database_db = database_mod.db
        database_stub = SimpleNamespace(get_session=_new_session)
        database_mod.db = database_stub

        import src.infrastructure.workers.nats_backtest_consumer as mod

        self._mod = mod
        self._orig_mod_db = mod.db
        mod.db = database_stub

        self._reset_tables()
        self.command_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO task_commands "
                    "(id, command_type, owner_type, owner_id, idempotency_key, payload_json, status) "
                    "VALUES (:id, 'backtest', 'backtest', :owner, :idem, '{}'::jsonb, 'pending')"
                ),
                {"id": self.command_id, "owner": "run-" + self.command_id[:8], "idem": "idem-" + self.command_id},
            )

    def tearDown(self):
        self._mod.db = self._orig_mod_db
        self._database_mod.db = self._orig_database_db
        self._reset_tables()
        self.engine.dispose()

    def _reset_tables(self):
        # Close any sessions the handler left open so their locks release before
        # the TRUNCATE takes an ACCESS EXCLUSIVE lock.
        for session in self._handed_out_sessions:
            try:
                session.rollback()
                session.close()
            except Exception:
                pass
        self._handed_out_sessions.clear()
        with self.engine.begin() as conn:
            conn.execute(text("TRUNCATE task_attempts, task_runs, task_commands RESTART IDENTITY CASCADE"))

    def _handler(self):
        from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler

        handler = BacktestCommandHandler()
        payload = handler._parse_payload(
            {"command_id": self.command_id, "idempotency_key": "idem-x", "run_id": "run-x"},
            {"message_id": self.command_id, "idempotency_key": "idem-x"},
        )
        return handler, payload

    def test_task_run_and_attempt_sql_matches_schema(self):
        """The previously-broken writes now execute cleanly against the schema."""
        handler, payload = self._handler()

        run_id = asyncio.run(handler._ensure_task_run(payload))
        self.assertIsNotNone(run_id)

        attempt_id = asyncio.run(handler._create_task_attempt(run_id, payload))
        self.assertIsNotNone(attempt_id)

        asyncio.run(handler._update_task_run_status(run_id, "running", 10.0))
        asyncio.run(handler._update_task_run_progress(run_id, 50.0))
        asyncio.run(handler._update_task_attempt_outcome(attempt_id, "success"))
        asyncio.run(handler._update_task_command_status(self.command_id, "completed"))

        with self.session_factory() as session:
            run = session.execute(
                text("SELECT status, progress_pct FROM task_runs WHERE id = :i"), {"i": run_id}
            ).fetchone()
            self.assertEqual(run[0], "running")
            self.assertEqual(float(run[1]), 50.0)

            cmd = session.execute(
                text("SELECT status FROM task_commands WHERE id = :i"), {"i": self.command_id}
            ).fetchone()
            self.assertEqual(cmd[0], "completed")

    def test_ensure_task_run_is_idempotent(self):
        """Re-calling _ensure_task_run for the same command returns the same run."""
        handler, payload = self._handler()

        first = asyncio.run(handler._ensure_task_run(payload))
        second = asyncio.run(handler._ensure_task_run(payload))
        self.assertEqual(first, second)

        with self.session_factory() as session:
            count = session.execute(
                text("SELECT count(*) FROM task_runs WHERE command_id = :i"), {"i": self.command_id}
            ).scalar()
            self.assertEqual(int(count), 1)

    # ------------------------------------------------------------------
    # Duplicate / redelivery barrier (Phase 2 idempotency evidence)
    # ------------------------------------------------------------------

    def _seed_command(self, idem_key: str, status: str) -> str:
        """Insert a task_commands row in a given status and return its id."""
        cmd_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO task_commands "
                    "(id, command_type, owner_type, owner_id, idempotency_key, payload_json, status) "
                    "VALUES (:id, 'backtest', 'backtest', :owner, :idem, '{}'::jsonb, :status)"
                ),
                {"id": cmd_id, "owner": "run-" + cmd_id[:8], "idem": idem_key, "status": status},
            )
        return cmd_id

    def test_duplicate_barrier_terminal_command_is_duplicate(self):
        """A terminal (completed/failed) command with the same key blocks redelivery."""
        from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler

        handler = BacktestCommandHandler()
        completed_id = self._seed_command("idem-terminal", "completed")

        # Same command id -> duplicate. Different command id but same key and
        # terminal status -> also duplicate (idempotency key wins).
        self.assertTrue(asyncio.run(handler._is_duplicate("idem-terminal", completed_id)))
        self.assertTrue(asyncio.run(handler._is_duplicate("idem-terminal", "00000000-0000-0000-0000-000000000000")))

        failed_id = self._seed_command("idem-failed", "failed")
        self.assertTrue(asyncio.run(handler._is_duplicate("idem-failed", failed_id)))

    def test_duplicate_barrier_nonterminal_command_is_not_duplicate(self):
        """A pending/published command does not block (re)processing."""
        from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler

        handler = BacktestCommandHandler()
        pending_id = self._seed_command("idem-pending", "pending")
        self.assertFalse(asyncio.run(handler._is_duplicate("idem-pending", pending_id)))

        published_id = self._seed_command("idem-published", "published")
        self.assertFalse(asyncio.run(handler._is_duplicate("idem-published", published_id)))

    def test_duplicate_barrier_unknown_key_is_not_duplicate(self):
        """An idempotency key with no command record is never a duplicate."""
        from src.infrastructure.workers.nats_backtest_consumer import BacktestCommandHandler

        handler = BacktestCommandHandler()
        self.assertFalse(asyncio.run(handler._is_duplicate("idem-absent", str(uuid.uuid4()))))

    def test_handle_acks_duplicate_redelivery_without_reprocessing(self):
        """Redelivery of a terminal command ACKs and never re-runs the backtest.

        This is the authoritative duplicate barrier: the consumer must not create
        a second task_run/attempt or re-execute side effects for a command that
        already reached terminal state. handle() returns ACK for the duplicate.
        """
        from src.infrastructure.workers.nats_backtest_consumer import (
            BacktestCommandHandler,
            MessageAction,
        )

        handler = BacktestCommandHandler()
        completed_id = self._seed_command("idem-redeliver", "completed")

        result = asyncio.run(
            handler.handle(
                {"command_id": completed_id, "idempotency_key": "idem-redeliver", "run_id": "run-x"},
                {"message_id": completed_id, "idempotency_key": "idem-redeliver", "consumer_name": "backtest-worker"},
            )
        )

        self.assertEqual(result.action, MessageAction.ACK)
        # No task_run should have been created for a redelivered terminal command.
        with self.session_factory() as session:
            runs = session.execute(
                text("SELECT count(*) FROM task_runs WHERE command_id = :i"), {"i": completed_id}
            ).scalar()
            self.assertEqual(int(runs), 0)
