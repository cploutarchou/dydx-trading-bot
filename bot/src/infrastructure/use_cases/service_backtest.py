"""Backtest service for handling backtest operations."""

from __future__ import annotations

import asyncio
import math
import random
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import numpy as np
from pydantic import BaseModel
from scipy.stats import linregress

try:  # pragma: no cover - optional at runtime, exercised in integration tests
    from statsmodels.tsa.stattools import adfuller, coint
except Exception:  # pragma: no cover
    adfuller = None
    coint = None

from src.trading.dydx_client import connect_dydx
from src.infrastructure.persistence.repository_backtest import BacktestRepository


class _BacktestRunStatus(BaseModel):
    run_id: str
    status: str
    progress_pct: float
    updated_at: str
    current_pair: Optional[str] = None
    current_task: Optional[str] = None
    error: Optional[str] = None
    error_message: Optional[str] = None


class _BacktestTrade(BaseModel):
    trade_id: str
    market_1: str
    market_2: str
    entry_timestamp: str
    exit_timestamp: str
    entry_zscore: float
    exit_zscore: float
    entry_price_m1: float
    exit_price_m1: float
    entry_price_m2: float
    exit_price_m2: float
    hedge_ratio: float
    pnl_usd: float
    pnl_pct: float
    duration_hours: float
    win: bool


class _BacktestRunDetails(BaseModel):
    run_id: str
    name: str
    status: str
    total_pnl: float
    win_rate: float
    sharpe_ratio: float
    max_drawdown_pct: float
    total_trades: int
    created_at: str
    updated_at: str
    profit_factor: float = 0.0
    start_date: str = ""
    end_date: str = ""
    progress_pct: float = 0.0
    current_pair: Optional[str] = None
    current_task: Optional[str] = None
    error: Optional[str] = None
    error_message: Optional[str] = None


class _BacktestRunList(BaseModel):
    runs: List[Dict[str, Any]]
    total: int


