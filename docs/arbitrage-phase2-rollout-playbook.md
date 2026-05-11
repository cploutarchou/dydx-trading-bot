# Arbitrage Phase 2 Rollout Playbook

Date: 2026-05-11

This playbook is for safely enabling the completed arbitrage efficiency and explainability work in staging, then production.

## Scope

Included in this rollout:

- `ARBITRAGE_IMPROVEMENTS_ENABLED`
- `PAIR_PRIORITY_ENGINE_ENABLED`
- Runtime diagnostics and explainability endpoints:
  - `GET /api/v1/arbitrage/improvement-metrics`
  - `GET /api/v1/arbitrage/pair-priority?limit=10`
  - `GET /api/v1/arbitrage/opportunity/:id/explain`

Explicitly excluded from this rollout:

- `AUTO_EXECUTION_CHANGES_ENABLED`
- External signal providers (`POLYMARKET_SIGNALS_ENABLED`, `DEFILLAMA_SIGNALS_ENABLED`, `NEWS_SIGNALS_ENABLED`)

## Preconditions

1. Latest migration-free backend/bot/frontend deploy is live.
2. Diagnostics endpoints return `200` and expected payloads.
3. Backtest and live behavior equivalence is accepted when flags are `false`.
4. Feature-flag admin route is functional:
   - `GET /api/v1/settings/arbitrage-runtime`
   - `PUT /api/v1/settings/arbitrage-runtime`

## Rollout Sequence

### Stage A — Baseline (all new flags off)

Duration: 30–60 minutes in staging traffic.

Settings:

- `ARBITRAGE_IMPROVEMENTS_ENABLED=false`
- `PAIR_PRIORITY_ENGINE_ENABLED=false`
- `PAIR_PRIORITY_MAX_PAIRS=0`

Capture baseline:

- `exchange_api_calls_total`
- `exchange_api_calls_saved_total`
- `duplicate_api_calls_avoided_total`
- `opportunities_detected_total`
- `opportunities_executed_total`
- `provider_errors_total`
- `stale_data_detected_total`
- top `rejection_reasons`

### Stage B — Enable safe API efficiency

Duration: 2–6 hours in staging traffic.

Settings:

- `ARBITRAGE_IMPROVEMENTS_ENABLED=true`
- keep all other new flags off

Expected effects:

- `exchange_api_calls_saved_total` and `duplicate_api_calls_avoided_total` increase
- stable or improved `opportunities_executed_total / opportunities_detected_total`
- no material increase in `provider_errors_total`

### Stage C — Enable pair-priority diagnostics

Duration: 2–6 hours in staging traffic.

Settings:

- `PAIR_PRIORITY_ENGINE_ENABLED=true`
- start with `PAIR_PRIORITY_MAX_PAIRS=0`

Then optionally apply a cap:

- `PAIR_PRIORITY_MAX_PAIRS=20` (or conservative value for your market universe)

Expected effects:

- similar or better execution quality with lower scan/API pressure
- visibility into why pairs are prioritized

### Stage D — Production progressive rollout

Roll out by environment slice or bot cohort:

1. 10% cohort for 2–4 hours
2. 50% cohort for 4–8 hours
3. 100% if gates pass

At each step, re-check KPI gates before proceeding.

## KPI Gates (Go / Hold / Rollback)

Use ratios where possible to avoid volume bias.

### Go thresholds

- API efficiency ratio improves:
   - $\text{saved\_ratio} = \frac{\Delta\,\text{exchange\_api\_calls\_saved\_total}}{\Delta\,\text{exchange\_api\_calls\_total}}$
   - target: `saved_ratio >= 0.10` in Stage B, `>= 0.15` after Stage C tuning.
- Duplicate-call avoidance ratio improves:
   - $\text{dup\_avoid\_ratio} = \frac{\Delta\,\text{duplicate\_api\_calls\_avoided\_total}}{\Delta\,\text{exchange\_api\_calls\_total}}$
   - target: non-decreasing across rollout stages.
- Execution quality does not regress materially:
   - $\text{exec\_quality} = \frac{\Delta\,\text{opportunities\_executed\_total}}{\Delta\,\text{opportunities\_detected\_total}}$
   - target: no worse than 5% relative from Stage A baseline.
