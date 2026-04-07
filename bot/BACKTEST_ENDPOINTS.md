# Backtest API Endpoints and Payloads

This file is an operator-friendly reference for all backtest endpoints currently exposed by `src/api/server.py`.

## Standard Response Envelope

All HTTP endpoints return the standard API envelope:

```json
{
  "success": true,
  "message": "Human-readable message",
  "data": {}
}
```

Error responses use the same envelope with `success=false` and may omit `data`.

## Endpoint Reference

### 1) Create and start backtest

- **Method/Path**: `POST /api/v1/backtests`
- **Body**: `BacktestConfigRequest` or compatibility `BacktestRunRequestCompat`

Example body:

```json
{
  "name": "manual-backtest",
  "description": "Manual backtest run",
  "start_date": "2026-03-01",
  "end_date": "2026-03-31",
  "initial_balance": 10000,
  "pair_selection_mode": "manual",
  "max_pairs": 10,
  "pairs": ["BTC-USD", "ETH-USD"],
  "trading_parameters": {
    "zscore_threshold": 1.5,
    "stats_window": 21,
    "usd_per_trade": 10.0,
    "close_at_zscore_cross": true
  }
}
```

Example `data` payload:

```json
{
  "run_id": "run-123",
  "name": "manual-backtest",
  "status": "created",
  "progress_pct": 0.0
}
```

### 2) Compatibility run route

- **Method/Path**: `POST /api/v1/backtests/run`
- **Body**: `BacktestRunRequestCompat`
- **Response aliases**: includes `progress` and `count`

Example `data` payload:

```json
{
  "run_id": "run-123",
  "name": "manual-backtest",
  "status": "queued",
  "progress_pct": 0.0,
  "progress": 0.0,
  "count": 1
}
```

### 3) List backtests

- **Method/Path**: `GET /api/v1/backtests`
- **Query params**: `limit`, `offset`, `status`, `days`
- **Response aliases**: includes both `runs` and `backtests`

Example `data` payload:

```json
{
  "runs": [{ "run_id": "run-1", "status": "completed", "progress_pct": 100.0 }],
  "backtests": [{ "run_id": "run-1", "status": "completed", "progress_pct": 100.0 }],
  "total": 1,
  "count": 1
}
```

### 4) List interrupted/orphaned runs (ops visibility)

- **Method/Path**: `GET /api/v1/backtests/interrupted`
- **Query params**: `limit` (default `50`)

Example `data` payload:

```json
{
  "interruption_error": "Backtest interrupted by API reload or restart",
  "orphaned_in_progress": [
    { "run_id": "run-orphaned", "status": "running", "error": null }
  ],
  "interrupted_runs": [
    {
      "run_id": "run-interrupted",
      "status": "failed",
      "error": "Backtest interrupted by API reload or restart"
    }
  ],
  "orphaned_count": 1,
  "interrupted_count": 1,
  "count": 2
}
```

### 5) Reconcile interrupted/orphaned runs

- **Method/Path**: `POST /api/v1/backtests/interrupted/reconcile`
- **Query params**: `dry_run` (default `true`)

Example `data` payload:

```json
{
  "interruption_error": "Backtest interrupted by API reload or restart",
  "dry_run": true,
  "candidates": [{ "run_id": "run-orphaned", "status": "running" }],
  "reconciled": [],
  "candidate_count": 1,
  "reconciled_count": 0,
  "count": 1
}
```

### 6) Admin alias: list interrupted/orphaned runs

- **Method/Path**: `GET /api/v1/admin/backtests/interrupted`
- **Auth**: admin user required (`get_admin_user`)
- **Query params**: `limit` (default `50`)
- **Response payload**: same as `GET /api/v1/backtests/interrupted`

### 7) Admin alias: reconcile interrupted/orphaned runs

- **Method/Path**: `POST /api/v1/admin/backtests/interrupted/reconcile`
- **Auth**: admin user required (`get_admin_user`)
- **Query params**: `dry_run` (default `true`)
- **Response payload**: same as `POST /api/v1/backtests/interrupted/reconcile`

### 8) Backtest details

- **Method/Path**: `GET /api/v1/backtests/{run_id}`

Example `data` payload:

```json
{
  "run_id": "run-123",
  "name": "manual-backtest",
  "status": "completed"
}
```

### 9) Backtest status

- **Method/Path**: `GET /api/v1/backtests/{run_id}/status`
- **Response aliases**: includes `progress` and `count`

Example `data` payload:

```json
{
  "run_id": "run-123",
  "status": "running",
  "progress_pct": 42.5,
  "progress": 42.5,
  "updated_at": "2026-01-01T00:00:00+00:00",
  "count": 1
}
```

### 10) Create strategy from backtest

- **Method/Path**: `POST /api/v1/backtests/{run_id}/create-strategy`
- **Body**: `BacktestCreateStrategyRequest`

Example body:

```json
{
  "name": "strategy-from-backtest",
  "description": "Derived from run-123",
  "config": {
    "entry_z": 1.8,
    "exit_z": 0.5
  }
}
```

### 11) Backtest trades

- **Method/Path**: `GET /api/v1/backtests/{run_id}/trades`
- **Query params**: `limit`, `offset`, `winning_only`

Example `data` payload:

```json
{
  "run_id": "run-123",
  "trades": [
    { "trade_id": "t-1", "market_1": "BTC-USD", "market_2": "ETH-USD" }
  ],
  "total": 1,
  "count": 1
}
```

### 12) Cancel backtest

- **Method/Path**: `POST /api/v1/backtests/{run_id}/cancel`

### 13) Delete backtest

- **Method/Path**: `DELETE /api/v1/backtests/{run_id}`

### 14) Backtest summary stats

- **Method/Path**: `GET /api/v1/backtests/stats/summary`
- **Query params**: `days`

### 15) Backtest analytics

- **Method/Path**: `GET /api/v1/backtests/{run_id}/analytics`

### 16) Position snapshots

- **Method/Path**: `GET /api/v1/backtests/{run_id}/position-snapshots`
- **Query params**: `limit`, `offset`, `market_pair`
- **Response aliases**: includes both `snapshots` and `position_snapshots`

### 17) Compare backtests

- **Method/Path**: `POST /api/v1/backtests/compare`

Example body:

```json
{
  "run_ids": ["run-1", "run-2"],
  "metrics": ["total_return_pct", "sharpe_ratio", "win_rate"]
}
```

### 18) Sync health

- **Method/Path**: `GET /api/v1/backtests/sync-health`

Example `data` payload:

```json
{
  "status": "ok",
  "queue_depth": 2,
  "active_jobs": 1,
  "total_runs": 5
}
```

### 19) dYdX validation

- **Method/Path**: `GET /api/v1/backtests/{run_id}/dydx-validation`

### 20) Performance metrics

- **Method/Path**: `GET /api/v1/backtests/{run_id}/performance-metrics`
- **Query params**: `benchmark` (default `BTC-USD`)

### 21) Live progress snapshot

- **Method/Path**: `GET /api/v1/backtests/{run_id}/live-progress`

### 22) Live websocket stream

- **Method/Path**: `WS /api/v1/backtests/{run_id}/live`
- **Use**: Subscribe to live progress messages while a run is executing.

## Persistence Note

Backtest runtime polling state (`/status`, interrupted reconciliation, runtime health) is persisted in the `backtest_runtime_runs` table.
Legacy analytics/backtest history tables may still exist separately (for example `backtest_runs`) and can have a different schema/purpose.

