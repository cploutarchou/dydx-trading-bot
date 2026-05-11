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

## References

- `docs/arbitrage-phase2-rollout-playbook.md`
- `docs/project-specific-arbitrage-improvement-plan.md`
- `docs/codex-final-report.md`
