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
* Checks with a limit <= 0 are disabled individually. The master switch
  ``BOT_PORTFOLIO_RISK_ENABLED`` is ON by default since the Phase B flip
  (2026-08-17, after the testnet burn-in — see
  ``docs/bot-risk-control-matrix.md``); ``=false`` restores the pre-guard
  behavior (mirroring the broadcast-bus rollout, whose flip also followed a
  recorded burn-in, and the enforce-only-proven-controls philosophy in
  ``src/shared/live_risk_controls``).

Every denial is expected to be logged and persisted by the caller with the
machine-readable reason codes (audit-trail requirement).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from loguru import logger

from src.constants import (
    BOT_PORTFOLIO_AGGREGATE_MAX_MARGIN_UTILIZATION_PCT,
    BOT_PORTFOLIO_AGGREGATE_MAX_OPEN_MARKETS,
    BOT_PORTFOLIO_CORRELATION_BUCKETS,
    BOT_PORTFOLIO_MAX_DAILY_LOSS_PCT,
    BOT_PORTFOLIO_MAX_DRAWDOWN_PCT,
    BOT_PORTFOLIO_MAX_MARGIN_UTILIZATION_PCT,
    BOT_PORTFOLIO_MAX_NOTIONAL_PER_MARKET_USD,
    BOT_PORTFOLIO_MAX_OPEN_MARKETS,
    BOT_PORTFOLIO_MAX_TOTAL_NOTIONAL_PCT,
    BOT_PORTFOLIO_MIN_FREE_COLLATERAL_USD,
    BOT_PORTFOLIO_RISK_ENABLED,
    MARKET_DATA_MODE,
)
from src.shared.redis_env import redis_url
from src.trading.account_manager import (
    get_account,
    get_open_positions,
    resolve_client_address_or_none,
)
from src.trading.portfolio_accounts import (
    AccountExposure,
    AggregateExposureTotals,
    enumerate_portfolio_accounts,
    load_account_exposures_via_client,
    summarize_exposures,
)


@dataclass(frozen=True)
class CorrelationBucket:
    """Operator-defined group of markets whose combined notional is capped.

    Buckets are how correlation/concentration risk is expressed without market
    metadata plumbing: the operator lists the tickers that move together (e.g.
    ``majors:BTC-USD,ETH-USD``) and a cap as % of equity for the group.
    """

    name: str
    markets: frozenset[str]
    max_notional_pct_of_equity: float


def parse_correlation_buckets(raw: str) -> tuple[CorrelationBucket, ...]:
    """Parse the ``BOT_PORTFOLIO_CORRELATION_BUCKETS`` specification.

    Format: ``NAME:m1,m2,...:max_pct_of_equity`` entries joined by ``;``.
    Parsing fails OPEN per entry — anything malformed is skipped with a
    warning rather than disabling or crashing the guard — and duplicate
    bucket names keep the first definition.
    """
    buckets: list[CorrelationBucket] = []
    seen_names: set[str] = set()
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) != 3:
            logger.warning(
                "portfolio_risk_bucket_entry_skipped entry={!r} reason=expected 'name:markets:pct'",
                entry,
            )
            continue
        name, markets_part, pct_part = (part.strip() for part in parts)
        markets = frozenset(m.strip() for m in markets_part.split(",") if m.strip())
        try:
            pct = float(pct_part)
        except ValueError:
            logger.warning(
                "portfolio_risk_bucket_entry_skipped entry={!r} reason=invalid pct",
                entry,
            )
            continue
        if not name or not markets or pct <= 0:
            logger.warning(
                "portfolio_risk_bucket_entry_skipped entry={!r} reason=empty name/markets or pct<=0",
                entry,
            )
            continue
        if name in seen_names:
            logger.warning(
                "portfolio_risk_bucket_entry_skipped entry={!r} reason=duplicate name",
                entry,
            )
            continue
        seen_names.add(name)
        buckets.append(
            CorrelationBucket(
                name=name,
                markets=markets,
                max_notional_pct_of_equity=pct,
            )
        )
    return tuple(buckets)


_bucket_parse_cache: tuple[str, tuple[CorrelationBucket, ...]] = ("", ())


