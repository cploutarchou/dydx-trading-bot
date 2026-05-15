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

## Celery Monitoring

Celery task monitoring and management is documented in [Celery Operations](./CELERY_OPERATIONS.md).

- Admin UI: `/admin/celery` in the backoffice portal only
- Admin APIs: `GET /api/v1/celery/tasks`, `GET /api/v1/celery/workers`, `GET /api/v1/celery/queues`, `GET /api/v1/celery/health`
- Task actions: `POST /api/v1/celery/tasks/{task_id}/revoke`, `POST /api/v1/celery/tasks/{task_id}/retry`

These endpoints and UI surfaces are admin-only. Do not expose Celery task management, tracebacks, revoke, retry, queue, worker, or Flower access to normal users.

## Runtime Datastores

The local development baseline is intentionally split:

- backend uses the backend PostgreSQL instance on `5432`
- bot uses the bot-dedicated PostgreSQL instance on `5433`

This mirrors the production ownership model and avoids accidental shared-state coupling.

## Backtest Strategy Resolution

For bot backtest creation endpoints (`POST /api/v1/backtests`, `POST /api/v1/backtests/run`), strategy payload
resolution is intentionally ordered to reduce `strategy_not_found` drift during delegated backend execution:

1. Bot strategy table lookup by `strategy_id`
2. Most recent persisted backtest request snapshots in bot DB
3. Request-provided `strategy_payload_snapshot` (compatibility fallback)

If lookup falls to step 3, execution still proceeds, but operators should verify strategy replication/sync between
backend and bot persistence domains.

### Drift monitoring and strict mode

- `GET /api/v1/backtests/sync-health` now includes
   `strategy_resolution_metrics` with counters for `store`, `history`, `request`, and `not_found` paths.
- To disable request-payload strategy fallback in production, set:
   `BACKTEST_DISABLE_REQUEST_SNAPSHOT_FALLBACK_IN_PRODUCTION=true`
   (effective only when `ENVIRONMENT=production`).

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

- bot persists lifecycle status, supervised job state, runtime events, and backtest progress to the bot PostgreSQL DB
- bot emits runtime state over websocket as a best-effort notification path; websocket publish failures must not fail core jobs
- backend proxies websocket/state surfaces
- frontend consumes backend-only live channels

Plain-text files under `bot/bot_states/` are operational debug artifacts only. PostgreSQL is the recovery source for
runtime status and job/backtest progress.

Runtime worker configuration is also database-first: workers resolve per-instance settings from `bot_instances.config`
before consulting `bot_states/config_<instance_id>.yaml`. The YAML file remains a compatibility/debug cache and is
refreshed from DB payloads when available.

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

#### Startup auto-recovery controls

- Backtests: API startup reconciles stale orphaned persisted `pending`/`running` runs. Default mode marks them failed with an interruption message after `BACKTEST_AUTO_RECOVERY_MIN_AGE_SECONDS` (default: stale heartbeat threshold). Set `BACKTEST_AUTO_RECOVERY_MODE=restart` or `BACKTEST_AUTO_RECOVER=true` to requeue restartable stale runs with persisted request payloads.
- Live bots: API startup verifies active persisted live workers by attached process or recovered PID. Missing workers are marked **ERROR** by default. Set `BOT_AUTO_RECOVER_LIVE_RUNTIMES=true` to auto-restart missing testnet workers through `BotInstanceManager`.
- Mainnet: live auto-restart is blocked unless `BOT_AUTO_RECOVER_LIVE_MAINNET=true` is also set.

## Subscription Tiers and Feature Gating (P1.8)

The platform supports three subscription tiers with profit-share incentive alignment:

### Tier specifications

- **Explorer**: Entry tier, profit-share 2%, limited to 1 active strategy, standard backtest access
- **Performance**: Mid tier, profit-share 5%, up to 3 active strategies, advanced analytics included
- **Enterprise**: Premium tier, profit-share 10%, unlimited strategies, dedicated support, custom integrations

### Subscription lifecycle

- **Trial**: New users receive 14-day trial of Performance tier (all features, 0% profit-share)
- **Active**: Paid subscription or post-trial tier selection
- **Expired**: Subscription past renewal date; auto-reverts to Explorer tier
- **Canceled**: User-initiated cancellation; access restricted to Explorer features only

### Feature gating enforcement

