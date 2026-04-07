# Bot API Parity Matrix (Backend -> Bot)

This matrix maps bot runtime capabilities into command/query/event surfaces so backend integrations can use bot as the canonical control plane.

## Commands (state-changing HTTP)

| Capability | Endpoint(s) | Status |
| --- | --- | --- |
| Create bot instance | `POST /api/v1/bots` | complete |
| Start bot instance | `POST /api/v1/bots/{instance_id}/start` | complete |
| Stop bot instance | `POST /api/v1/bots/{instance_id}/stop` | complete |
| Restart bot instance | `POST /api/v1/bots/{instance_id}/restart` | complete |
| Delete bot instance | `DELETE /api/v1/bots/{instance_id}` | complete |
| Quick deploy flow | `POST /api/v1/bots/quick-deploy` | complete |
| Create and run backtest | `POST /api/v1/backtests` | complete |
| Compatibility backtest run | `POST /api/v1/backtests/run` | complete |
| Cancel backtest | `POST /api/v1/backtests/{run_id}/cancel` | complete |
| Delete backtest | `DELETE /api/v1/backtests/{run_id}` | complete |
| Compare backtests | `POST /api/v1/backtests/compare` | complete |
| Reconcile interrupted backtests | `POST /api/v1/backtests/interrupted/reconcile` | complete |
| Admin reconcile interrupted backtests | `POST /api/v1/admin/backtests/interrupted/reconcile` | complete |

## Queries (read-only HTTP)

| Capability | Endpoint(s) | Status |
| --- | --- | --- |
| List bot instances | `GET /api/v1/bots` | complete |
| Get bot instance | `GET /api/v1/bots/{instance_id}` | complete |
| Bot history/jobs/trades/stats | `GET /api/v1/bots/{instance_id}/history`, `.../jobs`, `.../trades`, `.../stats` | complete |
| Current positions / position details | `GET /api/v1/bots/{bot_instance_id}/positions/current`, `.../positions/{position_id}` | complete |
| Market/stats/alerts snapshots | `GET /api/v1/bots/{bot_instance_id}/market-data`, `.../realtime-stats`, `.../alerts` | complete |
| Position history timeseries | `GET /api/v1/bots/{bot_instance_id}/position-history/{position_id}` | complete |
| Backtest list/details/status | `GET /api/v1/backtests`, `.../{run_id}`, `.../{run_id}/status` | complete |
| Backtest trades/analytics/snapshots | `GET /api/v1/backtests/{run_id}/trades`, `.../analytics`, `.../position-snapshots` | complete |
| Backtest validation/perf/live | `GET /api/v1/backtests/{run_id}/dydx-validation`, `.../performance-metrics`, `.../live-progress` | complete |
| Backtest summary and runtime health | `GET /api/v1/backtests/stats/summary`, `/api/v1/backtests/sync-health` | complete |
| Interrupted run reports | `GET /api/v1/backtests/interrupted`, `GET /api/v1/admin/backtests/interrupted` | complete |
| Runtime capability discovery | `GET /api/v1/capabilities` | complete |

## Events (websocket channels)

| Capability | Channel(s) | Status |
| --- | --- | --- |
| Strategy lifecycle snapshots/updates | `WS /ws/strategies` | complete |
| Bot runtime stream (positions/market/alerts) | `WS /api/v1/bots/{bot_instance_id}/positions/live`, `.../market/live`, `.../alerts/live` | complete |
| Bot runtime alias for backend consumers | `WS /ws/bots/{bot_instance_id}` | complete |
| Backtest progress stream | `WS /api/v1/backtests/{run_id}/live` | complete |
| Backtest progress alias for backend consumers | `WS /ws/backtests/{run_id}` | complete |

## Integration Rule

Backend should treat this bot API/WS surface as the canonical interface and avoid direct process/database manipulation outside the bot service boundary.