def _correlation_buckets_from_config() -> tuple[CorrelationBucket, ...]:
    """Parsed buckets, cached per distinct raw spec (avoids warn-per-entry)."""
    global _bucket_parse_cache
    raw = BOT_PORTFOLIO_CORRELATION_BUCKETS
    if _bucket_parse_cache[0] != raw:
        _bucket_parse_cache = (raw, parse_correlation_buckets(raw))
    return _bucket_parse_cache[1]


@dataclass(frozen=True)
class PortfolioRiskLimits:
    """Account-level entry limits; any field <= 0 disables that check.

    The ``aggregate_*`` fields cap the deployment-wide totals across every
    distinct subaccount configured in ``bot_instances`` (same network as the
    worker); they default to 0 (off) and only engage when the master switch is
    on — enabling either one also turns on cross-address public indexer reads.
    """

    max_open_markets: int
    max_margin_utilization_pct: float
    min_free_collateral_usd: float
    max_drawdown_pct: float
    aggregate_max_open_markets: int = 0
    aggregate_max_margin_utilization_pct: float = 0.0
    max_notional_per_market_usd: float = 0.0
    max_total_notional_pct: float = 0.0
    max_daily_loss_pct: float = 0.0
    correlation_buckets: tuple[CorrelationBucket, ...] = ()


@dataclass(frozen=True)
class PortfolioSnapshot:
    """Live view of the shared trading subaccount.

    ``per_market_notional_usd`` approximates booked exposure per open
    perpetual market as ``|size| x entryPrice`` (the position payload has no
    mark price; entry price is the deterministic, conservative-enough
    exposure the account actually took). ``unparsed_position_count`` counts
    positions whose size/price could not be parsed — any active notional
    control fails closed on it instead of silently under-counting exposure.
    """

    equity: float | None
    free_collateral: float | None
    open_market_count: int
    per_market_notional_usd: dict[str, float] = field(default_factory=dict)
    unparsed_position_count: int = 0

    @property
    def total_notional_usd(self) -> float:
        return sum(self.per_market_notional_usd.values())


@dataclass(frozen=True)
class PortfolioRiskDecision:
    allowed: bool
    reasons: tuple[str, ...]
    snapshot: PortfolioSnapshot | None
    limits: PortfolioRiskLimits
    aggregate_totals: AggregateExposureTotals | None = None

    @property
    def primary_reason(self) -> str:
        return self.reasons[0] if self.reasons else "allowed"


@dataclass(frozen=True)
class AggregateRiskEvaluation:
    """Pure result of the deployment-wide aggregate checks."""

    allowed: bool
    reasons: tuple[str, ...]
    totals: AggregateExposureTotals
    limits: PortfolioRiskLimits


def _limits_from_config() -> PortfolioRiskLimits:
    return PortfolioRiskLimits(
        max_open_markets=BOT_PORTFOLIO_MAX_OPEN_MARKETS,
        max_margin_utilization_pct=BOT_PORTFOLIO_MAX_MARGIN_UTILIZATION_PCT,
        min_free_collateral_usd=BOT_PORTFOLIO_MIN_FREE_COLLATERAL_USD,
        max_drawdown_pct=BOT_PORTFOLIO_MAX_DRAWDOWN_PCT,
        aggregate_max_open_markets=BOT_PORTFOLIO_AGGREGATE_MAX_OPEN_MARKETS,
        aggregate_max_margin_utilization_pct=(
            BOT_PORTFOLIO_AGGREGATE_MAX_MARGIN_UTILIZATION_PCT
        ),
        max_notional_per_market_usd=BOT_PORTFOLIO_MAX_NOTIONAL_PER_MARKET_USD,
        max_total_notional_pct=BOT_PORTFOLIO_MAX_TOTAL_NOTIONAL_PCT,
        max_daily_loss_pct=BOT_PORTFOLIO_MAX_DAILY_LOSS_PCT,
        correlation_buckets=_correlation_buckets_from_config(),
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
            "max_drawdown_pct": limits.max_drawdown_pct,
            "aggregate_max_open_markets": limits.aggregate_max_open_markets,
            "aggregate_max_margin_utilization_pct": (
                limits.aggregate_max_margin_utilization_pct
            ),
            "max_notional_per_market_usd": limits.max_notional_per_market_usd,
            "max_total_notional_pct": limits.max_total_notional_pct,
            "max_daily_loss_pct": limits.max_daily_loss_pct,
        },
        "correlation_buckets": [
            {
                "name": bucket.name,
                "markets": sorted(bucket.markets),
                "max_notional_pct_of_equity": bucket.max_notional_pct_of_equity,
            }
            for bucket in limits.correlation_buckets
        ],
        "incremental_notional": "pair entries consume ~2x usd_per_trade (1x approximation)",
    }


