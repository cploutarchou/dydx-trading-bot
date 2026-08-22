"""Ratchet guard for the mypy ``disallow_untyped_defs`` exemption list.

Phase 3a of type-check tightening (2026-08-22) turned
``disallow_untyped_defs = true`` on globally in ``pyproject.toml``: every NEW
module must be fully annotated. Modules that still carried pre-annotation defs
were placed on a per-module override list (``disallow_untyped_defs = false``)
so the blocking ``bot-typecheck`` gate could keep running at 0 errors.

This test pins that exemption list as a frozen set: a change that ADDS a
module to the list fails the build — dodging the annotation requirement for
new code must be a visible, reviewable decision recorded here. Removing
entries is always allowed (and expected): when you migrate a module, annotate
its defs until ``.venv/bin/python -m mypy src`` is clean, remove the entry in
``pyproject.toml``, and remove it from ``EXPECTED_EXEMPT_MODULES`` below in the
same change.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"

# Frozen exemption set (11 modules after phase 3c, 2026-08-22). Shrinks over
# time; NEVER grows without an explicit justification edit here.
# Phase 3a baseline (2026-08-22): 24 modules.
# Phase 3b (2026-08-22): -7 (workers/backtest_tasks, trading/portfolio_risk,
# trading/analysis/cointegration, shared/dataframe_utils, api/v1/bot_records,
# api/v1/auth, api/v1/arbitrage).
# Phase 3c (2026-08-22): -6 (api/v1/bot_lifecycle, api/v1/celery_admin,
# api/v1/monitoring, infrastructure/persistence/repository,
# infrastructure/persistence/repository_realtime, trading/market_data).
EXPECTED_EXEMPT_MODULES = frozenset(
    {
        "src.api.server",
        "src.api.v1.backtests",
        "src.api.v1.bot_realtime",
        "src.api.v1.strategies",
        "src.api.websocket_server",
        "src.bot_instance_manager",
        "src.infrastructure.database",
        "src.main_instance",
        "src.trading.account_manager",
        "src.trading.bot_agent",
        "src.trading.position_manager",
    }
)


def _exempt_modules_from_pyproject() -> set[str]:
    with _PYPROJECT.open("rb") as fh:
        data = tomllib.load(fh)
    modules: set[str] = set()
    for override in data.get("tool", {}).get("mypy", {}).get("overrides", []):
        if override.get("disallow_untyped_defs") is False:
            entries = override.get("module", [])
            if isinstance(entries, str):
                entries = [entries]
            modules.update(entries)
    return modules


def test_disallow_untyped_defs_is_enabled_globally() -> None:
    """The strict flag itself must stay on — weakening it needs review here."""
    with _PYPROJECT.open("rb") as fh:
        data = tomllib.load(fh)
    mypy_cfg = data["tool"]["mypy"]
    assert mypy_cfg.get("disallow_untyped_defs") is True, (
        "disallow_untyped_defs must remain enabled globally; per-module "
        "exemptions are the only sanctioned escape hatch (and are pinned below)"
    )
    assert mypy_cfg.get("warn_return_any") is True


def test_exemption_list_matches_frozen_set() -> None:
    """No silent growth: the pyproject list must equal the frozen set exactly."""
    actual = _exempt_modules_from_pyproject()
    expected = set(EXPECTED_EXEMPT_MODULES)
    added = actual - expected
    removed = expected - actual
    assert not added, (
        "New module(s) added to the disallow_untyped_defs exemption list: "
        f"{sorted(added)}. New code must be fully type-annotated. If this is "
        "a genuinely necessary exception, justify it and add the module to "
        "EXPECTED_EXEMPT_MODULES in this file (visible in review)."
    )
    assert not removed, (
        "Module(s) removed from the exemption list but still present in "
        f"EXPECTED_EXEMPT_MODULES: {sorted(removed)}. Congratulations — remove "
        "them from this test's frozen set in the same change so the ratchet "
        "keeps tightening."
    )
