---
agent: 'Senior DeFi Monorepo Platform'
name: codex-dydx-strategy-suggestions
description: "Tune AI strategy suggestions to be dYdX-specific, risk-aware, and grounded in the selected strategy configuration and backtest evidence."
argument-hint: "Paste strategy config + recent backtest outcomes + current runtime issue (if any)."
---

Use this command when improving AI parameter suggestions for strategy tuning.

## Mission

Produce high-signal, dYdX-specific parameter recommendations that are:

- grounded in current strategy config,
- informed by recent backtest evidence,
- safe for live runtime constraints,
- concise and directly applicable.

## Inputs expected

- Strategy context: name, category, runtime strategy, network, pair selection mode
- Current parameters (numeric/boolean/resolution)
- Recent backtest summaries (win rate, pnl, sharpe, drawdown, trades)
- Any last runtime/backtest failure text

If some fields are missing, infer conservatively from available data. Do not fabricate values.

## dYdX-specific guidance

Bias suggestions toward:

1. Drawdown containment and liquidation safety first
2. Slippage/fee-aware execution reality (avoid overtrading)
3. Resolution and window choices that reduce noise-chasing
4. Position sizing that respects collateral and volatility regime

## Output contract (strict)

Return 5 to 8 lines (or the requested count, if one is provided) and nothing else.

Each line must be:

`N. <parameter_key>: Current '<value>' -> Suggested '<value>'. Rationale: <one concise sentence>`

Allowed parameter keys:

- `zscore_threshold`
- `stats_window`
- `max_half_life`
- `usd_per_trade`
- `usd_min_collateral`
- `max_positions`
- `max_drawdown_pct`
- `stop_loss_pct`
- `take_profit_pct`
- `trailing_stop_pct`
- `rebalance_interval_hours`
- `position_timeout_hours`
- `transaction_fee`
- `slippage`
- `max_history_days`
- `risk_free_rate`
- `resolution`
- `candle_resolution`

## Guardrails

- No markdown blocks, no bullet lists, no extra commentary.
- Prefer concrete values over vague guidance.
- If backtest quality is weak (low sharpe / high drawdown), prioritize risk reduction over aggressiveness.
- Avoid duplicate parameter keys in the output.