def evaluate_portfolio_entry(
    snapshot: PortfolioSnapshot,
    limits: PortfolioRiskLimits,
    *,
    incremental_notional_usd: float,
    peak_equity: float | None = None,
    daily_peak_equity: float | None = None,
    entry_markets: tuple[str, ...] = (),
    per_leg_notional_usd: float = 0.0,
) -> PortfolioRiskDecision:
    """Decide whether a NEW entry keeps the account inside its limits.

    Deterministic and pure. At-limit is treated as full (the account may not
    grow to the bound, only up to it). ``peak_equity`` is the ratcheted
    all-time peak and ``daily_peak_equity`` the UTC-day peak used by the two
    loss checks; ``None`` (Redis unavailable) skips that check — the loss
    controls are best-effort auxiliary state, unlike the exchange-read
    controls which fail closed. ``entry_markets``/``per_leg_notional_usd``
    describe the legs of the proposed pair entry for the notional
    concentration checks (a pair entry books ``per_leg_notional_usd`` in each
    of its two markets).
    """
    reasons: list[str] = []

    if (
        limits.max_open_markets > 0
        and snapshot.open_market_count >= limits.max_open_markets
    ):
        reasons.append("portfolio_max_open_markets")

    notional_controls_active = (
        limits.max_notional_per_market_usd > 0
        or limits.max_total_notional_pct > 0
        or bool(limits.correlation_buckets)
    )
    if notional_controls_active and snapshot.unparsed_position_count > 0:
        # Never under-count exposure: an unreadable position makes the
        # notional math unreliable, so deny instead of guessing.
        reasons.append("portfolio_notional_data_incomplete")

    equity = snapshot.equity
    free_collateral = snapshot.free_collateral
    if equity is None or free_collateral is None:
        reasons.append("portfolio_data_unavailable")
    elif equity <= 0:
        reasons.append("portfolio_non_positive_equity")
    else:
        if limits.max_drawdown_pct > 0 and peak_equity is not None and peak_equity > 0:
            drawdown_pct = (peak_equity - equity) / peak_equity * 100.0
            if drawdown_pct >= limits.max_drawdown_pct:
                reasons.append("portfolio_max_drawdown")
        if (
            limits.max_daily_loss_pct > 0
            and daily_peak_equity is not None
            and daily_peak_equity > 0
        ):
            daily_loss_pct = (daily_peak_equity - equity) / daily_peak_equity * 100.0
            if daily_loss_pct >= limits.max_daily_loss_pct:
                reasons.append("portfolio_daily_loss")
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
        if limits.max_notional_per_market_usd > 0:
            for market in entry_markets:
                projected = (
                    snapshot.per_market_notional_usd.get(market, 0.0)
                    + per_leg_notional_usd
                )
                if projected >= limits.max_notional_per_market_usd:
                    reasons.append("portfolio_market_concentration")
                    break
        if limits.max_total_notional_pct > 0:
            projected_total = snapshot.total_notional_usd + per_leg_notional_usd * len(
                entry_markets
            )
            projected_total_pct = projected_total / equity * 100.0
            if projected_total_pct >= limits.max_total_notional_pct:
                reasons.append("portfolio_gross_notional")
        if limits.correlation_buckets:
            for bucket in limits.correlation_buckets:
                held = sum(
                    snapshot.per_market_notional_usd.get(market, 0.0)
                    for market in bucket.markets
                )
                legs_in_bucket = sum(
                    1 for market in entry_markets if market in bucket.markets
                )
                projected_bucket = held + per_leg_notional_usd * legs_in_bucket
                bucket_cap_usd = equity * bucket.max_notional_pct_of_equity / 100.0
                if projected_bucket >= bucket_cap_usd:
                    reasons.append(f"portfolio_bucket_concentration:{bucket.name}")

    return PortfolioRiskDecision(
        allowed=not reasons,
        reasons=tuple(reasons),
        snapshot=snapshot,
        limits=limits,
    )


