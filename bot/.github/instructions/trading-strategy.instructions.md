---
name: "Trading Strategy Safety and Design"
description: "Use when implementing new arbitrage strategies, trading logic, or market-making algorithms. Enforces safety-first design, position tracking, collateral validation, and observability for DeFi trading."
applyTo: "src/trading/**/*.py"
---

# Trading Strategy Safety and Design

Apply these rules when building arbitrage, market-making, or any trading execution logic.

## Core Principles

1. **Fail-safe first**: Detect edge cases _before_ sending orders
2. **Collateral validation**: Verify sufficient collateral before every trade
3. **Position reconciliation**: Track local state AND exchange state separately
4. **Non-blocking execution**: Never sleep or block inside async trading loops
5. **Observable decisions**: Log all trading decisions with decision context (prices, collateral, risk)
6. **Graceful degradation**: Degrade to lower confidence strategies rather than stopping completely

## Mandatory Safety Checks

### Pre-Order Validation

Before ANY `send_order()` call:

```python
# 1. Validate collateral sufficiency
available_collateral = get_available_collateral(subaccount)
required_margin = calculate_margin_requirement(order_size, leverage)
assert available_collateral >= required_margin * SAFETY_BUFFER, \
    f"Insufficient collateral: {available_collateral} < {required_margin * SAFETY_BUFFER}"

# 2. Validate position limits
current_notional = get_current_notional_exposure(market)
max_notional = get_max_notional_per_market()
assert current_notional + order_notional <= max_notional, \
    f"Position limit exceeded: {current_notional + order_notional} > {max_notional}"

# 3. Check exchange connection state
assert exchange_connection.is_healthy(), "Exchange connection unhealthy, cannot trade"

# 4. Validate order parameters
assert order_size > MIN_ORDER_SIZE, f"Order too small: {order_size}"
assert price > 0, f"Invalid price: {price}"
```

### Position Tracking (Dual State Model)

Maintain **two** position states:

```python
class PositionState:
    """Dual-state position tracking for safety reconciliation."""

    def __init__(self):
        # Local state: what we believe we own
        self.local_positions: Dict[str, float] = {}

        # Exchange state: what dYdX reports
        self.exchange_positions: Dict[str, float] = {}

    def record_local_order(self, order_id: str, market: str, size: float, side: str):
        """Record order locally BEFORE confirmation from exchange."""
        self.local_positions[market] = self.local_positions.get(market, 0)
        if side == "buy":
            self.local_positions[market] += size
        else:
            self.local_positions[market] -= size

    def reconcile_with_exchange(self, exchange_positions: Dict[str, float]):
        """Compare local vs exchange state; flag mismatches."""
        mismatches = {}
        for market, local_size in self.local_positions.items():
            exchange_size = exchange_positions.get(market, 0)
            if abs(local_size - exchange_size) > RECONCILIATION_TOLERANCE:
                mismatches[market] = {
                    "local": local_size,
                    "exchange": exchange_size,
                    "drift": local_size - exchange_size,
                }

        if mismatches:
            logger.warning("Position drift detected", extra={"mismatches": mismatches})
            # Escalate or trigger emergency cleanup
            if self._drift_exceeds_threshold(mismatches):
                raise PositionReconciliationError(mismatches)

        # Sync local state to exchange truth
        self.local_positions = exchange_positions.copy()
```

### Slippage and Price Validation

```python
def validate_order_execution(
    order_id: str,
    requested_price: float,
    executed_price: float,
    market: str,
):
    """Validate that executed price is within tolerance."""
    slippage_pct = abs((executed_price - requested_price) / requested_price) * 100

    max_slippage = get_max_slippage_for_market(market)
    if slippage_pct > max_slippage:
        logger.error(
            "Excessive slippage detected",
            extra={
                "order_id": order_id,
                "requested_price": requested_price,
                "executed_price": executed_price,
                "slippage_pct": slippage_pct,
                "max_allowed": max_slippage,
            },
        )
        raise ExcessiveSlippageError(order_id, slippage_pct, max_slippage)
```

## Arbitrage-Specific Rules

### 1. Cycle Detection and Validation

```python
class ArbitrageCycle:
    """Validate multi-leg arbitrage cycles."""

    def validate(self) -> ValidationResult:
        """
        Ensure:
        - Cycle completes (last leg returns to starting asset)
        - All legs have sufficient liquidity
        - Profit > transaction costs
        - All exchanges are healthy
        """
        # Check cycle completeness
        assert self.legs[-1].target_asset == self.legs[0].source_asset

        # Check liquidity for each leg
        for leg in self.legs:
            available_liquidity = get_market_depth(leg.market, self.size)
            if available_liquidity < self.size:
                return ValidationResult(
                    valid=False,
                    reason=f"Insufficient liquidity on {leg.market}",
                )

        # Calculate net profit
        gross_profit = self.calculate_gross_profit()
        transaction_costs = sum(leg.calculate_cost() for leg in self.legs)
        net_profit = gross_profit - transaction_costs

        if net_profit < MIN_PROFIT_THRESHOLD:
            return ValidationResult(
                valid=False,
                reason=f"Net profit {net_profit} below threshold",
            )

        return ValidationResult(valid=True, net_profit=net_profit)
```

