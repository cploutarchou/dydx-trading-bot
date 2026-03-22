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