def evaluate_aggregate_entry(
    exposures: tuple[AccountExposure, ...],
    limits: PortfolioRiskLimits,
) -> AggregateRiskEvaluation:
    """Decide whether deployment-wide totals stay inside the aggregate limits.

    Deterministic and pure. Totals come from
    :func:`src.trading.portfolio_accounts.summarize_exposures` (equity and free
    collateral sum COMPLETE accounts only; open markets count every account).
    There is deliberately no aggregate free-collateral floor — margin is
    isolated per subaccount on dYdX v4, so the floor stays a per-account
    check. ``sum(total_equity) <= 0`` skips the utilization check (nothing to
    compute); the per-account controls still fail closed on their own.
    """
    totals = summarize_exposures(exposures)
    reasons: list[str] = []

    if (
        limits.aggregate_max_open_markets > 0
        and totals.total_open_markets >= limits.aggregate_max_open_markets
    ):
        reasons.append("portfolio_aggregate_max_open_markets")

    utilization = totals.margin_utilization_pct
    if (
        limits.aggregate_max_margin_utilization_pct > 0
        and utilization is not None
        and utilization >= limits.aggregate_max_margin_utilization_pct
    ):
        reasons.append("portfolio_aggregate_margin_utilization")

    return AggregateRiskEvaluation(
        allowed=not reasons,
        reasons=tuple(reasons),
        totals=totals,
        limits=limits,
    )


async def load_portfolio_snapshot(client) -> PortfolioSnapshot:
    """Read the shared subaccount's equity, free collateral, open-market
    count, and per-market notionals via the circuit-broken indexer reads.

    Parse failures degrade to ``None`` fields (which the evaluator treats as
    fail-closed for entries); transport errors propagate to the caller, exactly
    like the existing free-collateral guards. Per-market notional uses the
    shared ``parse_open_positions_notional`` exposure math (``|size| x
    entryPrice`` per open perpetual, no mark price in the payload); positions
    that fail to parse are counted in ``unparsed_position_count`` so the
    notional controls can fail closed.
    """

    def _as_float(value) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    from src.trading.portfolio_accounts import parse_open_positions_notional

    account = await get_account(client)
    open_positions = await get_open_positions(client)
    per_market_notional, unparsed_position_count = parse_open_positions_notional(
        open_positions
    )
    return PortfolioSnapshot(
        equity=_as_float(account.get("equity")),
        free_collateral=_as_float(account.get("freeCollateral")),
        open_market_count=len(open_positions),
        per_market_notional_usd=per_market_notional,
        unparsed_position_count=unparsed_position_count,
    )


# Daily-peak keys outlive their UTC day generously so a short Redis clock
# skew can never resurrect yesterday's peak, then expire on their own.
_DAILY_PEAK_TTL_SECONDS = 172800  # 48 h


