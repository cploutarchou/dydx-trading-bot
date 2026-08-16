"""Enumeration and exposure reads for the deployment's trading subaccounts.

The Phase A portfolio guard evaluates ONE subaccount — the worker's own. This
module extends the portfolio view across EVERY distinct wallet address
configured in ``bot_instances`` (per network), enabling:

* **Visibility**: the ``GET /api/v1/monitoring/portfolio-risk`` route reports
  per-address and per-network aggregate exposure (equity, free collateral,
  open perpetual markets).
* **Aggregate entry limits** (opt-in, enforced in ``portfolio_risk``): caps on
  deployment-wide open markets and aggregate margin utilization across all
  subaccounts on the worker's network.

Design contract
---------------
* dYdX v4 indexer account reads are PUBLIC per address — aggregation needs
  only the address list, never the signing credentials.
* Enumeration decrypts each ``bot_instances.config`` best-effort (mirroring
  ``bot_instance_manager._coerce_record_config_payload``): an undecryptable
  row falls back to its raw payload and is skipped when no address is
  readable, so one bad row never aborts the portfolio view.
* Results are deduplicated on ``(network, address)`` and sorted for
  deterministic ordering (multi-instance determinism requirement).
* The address list is cached per process for
  ``BOT_PORTFOLIO_ACCOUNTS_CACHE_TTL_SECONDS`` so entry decisions do not
  re-decrypt every bot row on every check.
* A 404 from the indexer is a definitive "no subaccount exists" answer and is
  reported as a COMPLETE zero-exposure account, not as missing data.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

from loguru import logger

from src.constants import (
    BOT_PORTFOLIO_ACCOUNTS_CACHE_TTL_SECONDS,
    BOT_PORTFOLIO_ACCOUNTS_HTTP_TIMEOUT_SECONDS,
    BOT_PORTFOLIO_AGGREGATE_MAX_ACCOUNTS,
    INDEXER_ENDPOINT_MAINNET,
    INDEXER_ENDPOINT_TESTNET,
    SUBACCOUNT_NUMBER,
)
from src.shared.credentials_cipher import (
    CredentialDecryptionError,
    open_config_secrets,
)

_NETWORK_TESTNET = "testnet"
_NETWORK_MAINNET = "mainnet"


@dataclass(frozen=True)
class PortfolioAccountRef:
    """A distinct trading subaccount configured in ``bot_instances``."""

    address: str
    network: str  # "testnet" | "mainnet"


@dataclass(frozen=True)
class AccountExposure:
    """Live exposure of one subaccount (public indexer view).

    ``complete`` is False when the payload was readable but malformed (the
    equity/free-collateral sums must then exclude this account), or when the
    read failed outright (``error`` carries the reason). ``open_market_count``
    is still reported when known — a readable-but-malformed account keeps its
    positions count.
    """

    address: str
    network: str
    equity: float | None
    free_collateral: float | None
    open_market_count: int
    complete: bool
    error: str | None = None


@dataclass(frozen=True)
class AggregateExposureTotals:
    """Deterministic sums over a set of account exposures."""

    accounts: int
    incomplete_accounts: int
    total_equity: float
    total_free_collateral: float
    total_open_markets: int

    @property
    def margin_utilization_pct(self) -> float | None:
        if self.total_equity <= 0:
            return None
        return (
            (self.total_equity - self.total_free_collateral)
            / (self.total_equity)
            * 100.0
        )


def normalize_network(raw: Any) -> str:
    """Map a ``bot_instances.network`` value onto the canonical tags."""
    return (
        _NETWORK_MAINNET
        if str(raw or "").strip().lower() == _NETWORK_MAINNET
        else _NETWORK_TESTNET
    )


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_http_404(exc: BaseException) -> bool:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None) == 404


def parse_account_exposure(
    ref: PortfolioAccountRef, subaccount_payload: Any
) -> AccountExposure:
    """Build an :class:`AccountExposure` from a subaccount payload dict.

    Malformed fields degrade to ``None`` (incomplete) rather than raising —
    the pure evaluator decides what that means.
    """
    payload = subaccount_payload if isinstance(subaccount_payload, dict) else {}
    equity = _as_float(payload.get("equity"))
    free_collateral = _as_float(payload.get("freeCollateral"))
    positions = payload.get("openPerpetualPositions")
    open_market_count = len(positions) if isinstance(positions, dict) else 0
    return AccountExposure(
        address=ref.address,
        network=ref.network,
        equity=equity,
        free_collateral=free_collateral,
        open_market_count=open_market_count,
        complete=equity is not None and free_collateral is not None,
    )


def summarize_exposures(
    exposures: tuple[AccountExposure, ...],
) -> AggregateExposureTotals:
    """Sum exposures; equity/free collateral include COMPLETE accounts only."""
    complete = [e for e in exposures if e.complete]
    return AggregateExposureTotals(
        accounts=len(exposures),
        incomplete_accounts=len(exposures) - len(complete),
        total_equity=sum(e.equity for e in complete if e.equity is not None),
        total_free_collateral=sum(
            e.free_collateral for e in complete if e.free_collateral is not None
        ),
        total_open_markets=sum(e.open_market_count for e in exposures),
    )


# --------------------------------------------------------------------------- #
# Address enumeration (bot_instances → distinct (network, address) refs)
# --------------------------------------------------------------------------- #

_cached_refs: tuple[PortfolioAccountRef, ...] | None = None
_cached_at: float = 0.0


def reset_portfolio_account_cache() -> None:
    """Drop the cached address list (tests / forced reconfiguration)."""
    global _cached_refs, _cached_at
    _cached_refs = None
    _cached_at = 0.0


def extract_account_ref(record: Any) -> PortfolioAccountRef | None:
    """Best-effort ``(network, address)`` from one ``bot_instances`` row.

    Sealed configs are decrypted; undecryptable rows fall back to the raw
    payload (legacy plaintext rows keep readable addresses, sealed-but-broken
    rows yield none and are skipped). Returns ``None`` when no address is
    resolvable — the caller logs and moves on.
    """
    raw_config = getattr(record, "config", None)
    if isinstance(raw_config, dict):
        payload: dict[str, Any] = dict(raw_config)
    elif isinstance(raw_config, str):
        raw = raw_config.strip()
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if not isinstance(parsed, dict):
            return None
        payload = dict(parsed)
    else:
        return None

    try:
        payload = open_config_secrets(payload)
    except CredentialDecryptionError as exc:
        logger.warning(
            "portfolio_accounts: could not decrypt config for bot {} ({}); "
            "falling back to raw payload",
            getattr(record, "instance_id", "?"),
            exc,
        )

    address = str((payload.get("credentials") or {}).get("address") or "").strip()
    if not address:
        return None
    return PortfolioAccountRef(
        address=address, network=normalize_network(getattr(record, "network", None))
    )


def _load_account_refs_sync() -> tuple[PortfolioAccountRef, ...]:
    """Session-owning closure; run off the event loop via ``run_db``."""
    from internal.domain.models import Bot
    from src.infrastructure.database import db

    session = db.get_session()
    try:
        rows = session.query(Bot).all()
    finally:
        session.close()

    refs: set[PortfolioAccountRef] = set()
    for row in rows:
        ref = extract_account_ref(row)
        if ref is not None:
            refs.add(ref)
    ordered = tuple(sorted(refs, key=lambda r: (r.network, r.address)))
    if len(ordered) > BOT_PORTFOLIO_AGGREGATE_MAX_ACCOUNTS:
        logger.warning(
            "portfolio_accounts: {} distinct subaccounts exceed the cap {}; "
            "truncating deterministically (network, address order)",
            len(ordered),
            BOT_PORTFOLIO_AGGREGATE_MAX_ACCOUNTS,
        )
        ordered = ordered[:BOT_PORTFOLIO_AGGREGATE_MAX_ACCOUNTS]
    return ordered


async def enumerate_portfolio_accounts(
    *, force_refresh: bool = False
) -> tuple[PortfolioAccountRef, ...]:
    """Distinct ``(network, address)`` subaccounts across ``bot_instances``.

    Includes rows of every status — a stopped bot's positions still exist
    on-chain and belong in the exposure view. DB/decryption failures propagate
    (the DB is already a trading dependency); single-row decrypt failures are
    skipped inside :func:`extract_account_ref`.
    """
    global _cached_refs, _cached_at
    if (
        not force_refresh
        and _cached_refs is not None
        and (time.monotonic() - _cached_at) < BOT_PORTFOLIO_ACCOUNTS_CACHE_TTL_SECONDS
    ):
        return _cached_refs

    from src.infrastructure.db_offload import run_db

    refs = await run_db(_load_account_refs_sync)
    _cached_refs = refs
    _cached_at = time.monotonic()
    return refs


# --------------------------------------------------------------------------- #
# Exposure loaders (public per-address indexer reads)
# --------------------------------------------------------------------------- #


async def load_account_exposures_via_client(
    client: Any, refs: tuple[PortfolioAccountRef, ...]
) -> tuple[AccountExposure, ...]:
    """Read each ref's subaccount through the caller's indexer client.

    Guard-path loader: reads run concurrently through the ``dydx_indexer``
    circuit breaker; a 404 maps to a complete zero-exposure account; any other
    HTTP or circuit-breaker error propagates so the entry decision fails
    exactly like the worker's own account reads (fail-closed house style).
    """
    import httpx

    from src.exceptions import CircuitBreakerOpenError
    from src.infrastructure import resilience

    async def _read(ref: PortfolioAccountRef) -> AccountExposure:
        try:
            payload = await resilience.call_async(
                "dydx_indexer",
                lambda: client.indexer_account.account.get_subaccount(
                    ref.address, SUBACCOUNT_NUMBER
                ),
            )
        except (httpx.HTTPError, CircuitBreakerOpenError) as exc:
            if _is_http_404(exc):
                return AccountExposure(
                    address=ref.address,
                    network=ref.network,
                    equity=0.0,
                    free_collateral=0.0,
                    open_market_count=0,
                    complete=True,
                )
            raise
        return parse_account_exposure(ref, (payload or {}).get("subaccount"))

    return tuple(await asyncio.gather(*(_read(ref) for ref in refs)))


async def load_account_exposures_http(
    refs: tuple[PortfolioAccountRef, ...],
) -> tuple[AccountExposure, ...]:
    """Read each ref's subaccount via direct public indexer HTTP GETs.

    Monitoring-path loader: best-effort per account — an unreachable or
    malformed account degrades to an incomplete exposure (with ``error`` set)
    so the operator dashboard still renders the rest. Never raises for HTTP or
    circuit-breaker failures.
    """
    import httpx

    from src.exceptions import CircuitBreakerOpenError
    from src.infrastructure import resilience

    hosts = {
        _NETWORK_TESTNET: INDEXER_ENDPOINT_TESTNET,
        _NETWORK_MAINNET: INDEXER_ENDPOINT_MAINNET,
    }

    async def _read(
        http: httpx.AsyncClient, ref: PortfolioAccountRef
    ) -> AccountExposure:
        url = (
            f"{hosts[ref.network]}/v4/addresses/{ref.address}"
            f"/subaccountNumber/{SUBACCOUNT_NUMBER}"
        )
        try:
            response = await resilience.call_async(
                "dydx_indexer", lambda: http.get(url)
            )
            response.raise_for_status()
        except (httpx.HTTPError, CircuitBreakerOpenError) as exc:
            if _is_http_404(exc):
                return AccountExposure(
                    address=ref.address,
                    network=ref.network,
                    equity=0.0,
                    free_collateral=0.0,
                    open_market_count=0,
                    complete=True,
                )
            return AccountExposure(
                address=ref.address,
                network=ref.network,
                equity=None,
                free_collateral=None,
                open_market_count=0,
                complete=False,
                error=f"{type(exc).__name__}",
            )
        return parse_account_exposure(ref, (response.json() or {}).get("subaccount"))

    if not refs:
        return ()
    async with httpx.AsyncClient(
        timeout=BOT_PORTFOLIO_ACCOUNTS_HTTP_TIMEOUT_SECONDS
    ) as http:
        return tuple(await asyncio.gather(*(_read(http, ref) for ref in refs)))
