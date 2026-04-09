# Operations Guide

## Health Endpoints

### Backend

- `GET /health`
- `GET /ready`

### Bot

- `GET /health`
- `GET /ready`
- `GET /api/v1/capabilities`
- `GET /api/v1/runtime/db-config`

## Runtime Datastores

The local development baseline is intentionally split:

- backend uses the backend PostgreSQL instance on `5432`
- bot uses the bot-dedicated PostgreSQL instance on `5433`

This mirrors the production ownership model and avoids accidental shared-state coupling.

### Database ownership guardrails

- bot runtime supports cutover modes via `BOT_DB_CUTOVER_MODE`:
  - `shared`
  - `dedicated`
  - `dedicated_with_shared_fallback`
- in `dedicated` mode, startup now blocks if the bot target resolves to the same host/port/name as the shared backend DB target
- backend startup validates DB ownership and rejects dedicated-mode shared-target regressions
- backend `GET /health` and `GET /ready` include `database_ownership` diagnostics (mode, backend target, bot target, separation state, blocking flag)

### Dedicated cutover and rollback playbook

1. **Prepare dedicated bot DB target**
   - set `BOT_DATABASE_URL` (or `BOT_DB_*`) to the bot-owned PostgreSQL instance
   - keep backend `DB_*` / `DATABASE_URL` pointing at backend-owned DB
2. **Enable dedicated mode**
   - set `BOT_DB_CUTOVER_MODE=dedicated`
   - restart bot and backend
3. **Verify separation**
   - backend `GET /ready` returns `ready=true`
   - backend `database_ownership.separated=true`
   - bot `/api/v1/runtime/db-config` shows dedicated source and target metadata
4. **Rollback safely (if needed)**
   - switch bot to `BOT_DB_CUTOVER_MODE=dedicated_with_shared_fallback` for temporary fallback behavior
   - if full rollback is required, switch to `shared` and restart services
   - re-verify `GET /health` / `GET /ready` and runtime behavior after rollback

## Live Data Flow

### Backtests

- bot computes and persists backtest state
- backend proxies and normalizes the contract
- frontend subscribes via backend websocket channels and uses HTTP for bootstrap/recovery

### Strategy runtimes and bot stats

- bot emits runtime state
- backend proxies websocket/state surfaces
- frontend consumes backend-only live channels

## Troubleshooting

### Bot cannot start because port `5433` is unavailable

Start the dev infra:

```bash
make dev-infra
```

### Frontend is hitting the bot directly

Audit the frontend service code and ensure all origin helpers point to the backend origin, not `:8889`.

### Live views are stale

Check:

1. backend websocket proxy health
2. bot websocket emission
3. browser websocket connection in devtools
4. fallback HTTP recovery path

### Config drift

Regenerate `run.json`:

```bash
make dev
```

### Capital allocation and collateral guardrails (P1.6)

Bot runs perform strict collateral validation before each trade to prevent cascade failures:

#### Pre-launch capital checks (readiness preflight)

- **Minimum collateral**: Free collateral ≥ strategy's `usd_min_collateral` configuration
- **Per-trade size**: Free collateral ≥ strategy's `usd_per_trade` (minimum order size)
- **Safety buffer**: Recommends free collateral ≥ 1.25× (max of per-trade or minimum collateral)
- **Aggressive trade-size warning**: Alerts if per-trade is >10% of free collateral
- **Capital allocation check**: Warns if target allocation exceeds current free collateral

If any blocker fails, strategy launch is rejected. Warnings are shown to operator but do not block (e.g., buffer below 1.25× ratio, but above hard minimum).

#### Runtime trade execution guards

- **Before each trade**: Bot checks free collateral again (fetches live account state)
- **After trade**: Recalculates remaining buffer and ensures next trade won't breach minimum
- **Cascade prevention**: If remaining buffer would go below required threshold, halts trade execution
- **Subaccount isolation**: Warns if strategy uses subaccount >0 (confirm intentional capital segregation)

These guards ensure even if market conditions are extreme or positions move against the strategy, account will not be auto-liquidated due to collateral spam.

## Production Readiness Baseline

Before production rollout, validate:

- service-specific credentials are configured correctly
- backend and bot databases are separated
- readiness endpoints are green
- websocket channels are delivering live updates
- frontend is consuming backend-only routes
- strategy runtime preflight is passing for the selected environment
- live strategy launch always uses an explicit environment selection (`testnet` or `mainnet`)

### Live strategy launch environment safety

- backend `POST /api/v1/strategies/:id/start` requires an explicit `network` query (`testnet` or `mainnet`)
- backend rejects launch requests with missing/invalid environment selection before runtime startup
- frontend launch UX presents environment-specific risk messaging:
  - **mainnet**: elevated risk warning and real-funds caution
  - **testnet**: simulation guidance and clear non-production indication

### Runtime recovery and incident-safe behavior (P1.7)

Bot instances report their operational state via extended status indicators:

- **RUNNING**: Live and healthy; normal trade execution
- **RECOVERING**: Detected and recovering from process crash; state reconciliation in progress
- **DEGRADED**: Operational but with caution; heartbeat or other guardrails active
- **SAFEGUARDED**: Intentional incident-response mode; capital/position access locked pending operator review
- **ERROR**: Failed start or other terminal fault; can be restarted
- **STOPPED**: Operator-stopped or normal shutdown

#### Heartbeat and liveness monitoring

- Bot manager tracks `last_heartbeat` timestamp for each running instance
- Instances are automatically marked **DEGRADED** if heartbeat is stale >30 seconds
- Frontend observability shows heartbeat staleness and suggests operator action (restart, check logs)
- Backend reconciliation propagates heartbeat and recovery state from bot to strategy runtime view

#### Recovery playbook for dead workers

1. **Detect**: Bot manager monitor finds dead process (exit code != 0)
   - Instance transitions to **RECOVERING** state
   - Audit logs recorded with exit code and timestamp
2. **Reconcile**: Backend fetches runtime status; detects local/remote mismatch
   - If remote instance still exists: syncs and resumes if safe
   - If remote missing: rebuilds local record and offers to restart
3. **Verify**: Operator reviews diagnostics and decides:
   - Restart to recover (normal restart)
   - Force-recreate (if instance is stuck or stale)
   - Let operator investigate first (set to SAFEGUARDED and pause trades)