### 2. Multi-Exchange Order Synchronization

For arbitrage crossing multiple exchanges:

```python
async def execute_synchronized_arbitrage(cycle: ArbitrageCycle) -> ExecutionResult:
    """
    Execute multi-exchange arbitrage with atomic consistency.

    If any leg fails, emit emergency cleanup signal for partial fills.
    """
    executed_legs = []

    try:
        for i, leg in enumerate(cycle.legs):
            logger.info(f"Executing leg {i+1}/{len(cycle.legs)}", extra={"leg": leg})

            result = await execute_leg_with_timeout(leg, timeout=LEG_TIMEOUT_SECONDS)
            executed_legs.append(result)

            # Validate intermediate state
            if not result.success:
                raise LegExecutionError(i, result.error)

    except Exception as e:
        logger.error(
            "Arbitrage cycle failed; triggering emergency cleanup",
            extra={
                "executed_legs": len(executed_legs),
                "total_legs": len(cycle.legs),
                "error": str(e),
            },
        )

        # Emit cleanup signal so other systems can exit partial fills
        await emit_emergency_cleanup_signal(executed_legs)
        raise

    return ExecutionResult(success=True, legs=executed_legs)
```

## Liquidation Risk Management

```python
def check_liquidation_risk(subaccount: Subaccount) -> LiquidationRisk:
    """Calculate distance to liquidation."""
    equity = subaccount.equity
    total_maintenance_margin = sum(
        position.maintenance_margin for position in subaccount.positions
    )

    margin_ratio = equity / total_maintenance_margin if total_maintenance_margin > 0 else float("inf")

    LIQUIDATION_THRESHOLD = 1.0  # ratio at which liquidation occurs
    SAFETY_MARGIN = 1.25  # we want to stay 25% above liquidation

    if margin_ratio < LIQUIDATION_THRESHOLD:
        raise LiquidationError(f"Already liquidated! Ratio: {margin_ratio}")

    if margin_ratio < SAFETY_MARGIN:
        logger.warning(
            "Liquidation risk elevated",
            extra={
                "margin_ratio": margin_ratio,
                "equity": equity,
                "total_maintenance_margin": total_maintenance_margin,
            },
        )

    return LiquidationRisk(
        margin_ratio=margin_ratio,
        at_risk=margin_ratio < SAFETY_MARGIN,
    )
```

## Observability Requirements

Every trading decision must emit structured logs:

```python
logger.info(
    "Trading decision made",
    extra={
        "decision_type": "arbitrage_cycle_execution",
        "cycle_id": cycle.id,
        "legs": len(cycle.legs),
        "gross_profit": cycle.gross_profit,
        "transaction_costs": cycle.transaction_costs,
        "net_profit": cycle.net_profit,
        "collateral_available": available_collateral,
        "collateral_required": required_collateral,
        "max_position_notional": max_notional,
        "current_exposure": current_notional,
        "margin_ratio": margin_ratio,
        "liquidation_risk": "elevated" if margin_ratio < 1.25 else "normal",
    },
)
```

## Testing Expectations

For any new trading strategy:

1. **Unit tests**: Validate decision logic in isolation

   ```python
   def test_arbitrage_cycle_profit_calculation():
       cycle = ArbitrageCycle(...)
       result = cycle.validate()
       assert result.valid
       assert result.net_profit > MIN_PROFIT_THRESHOLD
   ```

2. **Integration tests**: Validate with mock exchange

   ```python
   async def test_synchronized_arbitrage_execution(mock_exchange):
       result = await execute_synchronized_arbitrage(cycle)
       assert result.success
       assert_positions_reconciled(result)
   ```

3. **Safety tests**: Ensure failures cascade gracefully

   ```python
   async def test_arbitrage_cleanup_on_leg_failure(mock_exchange):
       mock_exchange.fail_leg(leg_index=2)
       with pytest.raises(LegExecutionError):
           await execute_synchronized_arbitrage(cycle)
       # Verify cleanup signal was emitted
       assert cleanup_signal_emitted()
   ```

4. **Testnet validation**: Run on dYdX testnet with realistic parameters

## Documentation Requirements

When implementing a new strategy:

- **Decision logic**: Why does this strategy work? What are the edge cases?
- **Risk assumptions**: What collateral/leverage is safe?
- **Failure modes**: What breaks the strategy? How do we detect and recover?
- **Profit targets**: What's the minimum profitable spread? Under what conditions does profit vanish?
- **Emergency exit**: How do we unwind if the strategy goes wrong?