class RedisPeakEquityStore:
    """Ratcheted peak equity per wallet address, backed by Redis.

    Two variants share the implementation: the ALL-TIME peak (never resets;
    used by the drawdown check) and the UTC-DAY peak (dated key with a 48 h
    TTL, used by the daily loss limit so it self-heals each UTC midnight).
    The peak only ever moves UP (``max(stored, observed)``), so concurrent
    writers race benignly and converge. Redis here is auxiliary coordination
    state, not a trading dependency: every operation is non-raising and a
    failure simply returns ``None`` (the loss checks then skip themselves —
    see :func:`evaluate_portfolio_entry`). Reset the all-time peak with
    ``redis-cli DEL bot:portfolio:peak_equity:<address>``; daily keys expire
    on their own.
    """

    def __init__(
        self,
        *,
        url: str,
        socket_timeout: float = 1.0,
        connect_timeout: float = 1.0,
        client: object | None = None,
    ) -> None:
        self._url = url
        self._socket_timeout = float(socket_timeout)
        self._connect_timeout = float(connect_timeout)
        # ``client`` is an injection seam for tests; production leaves it None.
        self._client = client

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:  # pragma: no cover - optional-connection path, built lazily
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(
                self._url,
                decode_responses=True,
                socket_timeout=self._socket_timeout,
                socket_connect_timeout=self._connect_timeout,
            )
        except (OSError, ValueError, TypeError):
            self._client = None
        return self._client

    @staticmethod
    def _key(address: str) -> str:
        return f"bot:portfolio:peak_equity:{address}"

    @staticmethod
    def _daily_key(address: str) -> str:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"bot:portfolio:daily_peak_equity:{address}:{day}"

    async def observe(self, address: str, equity: float) -> float | None:
        """Fold ``equity`` into the stored ALL-TIME peak and return it.

        Returns ``None`` when Redis is unavailable or the stored value is
        malformed — never raises.
        """
        return await self._fold_peak(self._key(address), equity, ttl=None)

    async def observe_daily(self, address: str, equity: float) -> float | None:
        """Fold ``equity`` into the stored UTC-DAY peak and return it.

        Same ratchet semantics as :meth:`observe`, but the key is dated so the
        limit self-heals at the next UTC midnight; entries carry a TTL (48 h)
        so stale day keys garbage-collect themselves. Never raises.
        """
        return await self._fold_peak(
            self._daily_key(address), equity, ttl=_DAILY_PEAK_TTL_SECONDS
        )

    async def _fold_peak(
        self, key: str, equity: float, *, ttl: int | None
    ) -> float | None:
        client = self._ensure_client()
        if client is None:
            return None
        try:
            import redis.exceptions as redis_errors

            raw = await client.get(key)
            stored_peak: float | None = None
            if raw not in (None, ""):
                stored_peak = float(raw)
            new_peak = max(stored_peak, equity) if stored_peak else equity
            if stored_peak is None or new_peak != stored_peak:
                if ttl is not None:
                    await client.set(key, repr(float(new_peak)), ex=ttl)
                else:
                    await client.set(key, repr(float(new_peak)))
            return float(new_peak)
        except (redis_errors.RedisError, OSError, ValueError, TypeError):
            return None


_peak_equity_store: RedisPeakEquityStore | None = None


def get_peak_equity_store() -> RedisPeakEquityStore:
    """Process-wide peak store (lazy singleton; tests reset via ``reset_peak_equity_store``)."""
    global _peak_equity_store
    if _peak_equity_store is None:
        _peak_equity_store = RedisPeakEquityStore(
            url=redis_url(prefer_celery_broker=True),
        )
    return _peak_equity_store


def reset_peak_equity_store() -> None:
    """Drop the cached singleton (tests / forced reconfiguration)."""
    global _peak_equity_store
    _peak_equity_store = None


