# Operations Runbook

This runbook covers day-2 operations for the API-controlled multi-instance trading bot.

## Scope

- API process lifecycle
- Bot instance lifecycle
- Emergency actions
- Recovery after failures/restarts

## Prerequisites

- Project dependencies installed in `.venv`
- `.env` configured with network, DB, and notification values
- API reachable (`/health`)

## Standard startup sequence

1. Validate environment and safety defaults:
   - `IS_TESTNET=true` for staging/test
   - `BOT_PLACE_TRADES=false` for first validation pass
2. Start API server (venv interpreter).
3. Confirm API health and DB connectivity.
4. Create bot instance via API with explicit config.
5. Start instance and monitor logs/events.
6. Enable trading flags gradually (`manageExits` first, then `placeTrades`).

### API startup command (canonical)

- Canonical ASGI app: `src.api.server:app`
- Canonical launcher: `src/api/start_api.py`
- Backward-compatible launcher: `start_api.py` (root shim)

Example local starts (project `.venv`):

- Windows PowerShell: `.\\run_api.ps1`
- Unix shell: `./run_api.sh`
- Direct uvicorn: `.venv\\Scripts\\python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8889 --reload`

## Standard shutdown sequence

1. Disable new entries (`placeTrades=false`) if supported by active config path.
2. Stop the target instance through API (`stop_instance`).
3. Verify process is terminated and state persisted.
4. If needed, force stop and then reconcile open positions manually.

## Emergency stop procedure

Use this when behavior is unsafe, exchange state diverges, or repeated order failures occur.

1. Trigger instance stop with force mode.
2. Run/trigger `abort_all_positions` workflow for active account.
3. Verify open orders are zero.
4. Verify open positions are zero.
5. Capture logs and last known state files for incident review.

## Restart and recovery

After crash/redeploy:

1. Inspect `bot_states/instances.json`.
2. Inspect instance state files:
   - `bot_states/bot_agents_<instance_id>.json`
   - `bot_states/cointegrated_pairs_<instance_id>.json`
3. Compare local state against exchange state before resuming trading.
4. Start instance only after reconciliation is complete.

## Operational checks

- **Health**: `/health`, `/api/v1/system/status`
- **Process state**: instance status endpoints + PID/resource metadata
- **Trading state**: open orders/positions parity between exchange and local state
- **Alerting**: Telegram startup/error/shutdown message flow

## Backend ↔ Bot auth secret strategy

Use one of these explicit operating models and keep it consistent across environments:

1. **Shared JWT secret model (simple, internal deployments)**
   - Backend `JWT_SECRET_KEY` and bot `SECRET_KEY` are the same value.
   - Backend forwards user bearer token to bot delegated endpoints.
   - Pros: easiest for delegated auth parity.
   - Cons: tighter coupling between services; rotate both together.

2. **Service token model (recommended for stricter separation)**
   - Backend and bot use independent JWT secrets.
   - Backend calls bot with `BOT_API_TOKEN` (service credential) instead of user JWT reuse.
   - Set backend `BOT_API_USE_SERVICE_TOKEN=true` to prevent delegated routes from forwarding caller JWT upstream.
   - Bot validates service token explicitly on delegated HTTP/WebSocket paths.
   - Pros: least privilege and cleaner trust boundary.
   - Cons: requires explicit service-token lifecycle and rotation policy.

**Do not run mixed modes unintentionally.** If migrating between models, deploy backend and bot config changes atomically and verify delegated routes + websocket proxies before enabling trading.

### Service-token rotation policy (zero-downtime)

Use overlap windows to rotate without breaking delegated backend traffic:

1. Generate a new strong service token.
2. Set bot env:
   - `BOT_API_TOKEN=<new>`
   - `BOT_API_TOKEN_PREVIOUS=<old>`
3. Roll backend with `BOT_API_TOKEN=<new>`.
4. Verify delegated HTTP and WS smoke paths (`/api/v1/backtests/{run_id}/live`, `/ws/strategies`).
5. Remove `BOT_API_TOKEN_PREVIOUS` from bot env after verification.

Optional list-based rollout is supported with `BOT_API_TOKENS` (comma-separated), but prefer the explicit current/previous pair for operational clarity.

## Staging smoke commands (pre-release)

Run this sequence before release when using delegated websocket paths.

1. Ensure service-token model settings are active:
   - Backend: `BOT_API_TOKEN`, `BOT_API_USE_SERVICE_TOKEN=true`
   - Bot: `BOT_API_TOKEN` (and optional `BOT_API_TOKEN_PREVIOUS` during overlap)
2. Login to obtain a JWT access token from backend.
3. Validate websocket channels from backend origin:
   - Strategy channel: `/ws/strategies`
   - Delegated backtest channel: `/api/v1/backtests/{run_id}/live`

Example command flow (replace placeholders):

- `TOKEN=$(curl -s -X POST http://localhost:8888/api/v1/auth/login -H 'Content-Type: application/json' -d '{"username":"<user>","password":"<password>"}' | jq -r '.access_token // .data.access_token')`
- `wscat -c "ws://localhost:8888/ws/strategies?access_token=${TOKEN}"`
- `wscat -c "ws://localhost:8888/api/v1/backtests/<run_id>/live?access_token=${TOKEN}"`

Expected results:

- Strategy WS connects and receives handshake/ping-pong traffic without auth failures.
- Backtest live WS connects and streams progress events for active runs.

## Incident triage quick map

- Jurisdiction/access failure: see `docs/FAILURE_MODES.md` (FM-001)
- Exchange/local mismatch: see `docs/FAILURE_MODES.md` (FM-003)
- Backtest progress visibility gap: see `docs/FEATURE_STATUS.md`
- Auth/2FA placeholders: see `docs/FEATURE_STATUS.md`

## Post-incident checklist

- Record timeline, triggering condition, and impact window
- Save relevant logs and state-file snapshots
- Record operator actions taken
- Add remediation task + regression test if code fix is required
