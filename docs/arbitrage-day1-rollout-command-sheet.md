# Arbitrage Day-1 Rollout Command Sheet

Date: 2026-05-11

Use this sheet during rollout windows to verify health, enable flags safely, and decide go/hold/rollback.

## Scope

This command sheet covers:

- `ARBITRAGE_IMPROVEMENTS_ENABLED`
- `PAIR_PRIORITY_ENGINE_ENABLED`
- Diagnostics endpoints and explainability checks

This sheet does **not** enable:

- `AUTO_EXECUTION_CHANGES_ENABLED`
- External signal providers (`POLYMARKET_SIGNALS_ENABLED`, `DEFILLAMA_SIGNALS_ENABLED`, `NEWS_SIGNALS_ENABLED`)

## Preconditions

- Backend API reachable on `:8888`
- Bot API reachable on `:8889`
- Admin token available for runtime settings write operations

Set token once:

```bash
export ADMIN_TOKEN="<paste-admin-jwt>"
```

## 1) Health and diagnostics reachability

```bash
curl -sS http://localhost:8889/health | jq
curl -sS http://localhost:8889/metrics | jq
curl -sS -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8888/api/v1/arbitrage/improvement-metrics | jq
curl -sS -H "Authorization: Bearer $ADMIN_TOKEN" "http://localhost:8888/api/v1/arbitrage/pair-priority?limit=10" | jq
```

Expected:

- HTTP 200 for all calls
- metrics payload includes `counters`
- improvement metrics include `rejection_reasons`

## 2) Read current runtime settings

```bash
curl -sS -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8888/api/v1/settings/arbitrage-runtime | jq
```

Expected keys in `data`:

- `arbitrage_improvements_enabled`
- `pair_priority_engine_enabled`
- `pair_priority_max_pairs`
- `pair_priority_stale_seconds`

## 3) Stage A baseline (all off)

Set baseline config:

```bash
curl -sS -X PUT \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8888/api/v1/settings/arbitrage-runtime \
  -d '{
    "settings": {
      "arbitrage_improvements_enabled": false,
      "pair_priority_engine_enabled": false,
      "pair_priority_max_pairs": 0,
      "auto_execution_changes_enabled": false,
      "polymarket_signals_enabled": false,
      "defillama_signals_enabled": false,
      "news_signals_enabled": false
    }
  }' | jq
```

Capture baseline snapshot:

```bash
curl -sS -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8888/api/v1/arbitrage/improvement-metrics | jq '.data'
```

## 4) Stage B enable safe efficiency

Enable only safe API efficiency:

```bash
curl -sS -X PUT \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8888/api/v1/settings/arbitrage-runtime \
  -d '{
    "settings": {
      "arbitrage_improvements_enabled": true,
      "pair_priority_engine_enabled": false,
      "pair_priority_max_pairs": 0
    }
  }' | jq
```

Check counters after traffic interval:

```bash
curl -sS -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8888/api/v1/arbitrage/improvement-metrics | jq '.data.counters'
```

Watch:

- `exchange_api_calls_saved_total` increasing
- `duplicate_api_calls_avoided_total` increasing
- no abnormal increase in `provider_errors_total`

## 5) Stage C enable pair priority

Enable pair-priority engine without cap first:

```bash
curl -sS -X PUT \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8888/api/v1/settings/arbitrage-runtime \
  -d '{
    "settings": {
      "pair_priority_engine_enabled": true,
      "pair_priority_max_pairs": 0
    }
  }' | jq
```

Optional cap tuning (example: 20):

```bash
curl -sS -X PUT \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8888/api/v1/settings/arbitrage-runtime \
  -d '{
    "settings": {
      "pair_priority_max_pairs": 20
    }
  }' | jq
```

Inspect ranking and explanations:

```bash
curl -sS -H "Authorization: Bearer $ADMIN_TOKEN" "http://localhost:8888/api/v1/arbitrage/pair-priority?limit=10" | jq '.data'
```

## 6) Rejection reason explainability checks

Top reasons:

```bash
curl -sS -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8888/api/v1/arbitrage/improvement-metrics | jq '.data.rejection_reasons'
```

Explain one reason (example: `min_order_size`):

```bash
curl -sS -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8888/api/v1/arbitrage/opportunity/reason_min_order_size/explain | jq '.data'
```

## 7) Go / Hold / Rollback quick checks

GO when:

