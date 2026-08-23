"""Ratchet guard for broad exception handling.

The improvement plan targets replacing the broad ``except Exception`` / bare
``except:`` sites across ``src/`` with specific, typed exceptions
(see ``src/exceptions.py``). This test pins the current count as a ceiling: any
change that ADDS a new broad catch fails the build until the author either
narrows it to a specific type or, if it is a genuinely necessary best-effort
catch, lowers ``BROAD_CATCH_BASELINE`` here with a justification.

Counting mirrors the project lint reality: every ``except Exception`` (with or
without ``as``) and every bare ``except:``. ``src/`` only — tests and generated
artifacts are out of scope.

When you remove or narrow broad catches, lower the baseline to the new count so
the ratchet keeps tightening toward the long-term goal.
"""

from __future__ import annotations

import re
from pathlib import Path

# Current count of broad catches in src/. Lower this when you narrow/remove one.
# Do NOT raise it without explicit justification (a new genuinely-broad best-effort catch).
# 315 -> 311 (2026-08-03, ratchet Phase 2): removed 4 redundant route-level
# `except Exception -> return api_response(500)` catch-alls in src/api/v1/backtests.py
# (create/stats/delete/live-progress) that are fully covered by the global
# @app.exception_handler(Exception) — api_response forces INTERNAL_ERROR_MESSAGE for
# any 500, and the global handler logs via logger.exception, so removal is
# response+logging neutral. (Skipped routes that return custom data/error codes.)
# 311 -> 310 (2026-08-05, market-data L2 cache): removed the ad-hoc
# `_get_recent_candles_from_redis` helper in src/trading/market_data.py (one
# `except Exception -> return None`); its responsibilities moved to the new
# best-effort `src/infrastructure/cache/` module, which this ratchet excludes by
# design (the `cache` directory is in `_EXCLUDED_DIR_PARTS` — intentional
# cache-miss isolation). market_data.py added no new broad catches.
# 310 -> 309 (2026-08-06, circuit-breaker framework): migrated the ad-hoc
# `_dydx_circuit_breaker` out of src/trading/market_data.py — removed two broad
# catches there (the `_notify_circuit_breaker_open` notifier guard and the
# pybreaker-construction fallback) — into the new centralized
# src/infrastructure/resilience/ module, which adds back ONE intentional
# best-effort notifier-isolation catch in `_fire_breaker_open_alert` (so a faulty
# open-notifier can never corrupt the breaker state machine). Net -1. The
# `resilience` directory is deliberately NOT excluded from this ratchet: it owns
# its one legitimate catch. market_data now guards calls via
# `resilience.call_async("dydx_indexer", ...)`.
# 309 (unchanged, 2026-08-06, cross-worker WebSocket broadcast bus): added
# src/infrastructure/broadcast/bus.py — a Redis pub/sub bus for cross-worker
# fan-out. Like src/infrastructure/cache, it is best-effort optional
# infrastructure where every command must degrade to a no-op on Redis failure,
# so it carries several intentional isolation `except Exception` blocks. The
# `broadcast` directory is therefore excluded from this ratchet (added to
# `_EXCLUDED_DIR_PARTS`) — same precedent as `cache`. websocket_server.py's
# refactor (broadcast_to_bot -> _deliver_local + publish) added NO new broad
# catches: the bus guarantees publish() never raises, so the producer needs no
# try/except. Net 0.
# 309 -> 297 (2026-08-11, dead-code-paths resolution, IMPROVEMENTS.md item #1):
# deleted the uncalled src/trading/realtime_data_service.py (11 best-effort
# `except Exception` blocks across its _monitor_bot / _update_* / _check_alerts
# / add_position_* paths — the service had no production caller, so none ever
# ran) and removed the post-backtest candle-aggregation call block in
# src/infrastructure/workers/backtest_tasks.py (1 `except Exception: pass`
# guarding aggregate_backtest_candles.delay, itself a no-op "skipped" stub that
# is now deleted along with its Celery registration). Net -12. The other parts
# of the resolution — mounting the 2FA router, repointing the repository_realtime
# shim import to the canonical path — introduced no broad catches.
# 2026-08-23: -3 — removed the dead Redis backtest-status pub-sub producer
# (`_publish_backtest_status` + its `_get_redis_client`) from
# src/infrastructure/workers/backtest_tasks.py; the channel had no subscriber
# anywhere (NATS JetStream events are the sanctioned status path and websocket
# clients are DB-pull-based), so the two broad catches in the publisher and one
# in the client factory went with it.
BROAD_CATCH_BASELINE = 294

# Matches "except Exception", "except Exception as e", "except Exception:" and bare "except:".
_BROAD_CATCH_RE = re.compile(r"\bexcept\s+(Exception|BaseException)\b|^\s*except\s*:")

# Directories under src/ that are generated/migrations or best-effort optional
# infrastructure (cache / broadcast) whose intentional isolation catches must not
# count toward the broad-catch total.
_EXCLUDED_DIR_PARTS = {"__pycache__", "migrations", "cache", "generated", "broadcast"}


def _src_root() -> Path:
    # tests/ -> repo bot/ -> src/
    return Path(__file__).resolve().parent.parent / "src"


def _iter_source_files(root: Path):
    for path in root.rglob("*.py"):
        if any(part in _EXCLUDED_DIR_PARTS for part in path.parts):
            continue
        yield path


def _count_broad_catches(root: Path) -> tuple[int, list[str]]:
    total = 0
    offenders: list[str] = []
    for path in _iter_source_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _BROAD_CATCH_RE.search(line):
                total += 1
    return total, offenders


def test_broad_catch_count_does_not_exceed_baseline():
    root = _src_root()
    count = _count_broad_catches(root)[0]
    assert count <= BROAD_CATCH_BASELINE, (
        f"Broad exception-catch count in src/ rose to {count} "
        f"(baseline {BROAD_CATCH_BASELINE}). Narrow the new 'except Exception' to a "
        f"specific type from src/exceptions.py, or — if a broad catch is genuinely "
        f"required as best-effort cleanup — lower BROAD_CATCH_BASELINE in this test "
        f"with a justification comment."
    )


def test_broad_catch_baseline_is_tight():
    """The baseline should equal the actual count (no slack left behind).

    This prevents contributors from lowering the baseline speculatively and
    creating hidden headroom. If you intentionally narrowed catches, update the
    baseline to the exact new count.
    """
    count = _count_broad_catches(_src_root())[0]
    assert count == BROAD_CATCH_BASELINE, (
        f"BROAD_CATCH_BASELINE={BROAD_CATCH_BASELINE} but actual count is {count}. "
        f"Update the baseline to {count} to keep the ratchet tight."
    )