- Backend handler `StartStrategyRuntime` validates user subscription tier before permitting strategy launch
- Feature gates check `subscription_tier` against tier-specific feature list in the database
- Expired subscriptions automatically cascade to Explorer tier (non-blocking for live positions, but blocks new strategy launches)
- Trial status and expiration tracked in user record; frontend shows clear trial countdown and upsell messaging

### Upgrade and renewal flows

- Frontend displays upgrade CTA in strategy creation and analytics pages
- Backend sends `subscription_expired` webhook event on renewal date miss (operators can configure external billing hooks)
- Subscription status visible in user account page with: current plan, renewal date, active strategy count vs. tier limit

## Terminal-Grade Tables and UI Controls (P1.10)

All data-intensive surfaces (Strategy Manager, Bot Manager, Backtest History) use a consistent, reusable table pattern library:

### TableControls component features

- **Density selector**: Toggle between `comfortable` (default), `compact`, and `dense` row spacing; density preference persisted to browser localStorage
- **Column filtering**: Per-column text filter inputs; filters live-update table without server round-trip (client-side for fast UX)
- **Pagination**: Five-button pattern (first, prev, next, last, current page indicator); configurable rows-per-page (10, 25, 50, 100)
- **CSV export**: Single click to download filtered/paginated table data as RFC 4180 CSV (handles comma-escaping and quoted fields)
- **Accessibility**: ARIA labels on filter inputs, proper header markup, keyboard-navigable pagination buttons

### Integration pattern

All table surfaces must import and compose `TableHeader`, `TableFilterRow`, and `PaginationControls` from `frontend/src/components/TableControls.tsx`:

```typescript
import { TableHeader, TableFilterRow, PaginationControls } from '@/components/TableControls';

// Within table body render:
<TableHeader title="Strategies" onExport={() => exportTableAsCSV(rows)} onDensityChange={setDensity} />
<TableFilterRow columns={['name', 'status', 'pnl']} onFilter={setFilters} />
<PaginationControls total={total} pageSize={pageSize} onPageChange={page => setPage(page)} />
```

### Data-table best practices

- Table headers use `font-semibold` and light gray background for visual hierarchy
- Row hover applies subtle background change (e.g., `bg-gray-50` on desktop)
- Filter inputs have placeholder text matching column name (e.g., "Filter by name")
- Export filename includes timestamp: `strategies_2025-01-20T15_30_45Z.csv`
- Pagination always shows: "Showing items X–Y of Z" for clarity on filtered data

## Platform Observability Baseline (P2.13)

The platform provides three-layer observability for live trading operations:

### Health and readiness endpoints

- `GET /health`: Liveness check with dependency snapshots
  - Returns `status=healthy` with live timestamp and service uptime
  - Includes database stats: open connections, in-use, idle, wait counts, closed connection metrics
  - Includes bot API health snapshot and bot recovery state
  - **Use for**: Liveness alerting, dashboards, infrastructure monitoring

- `GET /ready`: Readiness/graceful shutdown detection
  - Returns `status=ready` only if all hard requirements met (database ownership, bot connectivity)
  - Blocks deployment if database ownership is violated
  - Includes database ownership diagnostics and bot recovery metadata
  - **Use for**: Kubernetes readiness probes, canary validation, deployment gates

### Operational metrics endpoint

- `GET /metrics`: Per-service operational data for observability stacks
  - Database connection pool utilization: open, in-use, idle, max-idle-closed, max-lifetime-closed
  - Database wait stats: total wait count and accumulated wait duration
  - Bot API metrics snapshot (delegated from bot service)
  - Service version, environment, and uptime_seconds
  - **Use for**: Prometheus scrapes, Grafana dashboards, capacity planning

### Integration with monitoring and alerting

- Set up Prometheus scrape of `/metrics` every 15-30 seconds
- Alert on database connection pool saturation: `open_connections > 0.8 × pool_max`
- Alert on database wait spike: `wait_count_delta > 100` per minute
- Alert on service restart: `uptime_seconds < 60` (indicates recent crash)
- Forward bot API snapshots to distributed tracing system (Jaeger, DataDog) for latency analysis

### Observability for incident response

- On production incident, operators should check in this order:
  1. `GET /health` → verify dependencies and database stats
  2. `GET /ready` → confirm if safe to route traffic
  3. `GET /metrics` → inspect connection pool and bot API snapshot for resource exhaustion
  4. Backend logs (structured JSON) → trace request flow and error context
  5. Bot logs (structured JSON) → trace strategy execution and exchange connectivity issues
