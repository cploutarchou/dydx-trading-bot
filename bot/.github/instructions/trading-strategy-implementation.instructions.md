---
name: "Trading Strategy Implementation"
description: "Use when implementing or reviewing DeFi arbitrage strategies, market-making logic, position management, or trading decision algorithms. Enforces safety-first design, risk controls, and deterministic behavior."
applyTo: "src/trading/**/*.py"
---

# Trading Strategy Implementation

Apply these rules when building or modifying trading strategies and decision logic.

## Mandatory rules

### 1. Risk Control First

- **Always** implement position size limits and maximum loss thresholds before decision logic
- Validate collateral availability and liquidation risk before ANY order placement
- Implement slippage simulation and mark-to-market loss estimates
- Use fail-safe defaults: reject ambiguous decisions rather than guess

### 2. Arbitrage Safety

- Cross-exchange spreads must account for:
  - Withdrawal/deposit delays and fees
  - Network latency and order execution variance
  - Liquidity depth and partial fill scenarios
  - Fee structures (maker, taker, withdrawal)
- Never assume instant fills; model partial execution and cancellation flow
- Calculate break-even threshold BEFORE signal generation
- Document all assumptions in docstrings with ranges/constraints

### 3. Deterministic State

- No random delays or probabilistic decisions in order logic
- All strategy parameters must be deterministic and version-controlled
- Use monotonic timestamps for event ordering, never wall-clock time
- Store decision history and rationale for post-trade analysis
- Implement audit logging: why each trade was taken/rejected

### 4. Position Reconciliation

- On startup: validate local position state vs. exchange state
- Implement diffs tolerance: expected vs. actual holdings
- For mismatches:
  - Log with full context (exchange API calls, local cache, timing)
  - Escalate with Telegram alert if drift exceeds threshold
  - Never auto-correct without human review on mainnet
  - Quarantine affected positions pending investigation
- Implement per-subaccount position tracking with rollup validation

### 5. Market Data Validation

- Validate market data freshness before using in decisions
  - Detect stale price feeds (e.g., no update for N seconds)
  - Detect spread anomalies (bid > ask or impossible levels)
  - Detect volume anomalies (exchange circuit breaker behavior)
- Fallback to last-known state with explicit degradation mode
- Log all data anomalies for post-incident review

### 6. Order Execution Safety

- Implement pre-order validation:
  - Sufficient collateral for worst-case loss
  - Position limits not exceeded after fill
  - Order price within band (e.g., ±5% of mark price)
- Implement order lifecycle tracking:
  - Keep pending orders in-memory with timeout
  - Detect partial fills and adjust remaining quantity
  - Reconcile filled quantities against exchange receipts
- For failed orders: log rejection reason, backoff if transient, escalate if persistent

### 7. Liquidation Prevention

- Track liquidation distance (mark price to liquidation price)
- Inject safety margin: never exceed collateral × (1 - safety_factor)
- On liquidation risk (distance < threshold):
  - Close highest-risk positions first
  - Reduce position size by fixed factor (e.g., 25%)
  - Notify with urgent alert + detailed reasoning
  - Log trades that avoided liquidation (for audit)

## Implementation Patterns

### Strategy Decision Function

```python
def should_enter_arbitrage(
    pair: str,
    exchange_a: dict,  # {bid, ask, depth_at_levels}
    exchange_b: dict,  # {bid, ask, depth_at_levels}
    config: StrategyConfig,
    state: TradingState,
) -> tuple[bool, str, float]:
    """
    Args:
        pair: Trading pair (e.g., "DYDX-USD")
        exchange_a, exchange_b: Market data with spread info
        config: Strategy parameters (thresholds, position limits)
        state: Current positions, collateral, liquidation margin

    Returns:
        (should_trade, reason, expected_pnl)
        reason: Human-readable decision rationale
        expected_pnl: Estimated profit (or loss if negative)
    """
    # 1. Validate data freshness
    if time.time() - exchange_a["timestamp"] > config.max_data_age_seconds:
        return False, "stale_data_a", 0.0
    if time.time() - exchange_b["timestamp"] > config.max_data_age_seconds:
        return False, "stale_data_b", 0.0

    # 2. Detect anomalies
    if exchange_a["bid"] >= exchange_a["ask"]:
        return False, "inverted_spread_a", 0.0
    if exchange_b["bid"] >= exchange_b["ask"]:
        return False, "inverted_spread_b", 0.0

    # 3. Calculate spread (worst-case with fees)
    spread = (exchange_b["ask"] + config.exchange_b_fee) - (exchange_a["bid"] - config.exchange_a_fee)

    # 4. Model execution cost
    liquidity_cost = 0.0
    for depth_level, depth_value in enumerate(config.depth_thresholds):
        if depth_value > exchange_a["depth"][depth_level]:
            liquidity_cost += config.depth_penalty_bps * 0.0001

    # 5. Calculate break-even
    break_even = spread + liquidity_cost + config.min_profit_bps * 0.0001
    if break_even < 0:
        return False, "insufficient_spread", break_even

    # 6. Check position limits
    notional_value = config.position_size * (exchange_a["bid"] + exchange_b["ask"]) / 2
    if state.total_notional + notional_value > config.max_notional:
        return False, "position_limit_exceeded", 0.0

    # 7. Check liquidation distance
    liquidation_margin = state.collateral / state.leverage
    available_margin = liquidation_margin - state.total_notional - notional_value
    if available_margin < config.min_liquidation_margin:
        return False, "liquidation_risk", 0.0

    # 8. All checks passed
    expected_pnl = break_even * config.position_size
    return True, f"spread_sufficient_{break_even:.4f}", expected_pnl
```

### Audit Logging

```python
def log_trade_decision(
    decision_id: str,
    pair: str,
    decision: bool,
    reason: str,
    expected_pnl: float,
    market_state: dict,
    config_snapshot: dict,
):
    """Log all trade decisions with full context for post-trade analysis."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "decision_id": decision_id,
        "pair": pair,
        "decision": decision,
        "reason": reason,
        "expected_pnl": expected_pnl,
        "market_state": market_state,
        "config_snapshot": config_snapshot,
    }
    logger.info(f"TRADE_DECISION: {json.dumps(entry)}")
    # Also persist to database for analysis dashboards
```

## Testing Requirements

- [ ] Unit test: arbitrage detection with synthetic market data
- [ ] Unit test: liquidation prevention logic with edge cases
- [ ] Unit test: partial fill handling and reconciliation
- [ ] Integration test: full entry → exit cycle on testnet
- [ ] Stress test: position limits with rapid market moves
- [ ] Regression test: previous loss incidents (if any) don't repeat

## Documentation

Every strategy implementation must include:

- **Objective**: What market inefficiency does it exploit?
- **Assumptions**: Market data freshness, fill probabilities, fee structures
- **Risk factors**: Liquidation triggers, max drawdown scenarios, tail risks
- **Parameters**: Thresholds, limits, timeouts—where they come from and how to tune
- **Audit trail**: How to replay trades and validate execution

## Co-changes

When shipping strategy changes, also update:

- `README.md` (strategy overview, new parameters)
- `docs/OPERATIONS.md` (tuning guide, risk controls)
- `tasks.md` (backtest/testnet validation steps)
