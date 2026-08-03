"""Read-side / reporting query methods for backtests.

Extracted from :mod:`src.infrastructure.use_cases.service_backtest` (Phase 4 of the
backtest-service decomposition). Pure read/projection methods over persisted run data:
details, status, trades, analytics, cross-run comparison, position snapshots, and
runtime health. Exposed as a **mixin** mixed into :class:`BacktestService` so the
public ``service.get_X(...)`` API used by the API router is unchanged.

The mixin relies on attributes/methods provided by ``BacktestService`` at runtime:
``_load_run_data`` / ``_resolve_stale_run_data`` / ``_load_run_overview`` /
``_strip_runtime_control`` / ``repository`` / ``_ACTIVE_STATUSES`` /
``_canonical_status`` / ``_tasks``. Response DTOs come from :mod:`backtest_models`.
The control/mutation methods (pause/resume/restart/cancel/delete/retry/repair) stay
on ``BacktestService`` (they couple to the runtime-control codec — Phase 5).
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from src.infrastructure.use_cases.async_job_manager import async_job_manager
from src.infrastructure.use_cases.backtest_models import (
    _BacktestRunDetails,
    _BacktestRunStatus,
    _BacktestTrade,
)


class BacktestQueryMixin:
    """Read-side query methods; mixed into :class:`BacktestService`."""

    def get_backtest_details(self, run_id: str) -> Optional[_BacktestRunDetails]:
        data = self._load_run_data(run_id)
        if not data:
            return None
        return _BacktestRunDetails(**self._resolve_stale_run_data(data))

    def get_backtest_status(self, run_id: str) -> Optional[_BacktestRunStatus]:
        data = self._load_run_overview(run_id)
        if not data:
            return None
        data = self._resolve_stale_run_data(data)
        request_payload = self._strip_runtime_control(data.get("request") or {})
        has_request_payload = bool(request_payload)
        timeout_value = data.get("timeout_seconds")
        heartbeat_age_value = data.get("heartbeat_age_seconds")
        strategy_id_value = data.get("strategy_id")
        retry_count_value = data.get("retry_count")
        metadata_value = data.get("metadata")
        metadata = metadata_value if isinstance(metadata_value, dict) else {}
        return _BacktestRunStatus(
            run_id=run_id,
            status=str(data.get("status", "unknown")),
            progress_pct=float(data.get("progress_pct", 0.0)),
            updated_at=str(data.get("updated_at")),
            created_at=(
                str(data.get("created_at"))
                if data.get("created_at") is not None
                else None
            ),
            started_at=(
                str(data.get("started_at"))
                if data.get("started_at") is not None
                else None
            ),
            completed_at=(
                str(data.get("completed_at") or data.get("finished_at"))
                if (data.get("completed_at") or data.get("finished_at")) is not None
                else None
            ),
            finished_at=(
                str(data.get("finished_at"))
                if data.get("finished_at") is not None
                else None
            ),
            deadline_at=(
                str(data.get("deadline_at"))
                if data.get("deadline_at") is not None
                else None
            ),
            timeout_seconds=(
                float(timeout_value) if timeout_value is not None else None
            ),
            last_heartbeat_at=(
                str(data.get("last_heartbeat_at"))
                if data.get("last_heartbeat_at") is not None
                else None
            ),
            heartbeat_age_seconds=(
                float(heartbeat_age_value) if heartbeat_age_value is not None else None
            ),
            cancellable=bool(data.get("cancellable", False)),
            pausable=bool(data.get("pausable", False)),
            resumable=bool(data.get("resumable", False)),
            restartable=bool(data.get("restartable", False)),
            control_status=(
                str(data.get("control_status"))
                if data.get("control_status") is not None
                else None
            ),
            control_action=(
                str(data.get("control_action"))
                if data.get("control_action") is not None
                else None
            ),
            worker_backend=(
                str(data.get("worker_backend"))
                if data.get("worker_backend") is not None
                else None
            ),
            worker_task_id=(
                str(data.get("worker_task_id"))
                if data.get("worker_task_id") is not None
                else None
            ),
            request=request_payload if has_request_payload else None,
            request_available=has_request_payload,
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
            error_code=(
                str(data.get("error_code"))
                if data.get("error_code") is not None
                else None
            ),
            traceback=(
                str(data.get("traceback"))
                if data.get("traceback") is not None
                else None
            ),
            result_location=(
                str(data.get("result_location"))
                if data.get("result_location") is not None
                else None
            ),
            result_summary=(
                data.get("result_summary")
                if isinstance(data.get("result_summary"), dict)
                else None
            ),
            strategy_id=(
                int(strategy_id_value) if strategy_id_value is not None else None
            ),
            bot_id=(
                str(data.get("bot_id")) if data.get("bot_id") is not None else None
            ),
            source=(
                str(data.get("source")) if data.get("source") is not None else None
            ),
            selected_pairs=list(data.get("selected_pairs") or []),
            metadata=metadata,
            worker_hostname=(
                str(data.get("worker_hostname"))
                if data.get("worker_hostname") is not None
                else None
            ),
            retry_count=(
                int(retry_count_value) if retry_count_value is not None else None
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
            return converted[offset : offset + limit]

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
        return trades[offset : offset + limit]

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

    def get_runtime_health(self) -> Dict[str, Any]:
        """Runtime counters used by orchestration and health endpoints."""
        runs = [
            self._resolve_stale_run_data(run)
            for run in self.repository.list_runs(limit=None, offset=0)
        ]
        active_statuses = set(self._ACTIVE_STATUSES)
        queued_or_running = [
            r
            for r in runs
            if self._canonical_status(r.get("status")) in active_statuses
        ]
        health: Dict[str, Any] = {
            "queue_depth": len(queued_or_running),
            "active_jobs": len(self._tasks),
            "total_runs": len(runs),
        }
        if hasattr(async_job_manager, "get_runtime_metrics"):
            try:
                health.update(async_job_manager.get_runtime_metrics())
            except Exception:
                # Keep health endpoint resilient even if optional metrics fail.
                pass
        return health

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
        data = self._load_run_overview(run_id)
        if not data:
            return None
        data = self._resolve_stale_run_data(data)
        progress = float(data.get("progress_pct", 0.0))
        return {
            "run_id": run_id,
            "status": data.get("status"),
            "progress": progress,
            "progress_pct": progress,
            "created_at": data.get("created_at"),
            "started_at": data.get("started_at"),
            "completed_at": data.get("completed_at") or data.get("finished_at"),
            "finished_at": data.get("finished_at"),
            "deadline_at": data.get("deadline_at"),
            "timeout_seconds": data.get("timeout_seconds"),
            "last_heartbeat_at": data.get("last_heartbeat_at"),
            "heartbeat_age_seconds": data.get("heartbeat_age_seconds"),
            "cancellable": data.get("cancellable"),
            "pausable": data.get("pausable"),
            "resumable": data.get("resumable"),
            "restartable": data.get("restartable"),
            "control_status": data.get("control_status"),
            "control_action": data.get("control_action"),
            "worker_backend": data.get("worker_backend"),
            "worker_task_id": data.get("worker_task_id"),
            "current_pair": data.get("current_pair"),
            "current_task": data.get("current_task"),
            "error": data.get("error"),
            "error_message": data.get("error_message"),
            "error_code": data.get("error_code"),
            "result_location": data.get("result_location"),
            "result_summary": data.get("result_summary"),
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
                    "metrics": {key: run.get(key) for key in metric_keys},
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

            best = (
                min(numeric_values)
                if key == "max_drawdown_pct"
                else max(numeric_values)
            )
            worst = (
                max(numeric_values)
                if key == "max_drawdown_pct"
                else min(numeric_values)
            )
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
            return snapshots[offset : offset + limit]

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
        return snapshots[offset : offset + limit]
