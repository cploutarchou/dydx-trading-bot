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
BROAD_CATCH_BASELINE = 315

# Matches "except Exception", "except Exception as e", "except Exception:" and bare "except:".
_BROAD_CATCH_RE = re.compile(r"\bexcept\s+(Exception|BaseException)\b|^\s*except\s*:")

# Directories under src/ that are generated/migrations and must not count.
_EXCLUDED_DIR_PARTS = {"__pycache__", "migrations", "cache", "generated"}


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
