# Backend Handoff Checklist (Production Rollout)

Use this checklist for backend -> bot integration go-live sign-off.
Scope: production rollout checks only.

## 1) Preconditions

- [ ] Backend uses bot as the only runtime control plane (no direct bot DB/process access).
- [ ] Backend has valid bearer token path for bot HTTP and websocket auth.
- [ ] Trace propagation is enabled (`X-Trace-Id` on outbound backend calls).

## 2) Required Readiness Gates

- [ ] `GET /ready` returns HTTP `200`.
- [ ] `GET /api/v1/capabilities` returns expected command/query/event surfaces.
- [ ] `GET /api/v1/runtime/db-config` (admin) confirms expected DB mode/source.

Minimal verification commands:

```bash
BOT_API_BASE="http://localhost:8889"
BOT_TOKEN="<token>"

curl -sS "${BOT_API_BASE}/ready"
curl -sS -H "Authorization: Bearer ${BOT_TOKEN}" "${BOT_API_BASE}/api/v1/capabilities"
curl -sS -H "Authorization: Bearer ${BOT_TOKEN}" "${BOT_API_BASE}/api/v1/runtime/db-config"
```

## 3) Contract and Trace Checks

- [ ] Standard response envelope is present (`success`, `message`, `data`, `trace_id`).
- [ ] `X-Trace-Id` response header is present and correlates with request trace.
- [ ] Error responses are sanitized (no internal SQL/stack leakage).

## 4) WebSocket Runtime Checks

- [ ] `WS /ws/strategies` connects and receives `strategy_status_snapshot`.
- [ ] `WS /ws/bots/{bot_instance_id}` connects for active bot instance streams.
- [ ] `WS /ws/backtests/{run_id}` connects for active backtest progress streams.
- [ ] Unauthorized websocket attempts fail closed with code `4401`.

## 5) Recovery and Reconciliation Checks

- [ ] Backend can recover from missed WS events by reconciling from HTTP snapshots.
- [ ] Backtest status polling works via `GET /api/v1/backtests/{run_id}/status` after API reload.
- [ ] Interrupted run visibility/reconciliation validated:
  - `GET /api/v1/backtests/interrupted`
  - `POST /api/v1/backtests/interrupted/reconcile?dry_run=true`

## 6) Go / No-Go Decision

- [ ] All required gates above passed.
- [ ] No unresolved severity-1/severity-2 integration defects.
- [ ] Rollback path verified (switch backend traffic away from bot or revert deployment).

## 7) Sign-Off

- Backend owner:
- Bot owner:
- Environment:
- Date/time (UTC):
- Evidence links (logs/dashboards/tickets):
- Decision: `GO` / `NO-GO`

## References

- `BACKEND_BOT_INTEGRATION.md`
- `BOT_SERVICE_ENDPOINTS.md`
- `API_CONTRACT.md`
- `PRODUCTION_READINESS.md`
- `openapi.json`