async def check_portfolio_entry_guard(
    client,
    *,
    incremental_notional_usd: float,
    entry_markets: tuple[str, ...] = (),
    per_leg_notional_usd: float = 0.0,
) -> PortfolioRiskDecision:
    """Entry-point guard used by ``position_manager.open_positions``.

    Returns an ALLOW decision without touching the exchange when the guard is
    disabled; otherwise evaluates the live subaccount snapshot against the
    configured limits. When an aggregate limit is configured (> 0), the
    deployment's OTHER same-network subaccounts (enumerated from
    ``bot_instances``) are read via public indexer calls and the aggregate
    checks run on top — with no extra exchange reads when both aggregate
    limits are off (the default). ``entry_markets``/``per_leg_notional_usd``
    feed the notional concentration checks (each pair leg books
    ``per_leg_notional_usd`` in its market). Never raises for data-shape
    problems (fail-closed via ``portfolio_data_unavailable``); transport
    errors propagate like the neighboring collateral guards.
    """
    limits = _limits_from_config()
    if not BOT_PORTFOLIO_RISK_ENABLED:
        return PortfolioRiskDecision(
            allowed=True, reasons=("disabled",), snapshot=None, limits=limits
        )
    snapshot = await load_portfolio_snapshot(client)
    address = None
    peak_equity: float | None = None
    daily_peak_equity: float | None = None
    if snapshot.equity is not None:
        address = resolve_client_address_or_none(client)
        if address:
            peak_equity = await get_peak_equity_store().observe(
                address, snapshot.equity
            )
            if limits.max_daily_loss_pct > 0:
                # Only touch Redis for the daily key when the control is on.
                daily_peak_equity = await get_peak_equity_store().observe_daily(
                    address, snapshot.equity
                )
    decision = evaluate_portfolio_entry(
        snapshot,
        limits,
        incremental_notional_usd=incremental_notional_usd,
        peak_equity=peak_equity,
        daily_peak_equity=daily_peak_equity,
        entry_markets=tuple(m for m in entry_markets if m),
        per_leg_notional_usd=per_leg_notional_usd,
    )
    aggregate_evaluation = await _evaluate_aggregate_if_configured(
        client, limits=limits, snapshot=snapshot
    )
    if aggregate_evaluation is not None:
        decision = PortfolioRiskDecision(
            allowed=decision.allowed and aggregate_evaluation.allowed,
            reasons=decision.reasons + aggregate_evaluation.reasons,
            snapshot=decision.snapshot,
            limits=decision.limits,
            aggregate_totals=aggregate_evaluation.totals,
        )
    if not decision.allowed:
        logger.warning(
            "portfolio_risk_entry_denied reasons={} equity={} free_collateral={} "
            "open_markets={} total_notional_usd={} limits.max_open_markets={} "
            "limits.max_margin_utilization_pct={} "
            "limits.min_free_collateral_usd={}",
            list(decision.reasons),
            snapshot.equity,
            snapshot.free_collateral,
            snapshot.open_market_count,
            snapshot.total_notional_usd,
            limits.max_open_markets,
            limits.max_margin_utilization_pct,
            limits.min_free_collateral_usd,
        )
        if aggregate_evaluation is not None:
            logger.warning(
                "portfolio_risk_aggregate_denied reasons={} total_open_markets={} "
                "total_equity={} total_free_collateral={} accounts={} "
                "incomplete_accounts={}",
                list(aggregate_evaluation.reasons),
                aggregate_evaluation.totals.total_open_markets,
                aggregate_evaluation.totals.total_equity,
                aggregate_evaluation.totals.total_free_collateral,
                aggregate_evaluation.totals.accounts,
                aggregate_evaluation.totals.incomplete_accounts,
            )
    return decision


def _own_network_tag() -> str:
    """The worker's own network, normalized to the enumeration tag."""
    return "testnet" if MARKET_DATA_MODE == "TESTNET" else "mainnet"


async def _evaluate_aggregate_if_configured(
    client, *, limits: PortfolioRiskLimits, snapshot: PortfolioSnapshot
) -> AggregateRiskEvaluation | None:
    """Run the deployment-wide aggregate checks when a limit is configured.

    Skips entirely (no enumeration, no extra exchange reads) when both
    aggregate limits are off — the default. Own-account exposure is folded in
    from the already-loaded snapshot; foreign same-network accounts come from
    the public per-address indexer reads.
    """
    if (
        limits.aggregate_max_open_markets <= 0
        and limits.aggregate_max_margin_utilization_pct <= 0
    ):
        return None

    own_address = resolve_client_address_or_none(client) or ""
    own_network = _own_network_tag()
    refs = await enumerate_portfolio_accounts()
    foreign_refs = tuple(
        ref for ref in refs if ref.network == own_network and ref.address != own_address
    )
    own_exposure = AccountExposure(
        address=own_address,
        network=own_network,
        equity=snapshot.equity,
        free_collateral=snapshot.free_collateral,
        open_market_count=snapshot.open_market_count,
        complete=snapshot.equity is not None and snapshot.free_collateral is not None,
    )
    exposures: tuple[AccountExposure, ...] = (own_exposure,)
    if foreign_refs:
        foreign_exposures = await load_account_exposures_via_client(
            client, foreign_refs
        )
        exposures = (own_exposure,) + foreign_exposures
    return evaluate_aggregate_entry(exposures, limits)