- saved-call counters rising
- execution quality stable
- provider errors stable

HOLD when:

- stale data or provider errors trend up unexpectedly
- execution quality trends down

ROLLBACK command:

```bash
curl -sS -X PUT \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8888/api/v1/settings/arbitrage-runtime \
  -d '{
    "settings": {
      "arbitrage_improvements_enabled": false,
      "pair_priority_engine_enabled": false,
      "pair_priority_max_pairs": 0
    }
  }' | jq
```

Verify rollback state:

```bash
curl -sS -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8888/api/v1/settings/arbitrage-runtime | jq '.data'
```

## 8) Backtest compatibility spot-check

```bash
curl -sS -H "Authorization: Bearer $ADMIN_TOKEN" "http://localhost:8888/api/v1/backtests?limit=5" | jq '.success, .data.total'
```

Expected:

- response shape unchanged
- no delegated route regressions

## 9) Backtest A/B experiments (feature impact)

Yes — you can run A/B backtests, but with an important boundary:

- `ARBITRAGE_IMPROVEMENTS_ENABLED`: expected to affect live runtime efficiency (API-call behavior), **not** backtest PnL logic.
- `PAIR_PRIORITY_ENGINE_ENABLED`: live runtime flag; backtest selection impact should be tested via backtest request fields (`pair_selection_mode`, `max_pairs`) rather than this runtime flag alone.

Recommended experiment pattern:

1. Keep strategy payload identical.
2. Run baseline backtest (A).
3. Change only one variable for variant (B):
   - `pair_selection_mode` (e.g. `liquidity` -> `cointegration`), or
   - `max_pairs` (e.g. `0` -> `20`).
4. Compare with `/api/v1/backtests/compare`.

Example A run:

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8888/api/v1/backtests/run \
  -d '{
    "name": "A-liquidity-all",
    "start_date": "2025-01-01",
    "end_date": "2025-03-31",
    "pair_selection_mode": "liquidity",
    "max_pairs": 0,
    "selected_pairs": ["BTC-USD/ETH-USD", "SOL-USD/AVAX-USD"],
    "trading_parameters": {
      "zscore_threshold": 1.5,
      "stats_window": 21,
      "usd_per_trade": 10.0,
      "pair_selection_mode": "liquidity"
    }
  }' | jq '.data.run_id'
```

Example B run (single-variable change):

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8888/api/v1/backtests/run \
  -d '{
    "name": "B-cointegration-all",
    "start_date": "2025-01-01",
    "end_date": "2025-03-31",
    "pair_selection_mode": "cointegration",
    "max_pairs": 0,
    "selected_pairs": ["BTC-USD/ETH-USD", "SOL-USD/AVAX-USD"],
    "trading_parameters": {
      "zscore_threshold": 1.5,
      "stats_window": 21,
      "usd_per_trade": 10.0,
      "pair_selection_mode": "cointegration"
    }
  }' | jq '.data.run_id'
```

Compare A vs B:

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8888/api/v1/backtests/compare \
  -d '{
    "run_ids": ["<runA>", "<runB>"],
    "metrics": ["total_pnl", "win_rate", "sharpe_ratio", "max_drawdown_pct", "total_trades", "profit_factor"]
  }' | jq '.data'
```

Optional automation helper (runs A/B end-to-end and prints compare summary):

```bash
python3 scripts/backtest_ab_experiment.py \
  --base-url http://localhost:8888 \
  --token "$ADMIN_TOKEN" \
  --experiment-name "ab-liquidity-vs-cointegration" \
  --start-date 2025-01-01 \
  --end-date 2025-03-31 \
  --selected-pairs "BTC-USD/ETH-USD,SOL-USD/AVAX-USD" \
  --pair-selection-mode-a liquidity \
  --pair-selection-mode-b cointegration \
  --max-pairs-a 0 \
  --max-pairs-b 0
```

Persistence note:

- The helper stores experiment context + comparison summary in each run's DB-backed metadata (`ab_experiment`) via the backtest metadata API.

Interpretation guide:

- If only runtime flags changed and backtest inputs stayed identical, large PnL deltas are unexpected.
- If `pair_selection_mode` / `max_pairs` changed, metric shifts are expected and should be used for strategy tuning.

## References

- `docs/arbitrage-phase2-rollout-playbook.md`
- `docs/project-specific-arbitrage-improvement-plan.md`
- `docs/codex-final-report.md`
