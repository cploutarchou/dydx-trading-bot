---
name: portfolio-risk-burn-in
description: Run and extend the dYdX bot's live portfolio-risk guard burn-in harness. Use whenever the user mentions portfolio risk controls, BOT_PORTFOLIO_RISK_ENABLED, the account-level entry guard (src/trading/portfolio_risk.py), portfolio Phase B, burn-in evidence, false-denial checks before enabling/flipping risk controls, the monitoring endpoint /api/v1/monitoring/portfolio-risk, or wants to validate the guard against real dYdX subaccount data.
---

# Portfolio-risk guard burn-in

`scripts/portfolio_risk_burn_in.py` (wrapped by `make portfolio-burn-in`) runs
repeated live evaluations of the guard's decision against every distinct
subaccount configured in `bot_instances` — the same public per-address indexer
reads the monitoring endpoint uses, so **no signing credentials are needed**
for foreign accounts. It is the tool that produced the Phase B flip evidence
(2026-08-17) and the one to re-run before any future default-limit change.

## Running it

```bash
cd bot
make portfolio-burn-in     # starts shared infra, then 20 cycles x 3s
# knobs: PORTFOLIO_BURN_IN_CYCLES / PORTFOLIO_BURN_IN_INTERVAL / PORTFOLIO_BURN_IN_OUT
# or directly:
.venv/bin/python scripts/portfolio_risk_burn_in.py --cycles 20 --interval-seconds 3 \
    --json-out bot_states/portfolio_risk_burn_in.json
```

Requirements: shared infra up (Postgres with the runtime DB migrated — the
harness reads `bot_instances` through the app's own `db` seam, so the DB
ownership guardrail applies: do NOT point `BOT_DATABASE_URL` at the shared
`dydx_bot` DB) and at least one `bot_instances` row whose
`config.credentials.address` is set. A row with an address that has NO
subaccount is valid — it exercises the 404 → complete-zero-exposure branch.

## What it asserts (and why each matters)

- **No cycle errors** — enumeration (DB + credential decryption) and the
  public indexer reads must succeed every cycle; a flaky data path means the
  fail-closed guard would deny live entries.
- **No `portfolio_data_unavailable` observations** — incomplete/malformed
  reads are exactly the false-denial class the burn-in exists to catch.
- **Limit denials are reported, not failed** — denying an over-limit account
  (`portfolio_max_open_markets`, `portfolio_margin_utilization`,
  `portfolio_non_positive_equity` on a genuinely empty account, aggregate
  caps) is the guard working; only the operator decides whether to raise the
  limit. Pass/fail therefore measures the DATA PATH, not the account's balance.
- **Decision stability** (`decision_changes`) — same account state must yield
  the same decision across cycles.
- **Peak ratchet** — when equity is present the harness folds it into the
  Redis peak store (live Valkey, Celery-broker DB); with a drawdown/daily-loss
  limit configured those checks evaluate against it.

Exit codes: 0 = clean burn-in, 1 = failed (read the summary), 2 = no accounts
configured. Evidence JSON includes the full per-cycle log — that file is the
flip/change evidence; reference its summary numbers in
`docs/bot-risk-control-matrix.md`.

## Good burn-in targets

Any real dYdX address works for the read path (v4 indexer account reads are
public). The dYdX docs' example subaccount
(`dydx14zzueazeh0hj67cghhf9jypslcf9sh2n5k6art`, TESTNET) is funded and holds
live perpetual positions — it exercises real equity strings and the per-market
notional parser (`parse_open_positions_notional`). Pair it with a fresh
never-traded address to cover the 404 → zero-exposure branch.

## Invariants to preserve when editing

- The harness evaluates the guard's PURE core (`evaluate_portfolio_entry` /
  `evaluate_aggregate_entry`) with limits rebuilt from
  `portfolio_risk_config()` — keep that seam public and faithful; never
  re-derive limits from raw env vars here.
- `scripts/` is not a package: tests import it via `importlib`
  (`tests/test_portfolio_burn_in.py`), and the module must stay import-safe —
  `load_repo_env` happens inside `main()` (AGENTS.md rule 1), never at import.
- In-process tests are hermetic: the conftest autouse `_isolate_portfolio_guard`
  fixture pins `portfolio_risk.BOT_PORTFOLIO_RISK_ENABLED` off (the shipped
  default is ON since Phase B); guard tests enable it explicitly via
  `monkeypatch.setattr` — their patch takes precedence.

## When touching the guard in production code

Run, in order: `tests/test_portfolio_risk.py` + `tests/test_portfolio_accounts.py`
(pure core + loaders), `tests/test_portfolio_burn_in.py` (harness semantics),
`tests/test_monitoring_routes.py` (operator surface), then the position-manager
suites (`test_position_manager_entry_backoff.py`,
`test_position_manager_exit_safety.py`) for the wiring. Then run this harness
live before changing any default limit or the master switch.
