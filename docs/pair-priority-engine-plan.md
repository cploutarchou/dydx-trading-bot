# Pair Priority Engine Plan

## Scope

The engine ranks existing stored cointegrated pairs. It does not create trades, alter z-score thresholds, or bypass risk checks.

## Feature Flag

`PAIR_PRIORITY_ENGINE_ENABLED=false`

Optional cap:

`PAIR_PRIORITY_MAX_PAIRS=0`

`0` means rank all pairs without dropping any. A positive value scans only the top ranked pairs.

## Inputs

- `CointegrationResult` fields from `pair_storage`.
- Existing dYdX market metadata if already available.
- No external providers by default.

## Score

```text
final_pair_score =
    spread_potential_score
    + volume_score
    + liquidity_score
    + volatility_score
    + historical_opportunity_score
    - slippage_risk
    - stale_data_penalty
    - api_cost_penalty
```

## External Signals Later

- Polymarket: narrative probability changes mapped to affected assets.
- DefiLlama: TVL, liquidity, protocol volume, yield context.
- News: headline classification mapped to assets.

External signals may only affect pair priority. They must not directly execute trades.