- Provider stability remains healthy:
   - $\text{provider\_error\_rate} = \frac{\Delta\,\text{provider\_errors\_total}}{\Delta\,\text{exchange\_api\_calls\_total}}$
   - target: no statistically meaningful increase vs baseline.
- Rejection mix remains explainable:
   - top 3 `rejection_reasons` remain stable or improve (no sudden new dominant unknown reason).

### Hold / investigate triggers

- `provider_error_rate` rises > 20% relative to baseline for 30+ minutes.
- `exec_quality` drops > 5% relative for 30+ minutes.
- `stale_data_detected_total` slope spikes materially after a flag flip.
- unexplained rejection reason appears and becomes top-3 quickly.

### Immediate rollback triggers

- sustained elevated provider failures plus reduced execution quality.
- clear runtime instability tied to flag changes.
- operational incident requiring deterministic return to baseline behavior.

## KPI Dashboard Targets (first week)

Track at least these KPI cards:

1. **Saved API call ratio**
    - target: `>= 10%` after Stage B; `>= 15%` after Stage C tuning.
2. **Duplicate-call avoidance ratio**
    - target: steady upward trend after Stage B.
3. **Execution quality ratio**
    - target: within 95–105% of baseline until pair-priority tuning settles.
4. **Provider error rate**
    - target: flat vs baseline.
5. **Top rejection reasons**
    - target: more actionable/expected reasons, fewer noisy/unexpected reasons.

Primary endpoints for dashboard ingestion:

- `GET /api/v1/arbitrage/improvement-metrics`
- `GET /api/v1/arbitrage/pair-priority?limit=10`
- `GET /api/v1/arbitrage/opportunity/:id/explain`

## Fast rollback

1. Set via admin runtime settings:
   - `ARBITRAGE_IMPROVEMENTS_ENABLED=false`
   - `PAIR_PRIORITY_ENGINE_ENABLED=false`
   - `PAIR_PRIORITY_MAX_PAIRS=0`
2. Verify with:
   - `GET /api/v1/settings/arbitrage-runtime`
   - `GET /api/v1/arbitrage/improvement-metrics`
3. Confirm drift returns to baseline:
   - saved/avoided counters flatten
   - rejection mix normalizes

No schema rollback is required for this phase.

## Go-live checklist

- [ ] Stage A baseline captured and documented.
- [ ] Stage B gates passed.
- [ ] Stage C gates passed.
- [ ] `PAIR_PRIORITY_MAX_PAIRS` tuned (or explicitly left at `0`).
- [ ] `AUTO_EXECUTION_CHANGES_ENABLED=false` confirmed.
- [ ] `PAIR_PRIORITY_ENGINE_ENABLED` only when Stage B is stable.
- [ ] External signal flags remain `false`.
- [ ] No contract break in backend-proxied endpoints.
- [ ] Rollback owner + communication channel assigned.

## Backtest support status

Backtest behavior was preserved in this phase (no strategy logic rewrite).

For release sign-off, run your normal backtest regression matrix and verify:

- no API contract breaks in delegated backtest routes
- expected run status normalization still works
- no regression in run creation/list/details/status/trades flows

For strategy-impact A/B testing:

- vary backtest request inputs one-at-a-time (`pair_selection_mode`, `max_pairs`) to measure behavioral impact
- treat `ARBITRAGE_IMPROVEMENTS_ENABLED` as runtime-efficiency scope (do not expect direct backtest PnL deltas from this flag alone)
- compare candidate runs via `POST /api/v1/backtests/compare`

## Day-1 commands

For a ready-to-run operator checklist with exact curl commands, use:

- `docs/arbitrage-day1-rollout-command-sheet.md`

## Recommended default rollout values

- `ARBITRAGE_IMPROVEMENTS_ENABLED=true` (after Stage B pass)
- `PAIR_PRIORITY_ENGINE_ENABLED=true` (after Stage C pass)
- `PAIR_PRIORITY_MAX_PAIRS=0` initially, then tune gradually
- `PAIR_PRIORITY_STALE_SECONDS=86400` (current default)
- keep all external signals and auto execution changes disabled
