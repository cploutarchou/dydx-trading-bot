"""Account-level (portfolio) risk controls for live entry decisions.

Per-instance limits (``max_positions`` etc.) count only what THIS instance
tracks, so N instances sharing one dYdX subaccount can each stay inside their
limits while the account as a whole is over-exposed. These controls close that
gap: they evaluate the SHARED subaccount — equity, free collateral, and the
number of open perpetual markets — which already reflects every instance's
fills, making it the authoritative portfolio view without any cross-process
state.

Design contract
---------------
* :func:`evaluate_portfolio_entry` is a PURE decision function: same inputs →
  same decision, no I/O, fully unit-testable (determinism requirement from the
  trading-strategy implementation standard).
* The decision is FAIL-CLOSED for new entries: missing/malformed account data
  denies the entry (``portfolio_data_unavailable``) rather than guessing.
  Transport errors are NOT swallowed here — they propagate exactly like the
  existing free-collateral guards in ``position_manager.open_positions``,
  preserving current cycle-level failure behavior.
* ``incremental_notional_usd`` is compared against free collateral as a
  conservative 1x-leverage approximation of the margin a new entry consumes
  (a pair entry commits ~2 × ``usd_per_trade`` notional across its legs).
* Checks with a limit <= 0 are disabled individually; the whole guard is off
  unless ``BOT_PORTFOLIO_RISK_ENABLED=true`` (Phase A: opt-in until proven in
  production, mirroring the broadcast-bus rollout pattern and the
  enforce-only-proven-controls philosophy in ``src/shared/live_risk_controls``).

Every denial is expected to be logged and persisted by the caller with the
machine-readable reason codes (audit-trail requirement).
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from src.constants import (
    BOT_PORTFOLIO_MAX_MARGIN_UTILIZATION_PCT,
    BOT_PORTFOLIO_MAX_OPEN_MARKETS,
    BOT_PORTFOLIO_MIN_FREE_COLLATERAL_USD,
    BOT_PORTFOLIO_RISK_ENABLED,
)
from src.trading.account_manager import get_account, get_open_positions


@dataclass(frozen=True)
class PortfolioRiskLimits:
    """Account-level entry limits; any field <= 0 disables that check."""

    max_open_markets: int
    max_margin_utilization_pct: float
    min_free_collateral_usd: float


@dataclass(frozen=True)
class PortfolioSnapshot:
    """Live view of the shared trading subaccount."""

    equity: float | None
    free_collateral: float | None
    open_market_count: int


@dataclass(frozen=True)
class PortfolioRiskDecision:
    allowed: bool
    reasons: tuple[str, ...]
    snapshot: PortfolioSnapshot | None
    limits: PortfolioRiskLimits

    @property
    def primary_reason(self) -> str:
        return self.reasons[0] if self.reasons else "allowed"


def _limits_from_config() -> PortfolioRiskLimits:
    return PortfolioRiskLimits(
        max_open_markets=BOT_PORTFOLIO_MAX_OPEN_MARKETS,
        max_margin_utilization_pct=BOT_PORTFOLIO_MAX_MARGIN_UTILIZATION_PCT,
        min_free_collateral_usd=BOT_PORTFOLIO_MIN_FREE_COLLATERAL_USD,
    )


def portfolio_risk_config() -> dict:
    """Operator-facing configuration snapshot (used by the monitoring route)."""
    limits = _limits_from_config()
    return {
        "enabled": BOT_PORTFOLIO_RISK_ENABLED,
        "limits": {
            "max_open_markets": limits.max_open_markets,
            "max_margin_utilization_pct": limits.max_margin_utilization_pct,
            "min_free_collateral_usd": limits.min_free_collateral_usd,
        },
        "incremental_notional": "pair entries consume ~2x usd_per_trade (1x approximation)",
    }


def evaluate_portfolio_entry(
    snapshot: PortfolioSnapshot,
    limits: PortfolioRiskLimits,
    *,
    incremental_notional_usd: float,
) -> PortfolioRiskDecision:
    """Decide whether a NEW entry keeps the account inside its limits.

    Deterministic and pure. At-limit is treated as full (the account may not
    grow to the bound, only up to it).
    """
    reasons: list[str] = []

    if (
        limits.max_open_markets > 0
        and snapshot.open_market_count >= limits.max_open_markets
    ):
        reasons.append("portfolio_max_open_markets")

    equity = snapshot.equity
    free_collateral = snapshot.free_collateral
    if equity is None or free_collateral is None:
        reasons.append("portfolio_data_unavailable")
    elif equity <= 0:
        reasons.append("portfolio_non_positive_equity")
    else:
        margin_utilization_pct = (equity - free_collateral) / equity * 100.0
        if (
            limits.max_margin_utilization_pct > 0
            and margin_utilization_pct >= limits.max_margin_utilization_pct
        ):
            reasons.append("portfolio_margin_utilization")
        projected_free_collateral = free_collateral - incremental_notional_usd
        if (
            limits.min_free_collateral_usd > 0
            and projected_free_collateral < limits.min_free_collateral_usd
        ):
            reasons.append("portfolio_free_collateral_floor")

    return PortfolioRiskDecision(
        allowed=not reasons,
        reasons=tuple(reasons),
        snapshot=snapshot,
        limits=limits,
    )


async def load_portfolio_snapshot(client) -> PortfolioSnapshot:
    """Read the shared subaccount's equity, free collateral, and open-market
    count via the circuit-broken indexer reads.

    Parse failures degrade to ``None`` fields (which the evaluator treats as
    fail-closed for entries); transport errors propagate to the caller, exactly
    like the existing free-collateral guards.
    """

    def _as_float(value) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    account = await get_account(client)
    open_positions = await get_open_positions(client)
    return PortfolioSnapshot(
        equity=_as_float(account.get("equity")),
        free_collateral=_as_float(account.get("freeCollateral")),
        open_market_count=len(open_positions),
    )


async def check_portfolio_entry_guard(
    client, *, incremental_notional_usd: float
) -> PortfolioRiskDecision:
    """Entry-point guard used by ``position_manager.open_positions``.

    Returns an ALLOW decision without touching the exchange when the guard is
    disabled; otherwise evaluates the live subaccount snapshot against the
    configured limits. Never raises for data-shape problems (fail-closed via
    ``portfolio_data_unavailable``); transport errors propagate like the
    neighboring collateral guards.
    """
    limits = _limits_from_config()
    if not BOT_PORTFOLIO_RISK_ENABLED:
        return PortfolioRiskDecision(
            allowed=True, reasons=("disabled",), snapshot=None, limits=limits
        )
    snapshot = await load_portfolio_snapshot(client)
    decision = evaluate_portfolio_entry(
        snapshot, limits, incremental_notional_usd=incremental_notional_usd
    )
    if not decision.allowed:
        logger.warning(
            "portfolio_risk_entry_denied reasons={} equity={} free_collateral={} "
            "open_markets={} limits.max_open_markets={} "
            "limits.max_margin_utilization_pct={} "
            "limits.min_free_collateral_usd={}",
            list(decision.reasons),
            snapshot.equity,
            snapshot.free_collateral,
            snapshot.open_market_count,
            limits.max_open_markets,
            limits.max_margin_utilization_pct,
            limits.min_free_collateral_usd,
        )
    return decision