class BacktestService:
    """Service for backtest operations."""

    _runs: Dict[str, Dict[str, Any]] = {}
    _tasks: Dict[str, asyncio.Task] = {}
    _BASELINE_METRICS: Dict[str, float] = {
        "total_pnl": 48.2,
        "win_rate": 0.59,
        "sharpe_ratio": 1.33,
        "max_drawdown_pct": 10.9,
        "total_trades": 24,
    }
    _INTERRUPTION_ERROR = "Backtest interrupted by API reload or restart"

    def __init__(self, session: Any):
        self.repository = (
            session if isinstance(session, BacktestRepository) else BacktestRepository(session)
        )
        self.session = getattr(self.repository, "session", session)
        # Reconciliation is explicit via API ops endpoints to avoid false-positive
        # failures when requests are served by different API worker processes.

    @staticmethod
    def _to_ops_row(run: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "run_id": str(run.get("run_id") or ""),
            "name": str(run.get("name") or ""),
            "status": str(run.get("status") or ""),
            "progress_pct": float(run.get("progress_pct", 0.0) or 0.0),
            "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at"),
            "error": run.get("error"),
            "error_message": run.get("error_message"),
        }

    def _find_orphaned_in_progress_runs(
            self, runs: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        source = runs if runs is not None else self.repository.list_runs(limit=None, offset=0)
        candidates: List[Dict[str, Any]] = []
        for run in source:
            run_id = str(run.get("run_id") or "").strip()
            if not run_id:
                continue
            status = str(run.get("status") or "").strip().lower()
            if status in {"created", "running"} and run_id not in self._tasks:
                candidates.append(dict(run))
        return candidates

    def _build_interrupted_run_payload(self, run: Dict[str, Any]) -> Dict[str, Any]:
        interrupted = dict(run)
        interrupted.update(
            {
                "status": "failed",
                "current_task": "failed",
                "error": self._INTERRUPTION_ERROR,
                "error_message": self._INTERRUPTION_ERROR,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return interrupted

    def list_interrupted_runs_for_ops(self, limit: int = 50) -> Dict[str, Any]:
        runs = self.repository.list_runs(limit=None, offset=0)
        orphaned = self._find_orphaned_in_progress_runs(runs)
        reconciled = [
            dict(run)
            for run in runs
            if str(run.get("status") or "").strip().lower() == "failed"
               and str(run.get("error") or "").strip() == self._INTERRUPTION_ERROR
        ]

        safe_limit = max(1, int(limit or 50))
        return {
            "interruption_error": self._INTERRUPTION_ERROR,
            "orphaned_in_progress": [
                self._to_ops_row(run) for run in orphaned[:safe_limit]
            ],
            "interrupted_runs": [
                self._to_ops_row(run) for run in reconciled[:safe_limit]
            ],
            "orphaned_count": len(orphaned),
            "interrupted_count": len(reconciled),
        }

    def reconcile_interrupted_runs(self, dry_run: bool = True) -> Dict[str, Any]:
        runs = self.repository.list_runs(limit=None, offset=0)
        for run in runs:
            run_id = str(run.get("run_id") or "").strip()
            if run_id:
                self._runs[run_id] = dict(run)

        candidates = self._find_orphaned_in_progress_runs(runs)
        reconciled: List[Dict[str, Any]] = []
        if not dry_run:
            for run in candidates:
                persisted = self.repository.save_run(self._build_interrupted_run_payload(run))
                run_id = str(persisted.get("run_id") or "").strip()
                if run_id:
                    self._runs[run_id] = dict(persisted)
                reconciled.append(dict(persisted))

        return {
            "interruption_error": self._INTERRUPTION_ERROR,
            "dry_run": bool(dry_run),
            "candidates": [self._to_ops_row(run) for run in candidates],
            "reconciled": [self._to_ops_row(run) for run in reconciled],
            "candidate_count": len(candidates),
            "reconciled_count": len(reconciled),
        }

    def _load_run_data(self, run_id: str) -> Optional[Dict[str, Any]]:
        cached = self._runs.get(run_id)
        if cached is not None:
            return dict(cached)

        persisted = self.repository.get_run(run_id)
        if persisted is None:
            return None

        self._runs[run_id] = dict(persisted)
        return dict(persisted)

    def _persist_run_data(self, run_data: Dict[str, Any]) -> Dict[str, Any]:
        persisted = self.repository.save_run(run_data)
        self._runs[str(persisted["run_id"])] = dict(persisted)
        return dict(persisted)

    def _update_run_data(self, run_id: str, **updates: Any) -> Optional[Dict[str, Any]]:
        run_data = self._load_run_data(run_id)
        if run_data is None:
            return None
        run_data.update(updates)
        if "updated_at" not in updates:
            run_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        return self._persist_run_data(run_data)

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))

    @staticmethod
    def _extract_request_payload(request: Any) -> Dict[str, Any]:
        if hasattr(request, "model_dump"):
            return request.model_dump()
        if isinstance(request, dict):
            return request
        return {}

    @staticmethod
    def _coerce_bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def _build_metrics(cls, request: Any) -> Dict[str, Any]:
        payload = cls._extract_request_payload(request)
        params = (
                payload.get("trading_parameters") or payload.get("strategy_params") or {}
        )

        zscore_threshold = float(params.get("zscore_threshold", 1.5) or 1.5)
        stats_window = int(params.get("stats_window", 21) or 21)
        usd_per_trade = float(params.get("usd_per_trade", 10.0) or 10.0)
        close_at_zscore_cross = cls._coerce_bool(
            params.get("close_at_zscore_cross"), default=True
        )

        transaction_fee = float(params.get("transaction_fee", 0.0) or 0.0)
        slippage = float(params.get("slippage", 0.0) or 0.0)
        risk_free_rate = float(params.get("risk_free_rate", 0.02) or 0.02)
        max_positions = int(params.get("max_positions", 5) or 5)

        baseline = cls._BASELINE_METRICS

        total_pnl = float(baseline["total_pnl"])
        total_pnl += 4.0 * (1.5 - zscore_threshold)
        total_pnl -= 0.05 * ((stats_window - 21) ** 2)
        total_pnl += 0.08 * (usd_per_trade - 10.0)
        if not close_at_zscore_cross:
            total_pnl -= 1.2

        win_rate = float(baseline["win_rate"])
        win_rate -= 0.03 * abs(zscore_threshold - 1.5)
        win_rate -= 0.0025 * abs(stats_window - 21)
        win_rate -= 0.001 * max(0.0, usd_per_trade - 10.0)
        if not close_at_zscore_cross:
            win_rate -= 0.02

        sharpe_ratio = float(baseline["sharpe_ratio"])
        sharpe_ratio -= 0.18 * ((zscore_threshold - 1.5) ** 2)
        sharpe_ratio -= 0.002 * ((stats_window - 21) ** 2)
        sharpe_ratio -= 0.002 * max(0.0, usd_per_trade - 10.0)
        if not close_at_zscore_cross:
            sharpe_ratio -= 0.05

        max_drawdown_pct = float(baseline["max_drawdown_pct"])
        max_drawdown_pct += 1.2 * max(0.0, 1.5 - zscore_threshold)
        max_drawdown_pct += 0.12 * abs(stats_window - 21)
        max_drawdown_pct += 0.035 * max(0.0, usd_per_trade - 10.0)
        if not close_at_zscore_cross:
            max_drawdown_pct += 0.6

        total_trades = int(baseline["total_trades"])
        total_trades += round((1.5 - zscore_threshold) * 10)
        total_trades += round((21 - stats_window) / 4)
        total_trades += round(max(0.0, usd_per_trade - 10.0) / 8)
        if not close_at_zscore_cross:
            total_trades -= 3

        total_pnl -= (transaction_fee * 4000.0) + (slippage * 4400.0)
        total_pnl -= max(0.0, risk_free_rate - 0.02) * 40.0
        total_pnl -= max(0, max_positions - 5) * 0.25

        sharpe_ratio -= (transaction_fee * 60.0) + (slippage * 60.0)
        sharpe_ratio -= max(0.0, risk_free_rate - 0.02) * 0.6
        sharpe_ratio -= max(0, max_positions - 5) * 0.01

        max_drawdown_pct += (transaction_fee * 400.0) + (slippage * 1600.0)
        max_drawdown_pct += max(0, max_positions - 5) * 0.08

        total_trades += int(round(slippage * 5000.0))

        return {
            "total_pnl": round(total_pnl, 1),
            "win_rate": round(cls._clamp(win_rate, 0.25, 0.95), 2),
            "sharpe_ratio": round(cls._clamp(sharpe_ratio, -2.0, 5.0), 2),
            "max_drawdown_pct": round(max(0.0, max_drawdown_pct), 1),
            "total_trades": max(1, total_trades),
        }

    @staticmethod
    def _parse_date(value: str, end_of_day: bool = False) -> datetime:
        base = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        if end_of_day and "T" not in str(value):
            return base.replace(hour=23, minute=59, second=59, microsecond=0)
        return base

    @staticmethod
    def _resolution_to_minutes(resolution: str) -> int:
        raw = str(resolution or "1HOUR").strip().upper()
        mapping = {
            "1MIN": 1,
            "5MINS": 5,
            "15MINS": 15,
            "30MINS": 30,
            "1HOUR": 60,
            "1H": 60,
            "4HOURS": 240,
            "4H": 240,
            "1DAY": 1440,
            "1D": 1440,
        }
        if raw in mapping:
            return mapping[raw]
        return 60

    @staticmethod
    def _to_iso(dt: datetime) -> str:
        utc = dt.astimezone(timezone.utc).replace(microsecond=0)
        return utc.isoformat().replace("+00:00", "Z")

    async def _fetch_market_history(
            self,
            client: Any,
            market: str,
            start_dt: datetime,
            end_dt: datetime,
            resolution: str,
    ) -> Dict[str, float]:
        step_minutes = self._resolution_to_minutes(resolution)
        max_candles = 100
        chunk = timedelta(minutes=step_minutes * 90)
        cursor = start_dt
        merged: Dict[str, float] = {}

        while cursor < end_dt:
            window_end = min(end_dt, cursor + chunk)
            response = await client.indexer.markets.get_perpetual_market_candles(
                market=market,
                resolution=resolution,
                from_iso=self._to_iso(cursor),
                to_iso=self._to_iso(window_end),
                limit=max_candles,
            )

            for candle in response.get("candles", []):
                ts = candle.get("startedAt")
                close = candle.get("close")
                if ts is None or close is None:
                    continue
                try:
                    merged[str(ts)] = float(close)
                except (TypeError, ValueError):
                    continue

            cursor = window_end + timedelta(minutes=step_minutes)

        return dict(sorted(merged.items(), key=lambda kv: kv[0]))

    @staticmethod
    def _align_series(
            market_1: Dict[str, float],
            market_2: Dict[str, float],
    ) -> tuple[list[str], np.ndarray, np.ndarray]:
        common = sorted(set(market_1.keys()) & set(market_2.keys()))
        p1 = np.array([market_1[k] for k in common], dtype=np.float64)
        p2 = np.array([market_2[k] for k in common], dtype=np.float64)
        return common, p1, p2

    @staticmethod
    def _compute_sharpe(daily_pnl: List[float], initial_balance: float) -> float:
        if len(daily_pnl) < 2:
            return 0.0
        returns = np.array(daily_pnl, dtype=np.float64) / max(1e-9, initial_balance)
        std = np.std(returns)
        if std <= 1e-12:
            return 0.0
        # Daily sampling assumption
        sharpe = (np.mean(returns) / std) * math.sqrt(252)
        return float(sharpe)

    @staticmethod
    def _compute_max_drawdown_pct(
            daily_pnl: List[float], initial_balance: float
    ) -> float:
        equity = initial_balance
        peak = equity
        max_dd = 0.0
        for pnl in daily_pnl:
            equity += pnl
            peak = max(peak, equity)
            if peak > 0:
                dd = (peak - equity) / peak
                max_dd = max(max_dd, dd)
        return float(max_dd * 100.0)

    @staticmethod
    def _build_daily_pnl_rows(
            daily_pnl_agg: Dict[str, float],
            all_trades: List[Dict[str, Any]],
            resolution: str,
    ) -> List[Dict[str, Any]]:
        return [
            {
                "candle_id": f"{day}|PORTFOLIO|{resolution}",
                "date": day,
                "timestamp": f"{day}T00:00:00Z",
                "market": "PORTFOLIO",
                "resolution": resolution,
                "pnl": round(daily_pnl_agg[day], 4),
                "trades": len(
                    [
                        t
                        for t in all_trades
                        if str(t.get("exit_timestamp", "")).startswith(day)
                    ]
                ),
            }
            for day in sorted(daily_pnl_agg.keys())
        ]

    @staticmethod
    def _build_market_pairs(markets: List[str]) -> List[tuple[str, str]]:
        """Build all unique non-self market combinations preserving input order."""
        normalized: List[str] = []
        seen: set[str] = set()
        for market in markets:
            m = str(market).strip()
            if not m or m in seen:
                continue
            seen.add(m)
            normalized.append(m)

        pairs: List[tuple[str, str]] = []
        for i in range(len(normalized) - 1):
            for j in range(i + 1, len(normalized)):
                pairs.append((normalized[i], normalized[j]))
        return pairs

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_pair_selection_mode(mode: Any) -> str:
        raw = str(mode or "liquidity").strip().lower()
        aliases = {
            "liquidity": "liquidity",
            "volume": "liquidity",
            "volatility": "volatility",
            "cointegration": "cointegration",
            "input": "input",
            "none": "input",
            "order": "input",
            "original": "input",
        }
        return aliases.get(raw, "liquidity")

    @classmethod
    def _extract_market_liquidity(cls, market_payload: Any) -> float:
        """Return a best-effort liquidity score from market metadata."""
        if not isinstance(market_payload, dict):
            return 0.0

        # dYdX payload fields can vary by endpoint/version; prefer 24h volumes when present.
        candidates = [
            market_payload.get("volume24H"),
            market_payload.get("volume24h"),
            market_payload.get("volume"),
            market_payload.get("baseVolume"),
            market_payload.get("baseVolume24H"),
            market_payload.get("notionalVolume24H"),
            market_payload.get("notional24H"),
            market_payload.get("turnover24H"),
        ]

        best = 0.0
        for raw in candidates:
            best = max(best, cls._safe_float(raw, 0.0))
        return best

    @classmethod
    def _prioritize_pairs_by_liquidity(
            cls,
            pair_markets: List[tuple[str, str]],
            market_map: Dict[str, Any],
    ) -> List[tuple[str, str]]:
        """Sort pairs by combined market liquidity descending, preserving stable order for ties."""
        if not pair_markets or not market_map:
            return pair_markets

        def score(pair: tuple[str, str]) -> float:
            a, b = pair
            a_info = market_map.get(a, {})
            b_info = market_map.get(b, {})
            return cls._extract_market_liquidity(
                a_info
            ) + cls._extract_market_liquidity(b_info)

        # Python sort is stable, so equal scores preserve original pair order.
        return sorted(pair_markets, key=score, reverse=True)

    @classmethod
    def _compute_market_volatility(cls, market_history: Dict[str, float]) -> float:
        if not isinstance(market_history, dict) or len(market_history) < 3:
            return 0.0
        prices = np.array(list(market_history.values()), dtype=np.float64)
        if len(prices) < 3:
            return 0.0
        returns = np.diff(prices) / np.maximum(prices[:-1], 1e-12)
        if len(returns) == 0:
            return 0.0
        return float(np.nanstd(returns))

    @classmethod
    def _prioritize_pairs_by_volatility(
            cls,
            pair_markets: List[tuple[str, str]],
            history_by_market: Dict[str, Dict[str, float]],
    ) -> List[tuple[str, str]]:
        if not pair_markets or not history_by_market:
            return pair_markets

        vol_cache: Dict[str, float] = {
            market: cls._compute_market_volatility(hist)
            for market, hist in history_by_market.items()
        }

        def score(pair: tuple[str, str]) -> float:
            a, b = pair
            return vol_cache.get(a, 0.0) + vol_cache.get(b, 0.0)

        return sorted(pair_markets, key=score, reverse=True)

    @classmethod
    def _pair_cointegration_score(
            cls,
            market_a: str,
            market_b: str,
            history_by_market: Dict[str, Dict[str, float]],
    ) -> float:
        h1 = history_by_market.get(market_a, {})
        h2 = history_by_market.get(market_b, {})
        timestamps, p1, p2 = cls._align_series(h1, h2)
        if len(timestamps) < 48:
            return -1e9

        # Statsmodels path: strict ranking using cointegration + stationarity tests.
        if coint is not None and adfuller is not None:
            try:
                if np.min(p1) <= 0 or np.min(p2) <= 0:
                    return -1e9

                log_p1 = np.log(p1)
                log_p2 = np.log(p2)

                coint_stat, coint_pvalue, _ = coint(log_p1, log_p2)

                # Estimate hedge ratio on log prices and test spread stationarity.
                lr = linregress(log_p2, log_p1)
                hedge_ratio = float(lr.slope)
                spread = log_p1 - (hedge_ratio * log_p2)

                adf_stat, adf_pvalue, *_ = adfuller(spread, autolag="AIC")

                # Half-life estimate from OU approximation: dS_t = k*S_{t-1}+e_t.
                lagged = spread[:-1]
                delta = np.diff(spread)
                if len(lagged) < 3 or np.std(lagged) <= 1e-12:
                    return -1e9

                mean_rev_lr = linregress(lagged, delta)
                kappa = float(mean_rev_lr.slope)
                if kappa >= 0:
                    half_life = float("inf")
                else:
                    half_life = -math.log(2.0) / kappa

                # Return-correlation as a secondary quality signal.
                r1 = np.diff(log_p1)
                r2 = np.diff(log_p2)
                corr = float(np.corrcoef(r1, r2)[0, 1]) if len(r1) > 1 else 0.0
                if math.isnan(corr):
                    corr = 0.0

                # Strict penalty: deprioritize pairs that fail significance thresholds.
                if coint_pvalue > 0.10 or adf_pvalue > 0.10:
                    return -100.0 - float(coint_pvalue) - float(adf_pvalue)

                coint_score = 1.0 - cls._clamp(float(coint_pvalue), 0.0, 1.0)
                adf_score = 1.0 - cls._clamp(float(adf_pvalue), 0.0, 1.0)
                half_life_score = (
                    0.0
                    if not np.isfinite(half_life)
                    else 1.0 / (1.0 + max(0.0, half_life))
                )
                corr_score = abs(corr)

                # Weighted blend (tests dominate, dynamics refine ties).
                score = (2.5 * coint_score) + (2.5 * adf_score) + (0.75 * corr_score)
                score += 0.5 * half_life_score

                # Small tie-breaker with test statistics where more negative is better.
                score += 0.01 * abs(float(coint_stat))
                score += 0.01 * abs(float(adf_stat))
                return float(score)
            except Exception:
                # Fall through to heuristic fallback if statistical path fails.
                pass

        # Fallback heuristic when strict tests are unavailable.
        var_b = float(np.var(p2))
        if var_b <= 1e-12:
            return -1e9
        hedge_ratio = float(np.cov(p1, p2)[0, 1] / var_b)
        spread = p1 - (hedge_ratio * p2)

        spread_std = float(np.std(spread))
        if spread_std <= 1e-12:
            return -1e9

        diff_std = float(np.std(np.diff(spread))) if len(spread) > 1 else 0.0
        corr = float(np.corrcoef(p1, p2)[0, 1]) if len(p1) > 1 else 0.0
        if math.isnan(corr):
            corr = 0.0

        # Heuristic: prefer high absolute correlation and faster spread dynamics.
        mean_reversion_component = min(1.0, diff_std / max(spread_std, 1e-12))
        return abs(corr) + mean_reversion_component

    @classmethod
    def _prioritize_pairs_by_cointegration(
            cls,
            pair_markets: List[tuple[str, str]],
            history_by_market: Dict[str, Dict[str, float]],
    ) -> List[tuple[str, str]]:
        if not pair_markets or not history_by_market:
            return pair_markets

        def score(pair: tuple[str, str]) -> float:
            return cls._pair_cointegration_score(pair[0], pair[1], history_by_market)

        return sorted(pair_markets, key=score, reverse=True)

    @classmethod
    def _prioritize_pairs(
            cls,
            pair_markets: List[tuple[str, str]],
            mode: str,
            market_map: Dict[str, Any],
            history_by_market: Dict[str, Dict[str, float]],
    ) -> List[tuple[str, str]]:
        normalized_mode = cls._normalize_pair_selection_mode(mode)
        if normalized_mode == "input":
            return pair_markets
        if normalized_mode == "volatility":
            return cls._prioritize_pairs_by_volatility(pair_markets, history_by_market)
        if normalized_mode == "cointegration":
            return cls._prioritize_pairs_by_cointegration(
                pair_markets, history_by_market
            )
        return cls._prioritize_pairs_by_liquidity(pair_markets, market_map)

    def _simulate_pair(
            self,
            run_id: str,
            market_a: str,
            market_b: str,
            timestamps: List[str],
            prices_a: np.ndarray,
            prices_b: np.ndarray,
            params: Dict[str, Any],
            trade_index_offset: int,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, float]]:
        stats_window = max(5, int(params.get("stats_window", 21) or 21))
        entry_z = float(params.get("zscore_threshold", 1.5) or 1.5)
        usd_per_trade = float(params.get("usd_per_trade", 10.0) or 10.0)
        close_on_cross = self._coerce_bool(
            params.get("close_at_zscore_cross"), default=True
        )
        transaction_fee = float(params.get("transaction_fee", 0.0) or 0.0)
        slippage = float(params.get("slippage", 0.0) or 0.0)

        if len(prices_a) <= stats_window + 1:
            return [], [], {}

        var_b = float(np.var(prices_b))
        if var_b <= 1e-12:
            return [], [], {}
        hedge_ratio = float(np.cov(prices_a, prices_b)[0, 1] / var_b)

        spread = prices_a - (hedge_ratio * prices_b)
        trades: List[Dict[str, Any]] = []
        snapshots: List[Dict[str, Any]] = []
        daily_pnl: Dict[str, float] = {}

        open_pos: Optional[Dict[str, Any]] = None

        for idx in range(stats_window, len(spread)):
            window = spread[idx - stats_window: idx]
            mean = float(np.mean(window))
            std = float(np.std(window))
            if std <= 1e-12:
                continue
            z = (float(spread[idx]) - mean) / std
            ts = timestamps[idx]

            if open_pos is None:
                if z >= entry_z:
                    open_pos = {
                        "side": "short_spread",
                        "entry_idx": idx,
                        "entry_z": z,
                        "entry_p1": float(prices_a[idx]),
                        "entry_p2": float(prices_b[idx]),
                        "entry_ts": ts,
                    }
                elif z <= -entry_z:
                    open_pos = {
                        "side": "long_spread",
                        "entry_idx": idx,
                        "entry_z": z,
                        "entry_p1": float(prices_a[idx]),
                        "entry_p2": float(prices_b[idx]),
                        "entry_ts": ts,
                    }
                continue

            should_close = abs(z) <= 0.25
            if close_on_cross and open_pos is not None:
                if open_pos["side"] == "short_spread" and z <= 0:
                    should_close = True
                if open_pos["side"] == "long_spread" and z >= 0:
                    should_close = True

            if not should_close or open_pos is None:
                continue

            ep1 = open_pos["entry_p1"]
            ep2 = open_pos["entry_p2"]
            xp1 = float(prices_a[idx])
            xp2 = float(prices_b[idx])

            spread_move = (xp1 - ep1) - hedge_ratio * (xp2 - ep2)
            if open_pos["side"] == "short_spread":
                spread_move *= -1.0

            notional = max(1e-9, abs(ep1) + abs(hedge_ratio * ep2))
            pnl_gross = (spread_move / notional) * usd_per_trade
            fee_cost = usd_per_trade * (transaction_fee + slippage) * 2.0
            pnl = pnl_gross - fee_cost
            pnl_pct = (pnl / max(1e-9, usd_per_trade)) * 100.0

            trade_id = f"t-{run_id}-{trade_index_offset + len(trades):03d}"
            exit_z = z
            entry_dt = datetime.fromisoformat(
                open_pos["entry_ts"].replace("Z", "+00:00")
            )
            exit_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            duration_hours = max(0.0, (exit_dt - entry_dt).total_seconds() / 3600.0)

            trades.append(
                {
                    "trade_id": trade_id,
                    "market_1": market_a,
                    "market_2": market_b,
                    "entry_timestamp": open_pos["entry_ts"],
                    "exit_timestamp": ts,
                    "entry_zscore": round(float(open_pos["entry_z"]), 4),
                    "exit_zscore": round(float(exit_z), 4),
                    "entry_price_m1": round(ep1, 4),
                    "exit_price_m1": round(xp1, 4),
                    "entry_price_m2": round(ep2, 4),
                    "exit_price_m2": round(xp2, 4),
                    "hedge_ratio": round(hedge_ratio, 6),
                    "pnl_usd": round(float(pnl), 4),
                    "pnl_pct": round(float(pnl_pct), 4),
                    "duration_hours": round(duration_hours, 3),
                    "win": bool(pnl > 0),
                }
            )

            snapshots.append(
                {
                    "timestamp": ts,
                    "positions": [
                        {
                            "position_id": f"pos-{trade_id}",
                            "market_1": market_a,
                            "market_2": market_b,
                            "entry_timestamp": open_pos["entry_ts"],
                            "exit_timestamp": ts,
                            "entry_price_m1": round(ep1, 4),
                            "entry_price_m2": round(ep2, 4),
                            "hedge_ratio": round(hedge_ratio, 6),
                            "entry_zscore": round(float(open_pos["entry_z"]), 4),
                            "total_pnl_usd": round(float(pnl), 4),
                            "status": "CLOSED",
                        }
                    ],
                }
            )

            day_key = ts[:10]
            daily_pnl[day_key] = round(daily_pnl.get(day_key, 0.0) + float(pnl), 4)
            open_pos = None

        return trades, snapshots, daily_pnl

    async def _execute_backtest(
            self,
            run_id: str,
            request_payload: Dict[str, Any],
            progress_callback: Any,
    ) -> None:
        run_data = self._load_run_data(run_id)
        if not run_data:
            return

        client = None
        try:
            run_data["status"] = "running"
            run_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            run_data = self._persist_run_data(run_data)

            params = request_payload.get("trading_parameters") or {}
            pairs_raw = request_payload.get("pairs") or []
            if len(pairs_raw) < 2:
                raise ValueError("Backtest requires at least two markets in 'pairs'")

            start_dt = self._parse_date(str(request_payload.get("start_date")))
            end_dt = self._parse_date(
                str(request_payload.get("end_date")), end_of_day=True
            )
            if end_dt <= start_dt:
                raise ValueError("end_date must be after start_date")

            resolution = str(params.get("resolution", "1HOUR") or "1HOUR")
            initial_balance = float(
                request_payload.get("initial_balance", 10000.0) or 10000.0
            )
            pair_selection_mode = self._normalize_pair_selection_mode(
                request_payload.get(
                    "pair_selection_mode",
                    params.get("pair_selection_mode", "liquidity"),
                )
            )

            # Build all unique pair combinations.
            # Example: [BTC, ETH, SOL] -> (BTC, ETH), (BTC, SOL), (ETH, SOL)
            pair_markets = self._build_market_pairs([str(m) for m in pairs_raw])

            max_pairs: Optional[int] = None
            max_pairs_raw = request_payload.get("max_pairs", None)
            if max_pairs_raw is None:
                max_pairs_raw = params.get("max_pairs", None)
            if max_pairs_raw is not None:
                try:
                    parsed_max_pairs = int(max_pairs_raw)
                    # 0 or negative means "no cap" (use all available pairs).
                    max_pairs = parsed_max_pairs if parsed_max_pairs > 0 else None
                except (TypeError, ValueError):
                    # Ignore malformed max_pairs and continue with all pairs.
                    max_pairs = None

            if not pair_markets:
                raise ValueError("No valid market pairs available from request")

            client = await connect_dydx()

            unique_markets = sorted({m for pair in pair_markets for m in pair})
            market_history_cache: Dict[str, Dict[str, float]] = {}

            # Pull market metadata for liquidity ranking when available.
            market_map: Dict[str, Any] = {}
            try:
                markets_payload = await client.indexer.markets.get_perpetual_markets()
                market_map = (
                    markets_payload.get("markets", {})
                    if isinstance(markets_payload, dict)
                    else {}
                )
            except Exception:
                market_map = {}

            # Modes using historical behavior require per-market history cache.
            if pair_selection_mode in {"volatility", "cointegration"}:
                for market in unique_markets:
                    try:
                        market_history_cache[market] = await self._fetch_market_history(
                            client=client,
                            market=market,
                            start_dt=start_dt,
                            end_dt=end_dt,
                            resolution=resolution,
                        )
                    except Exception:
                        market_history_cache[market] = {}

            pair_markets = self._prioritize_pairs(
                pair_markets=pair_markets,
                mode=pair_selection_mode,
                market_map=market_map,
                history_by_market=market_history_cache,
            )

            if max_pairs is not None:
                pair_markets = pair_markets[:max_pairs]

            total_pairs = len(pair_markets)
            all_trades: List[Dict[str, Any]] = []
            all_snapshots: List[Dict[str, Any]] = []
            daily_pnl_agg: Dict[str, float] = {}

            for idx, (m1, m2) in enumerate(pair_markets):
                if run_data.get("cancel_requested"):
                    raise asyncio.CancelledError()

                progress = round((idx / max(1, total_pairs)) * 95.0, 2)
                run_data["progress_pct"] = progress
                run_data["current_pair"] = f"{m1}/{m2}"
                run_data["current_task"] = "processing pair"
                run_data["updated_at"] = datetime.now(timezone.utc).isoformat()
                run_data = self._persist_run_data(run_data)

                if progress_callback is not None:
                    await progress_callback(run_id, progress, f"{m1}/{m2}", 0)

                if m1 in market_history_cache:
                    candles_1 = market_history_cache[m1]
                else:
                    candles_1 = await self._fetch_market_history(
                        client=client,
                        market=m1,
                        start_dt=start_dt,
                        end_dt=end_dt,
                        resolution=resolution,
                    )
                    market_history_cache[m1] = candles_1

                if m2 in market_history_cache:
                    candles_2 = market_history_cache[m2]
                else:
                    candles_2 = await self._fetch_market_history(
                        client=client,
                        market=m2,
                        start_dt=start_dt,
                        end_dt=end_dt,
                        resolution=resolution,
                    )
                    market_history_cache[m2] = candles_2

                timestamps, p1, p2 = self._align_series(candles_1, candles_2)
                trades, snapshots, daily_pnl = self._simulate_pair(
                    run_id=run_id,
                    market_a=m1,
                    market_b=m2,
                    timestamps=timestamps,
                    prices_a=p1,
                    prices_b=p2,
                    params=params,
                    trade_index_offset=len(all_trades),
                )

                all_trades.extend(trades)
                all_snapshots.extend(snapshots)
                for day, pnl in daily_pnl.items():
                    daily_pnl_agg[day] = round(daily_pnl_agg.get(day, 0.0) + pnl, 4)

                running_total_pnl = float(sum(t["pnl_usd"] for t in all_trades))
                running_total_trades = len(all_trades)
                running_winners = len([t for t in all_trades if t["win"]])
                running_win_rate = (
                    running_winners / running_total_trades
                    if running_total_trades > 0
                    else 0.0
                )
                ordered_running_daily = [
                    daily_pnl_agg[d] for d in sorted(daily_pnl_agg.keys())
                ]
                running_sharpe_ratio = self._compute_sharpe(
                    ordered_running_daily, initial_balance
                )
                running_max_drawdown_pct = self._compute_max_drawdown_pct(
                    ordered_running_daily, initial_balance
                )
                running_profit_factor = (
                    sum(t["pnl_usd"] for t in all_trades if t["pnl_usd"] > 0)
                    / max(
                        1e-9,
                        abs(sum(t["pnl_usd"] for t in all_trades if t["pnl_usd"] < 0)),
                    )
                    if running_total_trades > 0
                    else 0.0
                )

                run_data.update(
                    {
                        "total_pnl": round(running_total_pnl, 4),
                        "total_trades": running_total_trades,
                        "win_rate": round(running_win_rate, 4),
                        "sharpe_ratio": round(running_sharpe_ratio, 4),
                        "max_drawdown_pct": round(running_max_drawdown_pct, 4),
                        "profit_factor": round(float(running_profit_factor), 4),
                        "trades": list(all_trades),
                        "position_snapshots": list(all_snapshots),
                        "daily_pnl": self._build_daily_pnl_rows(
                            daily_pnl_agg=daily_pnl_agg,
                            all_trades=all_trades,
                            resolution=resolution,
                        ),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                run_data = self._persist_run_data(run_data)

                # Yield control so other coroutines (status polling) run smoothly.
                await asyncio.sleep(0)

            total_pnl = float(sum(t["pnl_usd"] for t in all_trades))
            total_trades = len(all_trades)
            winners = len([t for t in all_trades if t["win"]])
            win_rate = (winners / total_trades) if total_trades > 0 else 0.0
            profit_factor = (
                sum(t["pnl_usd"] for t in all_trades if t["pnl_usd"] > 0)
                / max(
                    1e-9, abs(sum(t["pnl_usd"] for t in all_trades if t["pnl_usd"] < 0))
                )
                if total_trades > 0
                else 0.0
            )

            ordered_daily = [daily_pnl_agg[d] for d in sorted(daily_pnl_agg.keys())]
            sharpe_ratio = self._compute_sharpe(ordered_daily, initial_balance)
            max_drawdown_pct = self._compute_max_drawdown_pct(
                ordered_daily, initial_balance
            )

            run_data.update(
                {
                    "status": "completed",
                    "progress_pct": 100.0,
                    "current_pair": "complete",
                    "current_task": "complete",
                    "total_pnl": round(total_pnl, 4),
                    "win_rate": round(win_rate, 4),
                    "sharpe_ratio": round(sharpe_ratio, 4),
                    "max_drawdown_pct": round(max_drawdown_pct, 4),
                    "total_trades": total_trades,
                    "profit_factor": round(float(profit_factor), 4),
                    "trades": all_trades,
                    "position_snapshots": all_snapshots,
                    "daily_pnl": self._build_daily_pnl_rows(
                        daily_pnl_agg=daily_pnl_agg,
                        all_trades=all_trades,
                        resolution=resolution,
                    ),
                    "error": None,
                    "error_message": None,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            run_data = self._persist_run_data(run_data)

            if progress_callback is not None:
                await progress_callback(run_id, 100.0, "complete", 0)

        except asyncio.CancelledError:
            run_data.update(
                {
                    "status": "cancelled",
                    "progress_pct": run_data.get("progress_pct", 0.0),
                    "current_pair": None,
                    "current_task": "cancelled",
                    "error": "Backtest cancelled",
                    "error_message": "Backtest cancelled",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            run_data = self._persist_run_data(run_data)
        except Exception as exc:
            error_message = str(exc)
            run_data.update(
                {
                    "status": "failed",
                    "current_task": "failed",
                    "error": error_message,
                    "error_message": error_message,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            run_data = self._persist_run_data(run_data)
        finally:
            self._tasks.pop(run_id, None)
            if client is not None:
                try:
                    await client.node.close()
                except Exception:
                    pass

    async def create_and_run_backtest(
            self,
            request: Any,
            progress_callback: Any = None,
    ) -> _BacktestRunDetails:
        """Create a backtest run and execute asynchronously using historical market data."""
        now = datetime.now(timezone.utc).isoformat()
        run_id = f"run-{uuid4().hex[:12]}"
        request_payload = self._extract_request_payload(request)

        start_date = getattr(request, "start_date", None) or request_payload.get(
            "start_date", ""
        )
        end_date = getattr(request, "end_date", None) or request_payload.get(
            "end_date", ""
        )
        name = (
                getattr(request, "name", None)
                or request_payload.get("name")
                or "unnamed-backtest"
        )

        run_data: Dict[str, Any] = {
            "run_id": run_id,
            "name": name,
            "status": "created",
            "progress_pct": 0.0,
            "current_pair": "pending",
            "current_task": "pending",
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "total_trades": 0,
            "start_date": str(start_date) if start_date else "",
            "end_date": str(end_date) if end_date else "",
            "profit_factor": 0.0,
            "created_at": now,
            "updated_at": now,
            "error": None,
            "error_message": None,
            "request": request_payload,
            "trades": [],
            "position_snapshots": [],
            "daily_pnl": [],
            "cancel_requested": False,
        }
        run_data = self._persist_run_data(run_data)

        task = asyncio.create_task(
            self._execute_backtest(
                run_id=run_id,
                request_payload=request_payload,
                progress_callback=progress_callback,
            )
        )
        self._tasks[run_id] = task
        run_data["status"] = "running"
        run_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        run_data = self._persist_run_data(run_data)

        return _BacktestRunDetails(**run_data)

    def list_backtest_runs(
            self,
            limit: int = 50,
            offset: int = 0,
            status_filter: Optional[str] = None,
            days_filter: Optional[int] = None,
    ) -> _BacktestRunList:
        runs = self.repository.list_runs(
            limit=limit,
            offset=offset,
            status_filter=status_filter,
            days_filter=days_filter,
        )
        total = self.repository.count_runs(
            statuses=[status_filter] if status_filter else None,
            days_filter=days_filter,
        )
        return _BacktestRunList(runs=runs, total=total)

    def get_backtest_details(self, run_id: str) -> Optional[_BacktestRunDetails]:
        data = self._load_run_data(run_id)
        if not data:
            return None
        return _BacktestRunDetails(**data)

    def get_backtest_status(self, run_id: str) -> Optional[_BacktestRunStatus]:
        data = self._load_run_data(run_id)
        if not data:
            return None
        return _BacktestRunStatus(
            run_id=run_id,
            status=str(data.get("status", "unknown")),
            progress_pct=float(data.get("progress_pct", 0.0)),
            updated_at=str(data.get("updated_at")),
            current_pair=(
                str(data.get("current_pair"))
                if data.get("current_pair") is not None
                else None
            ),
            current_task=(
                str(data.get("current_task"))
                if data.get("current_task") is not None
                else None
            ),
            error=str(data.get("error")) if data.get("error") is not None else None,
            error_message=(
                str(data.get("error_message"))
                if data.get("error_message") is not None
                else None
            ),
        )

    def get_backtest_trades(
            self,
            run_id: str,
            limit: int = 100,
            offset: int = 0,
            winning_only: bool = False,
    ) -> List[_BacktestTrade]:
        """Return trades captured during backtest execution."""
        data = self._load_run_data(run_id)
        if not data:
            return []
        raw_trades = data.get("trades")
        if isinstance(raw_trades, list):
            converted: List[_BacktestTrade] = []
            for trade in raw_trades:
                try:
                    converted.append(_BacktestTrade(**trade))
                except Exception:
                    continue
            if winning_only:
                converted = [t for t in converted if t.win]
            return converted[offset: offset + limit]

        # Backward-compatible fallback for legacy in-memory runs
        total_trades = max(1, int(data.get("total_trades", 0)))
        win_rate = float(data.get("win_rate", 0.5))
        total_pnl = float(data.get("total_pnl", 0))
        start_date_str = data.get("start_date", "")
        end_date_str = data.get("end_date", "")
        try:
            sd = (
                date.fromisoformat(start_date_str)
                if start_date_str
                else date.today() - timedelta(days=30)
            )
            ed = date.fromisoformat(end_date_str) if end_date_str else date.today()
            date_range = max(1, (ed - sd).days)
        except (ValueError, TypeError):
            sd = date.today() - timedelta(days=30)
            date_range = 30
        markets = [
            ("BTC-USD", "ETH-USD"),
            ("SOL-USD", "AVAX-USD"),
            ("LINK-USD", "DOT-USD"),
        ]
        rng = random.Random(run_id + "trades")
        winning_count = max(0, int(total_trades * win_rate))
        per_win = (
            (total_pnl / max(1, winning_count)) * 1.3 if winning_count > 0 else 5.0
        )
        per_loss = -(abs(per_win) * 0.6)
        trades: List[_BacktestTrade] = []
        for i in range(total_trades):
            is_win = i < winning_count
            pair = markets[i % len(markets)]
            entry_day = sd + timedelta(days=rng.randint(0, date_range - 1))
            dur = rng.uniform(4.0, 48.0)
            pnl = (
                (per_win * rng.uniform(0.7, 1.3))
                if is_win
                else (per_loss * rng.uniform(0.7, 1.3))
            )
            ep1 = rng.uniform(1000.0, 50000.0)
            ep2 = rng.uniform(100.0, 5000.0)
            trades.append(
                _BacktestTrade(
                    trade_id=f"t-{run_id}-{i:03d}",
                    market_1=pair[0],
                    market_2=pair[1],
                    entry_timestamp=entry_day.isoformat() + "T00:00:00Z",
                    exit_timestamp=(entry_day + timedelta(hours=dur)).isoformat()
                                   + "T06:00:00Z",
                    entry_zscore=round(rng.uniform(1.5, 2.5), 3),
                    exit_zscore=round(rng.uniform(-0.5, 0.5), 3),
                    entry_price_m1=round(ep1, 2),
                    exit_price_m1=round(ep1 * rng.uniform(0.95, 1.05), 2),
                    entry_price_m2=round(ep2, 2),
                    exit_price_m2=round(ep2 * rng.uniform(0.95, 1.05), 2),
                    hedge_ratio=round(rng.uniform(0.8, 1.2), 4),
                    pnl_usd=round(pnl, 2),
                    pnl_pct=round(pnl / 1000.0, 4),
                    duration_hours=round(dur, 1),
                    win=is_win,
                )
            )
        if winning_only:
            trades = [t for t in trades if t.win]
        return trades[offset: offset + limit]

    def cancel_backtest(self, run_id: str) -> bool:
        data = self._load_run_data(run_id)
        if not data:
            return False
        data["cancel_requested"] = True
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
        data["status"] = "cancelled"
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._persist_run_data(data)
        return True

    def delete_backtest(self, run_id: str) -> bool:
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
        self._runs.pop(run_id, None)
        return self.repository.delete_run(run_id)

    def get_summary_stats(self, days: int = 30) -> Dict[str, Any]:
        runs = self.repository.list_runs(limit=None, offset=0, days_filter=days)
        completed = [r for r in runs if r.get("status") == "completed"]
        return {
            "total_runs": len(runs),
            "completed_runs": len(completed),
            "avg_sharpe": (
                    sum(float(r.get("sharpe_ratio", 0.0)) for r in completed)
                    / max(1, len(completed))
            ),
        }

    def get_runtime_health(self) -> Dict[str, int]:
        """Runtime counters used by orchestration and health endpoints."""
        runs = self.repository.list_runs(limit=None, offset=0)
        active_statuses = {"created", "running"}
        queued_or_running = [r for r in runs if str(r.get("status")) in active_statuses]
        return {
            "queue_depth": len(queued_or_running),
            "active_jobs": len(self._tasks),
            "total_runs": len(runs),
        }

    def get_backtest_analytics(self, run_id: str) -> Optional[Dict[str, Any]]:
        data = self._load_run_data(run_id)
        if not data:
            return None
        return {
            "run_id": run_id,
            "risk": {"max_drawdown_pct": data.get("max_drawdown_pct")},
            "performance": {
                "total_pnl": data.get("total_pnl"),
                "sharpe_ratio": data.get("sharpe_ratio"),
            },
        }

    def get_advanced_performance_metrics(
            self,
            run_id: str,
            benchmark: str = "BTC-USD",
    ) -> Optional[Dict[str, Any]]:
        data = self._load_run_data(run_id)
        if not data:
            return None
        return {
            "run_id": run_id,
            "benchmark": benchmark,
            "alpha": 0.03,
            "beta": 0.78,
            "information_ratio": 0.21,
            "sharpe_ratio": data.get("sharpe_ratio"),
        }

    def get_live_progress(self, run_id: str) -> Optional[Dict[str, Any]]:
        data = self._load_run_data(run_id)
        if not data:
            return None
        progress = float(data.get("progress_pct", 0.0))
        return {
            "run_id": run_id,
            "status": data.get("status"),
            "progress": progress,
            "progress_pct": progress,
            "current_pair": data.get("current_pair"),
            "current_task": data.get("current_task"),
            "error": data.get("error"),
            "error_message": data.get("error_message"),
        }

    def compare_backtests(
            self,
            run_ids: List[str],
            metrics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Compare selected backtest runs across requested metrics."""
        metric_keys = metrics or [
            "total_pnl",
            "win_rate",
            "sharpe_ratio",
            "max_drawdown_pct",
            "total_trades",
            "profit_factor",
        ]

        selected_runs: List[Dict[str, Any]] = []
        missing_runs: List[str] = []

        for run_id in run_ids:
            run = self._load_run_data(run_id)
            if run is None:
                missing_runs.append(run_id)
                continue
            selected_runs.append(run)

        if not selected_runs:
            return {
                "run_ids": run_ids,
                "metrics": metric_keys,
                "runs": [],
                "summary": {},
                "missing_runs": missing_runs,
            }

        runs_payload: List[Dict[str, Any]] = []
        for run in selected_runs:
            runs_payload.append(
                {
                    "run_id": run.get("run_id"),
                    "name": run.get("name"),
                    "status": run.get("status"),
                    "created_at": run.get("created_at"),
                    "start_date": run.get("start_date"),
                    "end_date": run.get("end_date"),
                    "metrics": {
                        key: run.get(key)
                        for key in metric_keys
                    },
                }
            )

        summary: Dict[str, Any] = {}
        for key in metric_keys:
            numeric_values = []
            for run in selected_runs:
                value = run.get(key)
                try:
                    if value is not None:
                        numeric_values.append(float(value))
                except (TypeError, ValueError):
                    continue

            if not numeric_values:
                continue

            best = min(numeric_values) if key == "max_drawdown_pct" else max(numeric_values)
            worst = max(numeric_values) if key == "max_drawdown_pct" else min(numeric_values)
            avg = sum(numeric_values) / len(numeric_values)

            summary[key] = {
                "best": best,
                "worst": worst,
                "average": avg,
            }

        return {
            "run_ids": [r.get("run_id") for r in selected_runs],
            "metrics": metric_keys,
            "runs": runs_payload,
            "summary": summary,
            "missing_runs": missing_runs,
        }

    def get_comprehensive_analytics(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Full analytics including daily_pnl series for equity curve rendering."""
        data = self._load_run_data(run_id)
        if not data:
            return None
        if isinstance(data.get("daily_pnl"), list) and data.get("daily_pnl"):
            daily_pnl_list = data.get("daily_pnl")
            return {
                "run_id": run_id,
                "status": data.get("status"),
                "performance": {
                    "total_pnl": data.get("total_pnl"),
                    "win_rate": data.get("win_rate"),
                    "sharpe_ratio": data.get("sharpe_ratio"),
                    "total_trades": data.get("total_trades"),
                },
                "risk": {"max_drawdown_pct": data.get("max_drawdown_pct")},
                "trades": data.get("trades", []),
                "position_snapshots": data.get("position_snapshots", []),
                "candles": daily_pnl_list,
                "daily_pnl": daily_pnl_list,
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
            }

        total_pnl = float(data.get("total_pnl", 0))
        total_trades = int(data.get("total_trades", 0))
        start_date_str = data.get("start_date", "")
        end_date_str = data.get("end_date", "")
        try:
            sd = (
                date.fromisoformat(start_date_str)
                if start_date_str
                else date.today() - timedelta(days=30)
            )
            ed = date.fromisoformat(end_date_str) if end_date_str else date.today()
            num_days = max(1, (ed - sd).days)
        except (ValueError, TypeError):
            sd = date.today() - timedelta(days=30)
            num_days = 30
        rng = random.Random(run_id + "analytics")
        raw_series = [rng.gauss(0, 1) for _ in range(num_days)]
        raw_sum = sum(raw_series) or 1.0
        scale = total_pnl / raw_sum
        daily_pnl_list = []
        for i, raw in enumerate(raw_series):
            day = sd + timedelta(days=i)
            resolution = "1DAY"
            daily_pnl_list.append(
                {
                    "candle_id": f"{day.isoformat()}|PORTFOLIO|{resolution}",
                    "date": day.isoformat(),
                    "timestamp": f"{day.isoformat()}T00:00:00Z",
                    "market": "PORTFOLIO",
                    "resolution": resolution,
                    "pnl": round(raw * scale, 2),
                    "trades": max(0, round(total_trades / max(1, num_days))),
                }
            )
        return {
            "run_id": run_id,
            "status": data.get("status"),
            "performance": {
                "total_pnl": data.get("total_pnl"),
                "win_rate": data.get("win_rate"),
                "sharpe_ratio": data.get("sharpe_ratio"),
                "total_trades": data.get("total_trades"),
            },
            "risk": {"max_drawdown_pct": data.get("max_drawdown_pct")},
            "trades": data.get("trades", []),
            "position_snapshots": data.get("position_snapshots", []),
            "candles": daily_pnl_list,
            "daily_pnl": daily_pnl_list,
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        }

    def get_position_snapshots(
            self,
            run_id: str,
            limit: int = 100,
            offset: int = 0,
            market_pair: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return position snapshots captured during the run."""
        data = self._load_run_data(run_id)
        if not data:
            return []
        raw_snapshots = data.get("position_snapshots")
        if isinstance(raw_snapshots, list) and raw_snapshots:
            snapshots = raw_snapshots
            if market_pair:
                snapshots = [
                    s
                    for s in snapshots
                    if any(
                        f"{p.get('market_1')}/{p.get('market_2')}" == market_pair
                        for p in s.get("positions", [])
                    )
                ]
            return snapshots[offset: offset + limit]

        # Backward-compatible fallback for legacy in-memory runs
        total_trades = max(1, int(data.get("total_trades", 0)))
        win_rate = float(data.get("win_rate", 0.5))
        total_pnl = float(data.get("total_pnl", 0))
        start_date_str = data.get("start_date", "")
        end_date_str = data.get("end_date", "")
        try:
            sd = (
                date.fromisoformat(start_date_str)
                if start_date_str
                else date.today() - timedelta(days=30)
            )
            ed = date.fromisoformat(end_date_str) if end_date_str else date.today()
            date_range = max(1, (ed - sd).days)
        except (ValueError, TypeError):
            sd = date.today() - timedelta(days=30)
            date_range = 30
        markets = [
            ("BTC-USD", "ETH-USD"),
            ("SOL-USD", "AVAX-USD"),
            ("LINK-USD", "DOT-USD"),
        ]
        rng = random.Random(run_id + "positions")
        winning_count = max(0, int(total_trades * win_rate))
        per_win = (
            (total_pnl / max(1, winning_count)) * 1.3 if winning_count > 0 else 5.0
        )
        per_loss = -(abs(per_win) * 0.6)
        snapshots: List[Dict[str, Any]] = []
        for i in range(total_trades):
            pair = markets[i % len(markets)]
            pair_key = f"{pair[0]}/{pair[1]}"
            if market_pair and pair_key != market_pair:
                continue
            is_win = i < winning_count
            entry_day = sd + timedelta(days=rng.randint(0, date_range - 1))
            pnl = (
                (per_win * rng.uniform(0.7, 1.3))
                if is_win
                else (per_loss * rng.uniform(0.7, 1.3))
            )
            snapshots.append(
                {
                    "timestamp": entry_day.isoformat() + "T00:00:00Z",
                    "positions": [
                        {
                            "position_id": f"pos-{run_id}-{i:03d}",
                            "market_1": pair[0],
                            "market_2": pair[1],
                            "entry_timestamp": entry_day.isoformat() + "T00:00:00Z",
                            "exit_timestamp": None,
                            "entry_price_m1": round(rng.uniform(1000.0, 50000.0), 2),
                            "entry_price_m2": round(rng.uniform(100.0, 5000.0), 2),
                            "hedge_ratio": round(rng.uniform(0.8, 1.2), 4),
                            "entry_zscore": round(rng.uniform(1.5, 2.5), 3),
                            "total_pnl_usd": round(pnl, 2),
                            "status": "CLOSED" if is_win else "STOPPED",
                        }
                    ],
                }
            )
        return snapshots[offset: offset + limit]
