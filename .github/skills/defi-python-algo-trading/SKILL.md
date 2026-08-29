---
name: defi-python-algo-trading
description: 'Design, implement, debug, and validate Python DeFi algo-trading changes in this dYdX bot repo. Use for strategy updates, entry/exit logic, config wiring, precision fixes, async API handling, state persistence, and backtest verification with quality gates.'
argument-hint: 'What trading change should this skill deliver?'
user-invocable: true
---

# DeFi Python Algo Trading Workflow

Use this skill when you need production-safe changes to the Python trading bot, especially for:
- Strategy logic (entry/exit, z-score, cointegration)
- Order execution safety (paired atomic execution)
- Config additions (`config.yaml` -> dataclass -> constants)
- dYdX precision/formatting and async API correctness
- Backtesting, validation, and regression checks
- Risk controls (kill-switch, drawdown controls, circuit-breakers)
- DeFi execution realities (funding, slippage, liquidity, market impact)
- Performance optimization and production observability

## Outcome

Produce a tested, minimal-risk code change that:
1. Preserves atomic paired trade behavior
2. Uses constants/config patterns correctly
3. Keeps datetime operations timezone-aware UTC
4. Passes relevant tests/lint checks
5. Includes a short verification summary

## Decision Logic

1. **Is this config-related?**
   - Yes -> Add key to the encrypted profile (`config/profiles/*.config.enc.json` via `make dev-config`), update the dataclass in `bot/config/config.py`, export in `bot/src/constants.py`, consume constants in runtime code.
   - No -> Continue.

2. **Does this touch order placement or close logic?**
   - Yes -> Enforce atomic pair guarantees; if side 2 fails after side 1 filled, perform emergency cleanup on side 1.
   - No -> Continue.

3. **Does this touch market values sent to exchange?**
   - Yes -> Format all numbers with `format_number(value, reference)` using tick/step metadata.
   - No -> Continue.

4. **Does this touch datetimes/backtests?**
   - Yes -> Use timezone-aware UTC (`pd.Timestamp(..., tz='UTC')`) consistently.
   - No -> Continue.

5. **Are API calls async dYdX operations?**
   - Yes -> Ensure every client call is awaited.

6. **What strategy family does this change target?**
   - Mean reversion/stat-arb -> prioritize spread stability, z-score robustness, and pair selection quality.
   - Momentum/trend -> prioritize regime filters, trend persistence checks, and stop logic.
   - Market making/liquidity capture -> prioritize inventory limits, spread adaptation, and quote safety.
   - Mixed/hybrid -> isolate each component and validate independently before integration.

## Multi-Phase Procedure

1. **Phase 1: Strategy & Risk Framing**
   - Identify expected behavior, failure modes, and rollback/safety concerns.
   - Confirm affected areas: config, execution, precision, state, backtest, observability.
   - Define acceptance criteria: PnL impact expectations, max tolerated drawdown, and execution safety boundaries.

2. **Phase 2: Investigation & Baseline**
   - Read relevant files end-to-end (or large sections) for full context.
   - Map call flow and side effects (state files, DB writes, external API calls).
   - Capture baseline metrics (current loop time, backtest result snapshot, error rate/log noise).

3. **Phase 3: Plan Minimal, Testable Changes**
   - Create a short checklist with small, testable increments.
   - Prefer smallest change set preserving existing public behavior unless requirement dictates otherwise.
   - Add branch-specific tests (mean reversion vs momentum vs market-making path).

4. **Phase 4: Implement Incrementally**
   - Add/update logic in small commits/patches.
   - Preserve style and existing APIs.
   - Keep logging meaningful and error handling tiered (critical exit vs skip/log).

5. **Phase 5: Validate Continuously**
   - Run focused tests after each significant change.
   - Run lint/format checks where relevant.
   - For strategy behavior, run a quick backtest/smoke validation.

6. **Phase 6: Safety & DeFi Execution Hardening**
   - Confirm no orphaned positions path exists.
   - Confirm precision formatting on all order parameters.
   - Confirm state persistence remains consistent (`bot_agents.json`, `cointegrated_pairs.json`, history files).
   - Validate funding-aware behavior if holding windows can span funding timestamps.
   - Validate liquidity-aware sizing and slippage assumptions for each market.

7. **Phase 7: Performance & Observability Validation**
   - Check loop/runtime overhead introduced by the change.
   - Ensure actionable telemetry exists (structured logs and event-level tracing for entry/exit/open/close failures).
   - Ensure alerts are wired for critical failures and anomaly spikes.

8. **Phase 8: Finalize Output**
   - Summarize changed files and why.
   - Report what was verified (tests/lint/backtest) and any remaining risks.
   - List optional follow-up tests for hidden edge cases.

## Strategy Branch Checks

### Mean Reversion / Statistical Arbitrage
- Verify spread stationarity assumptions still hold.
- Validate z-score windows and zero-cross exit behavior.
- Stress-test with volatile windows and stale candle gaps.

### Momentum / Trend Following
- Validate trend filter lookback and whipsaw behavior.
- Confirm stop/exit logic triggers with low latency.
- Test across trend and chop regimes.

### Market Making / Liquidity Capture
- Enforce inventory caps and skew limits.
- Validate quote update throttling/rate limits.
- Verify adverse selection protections and spread widening rules.

## Risk Control Requirements

- Define and enforce max per-trade risk and max concurrent exposure.
- Add or validate a kill-switch condition for severe anomaly states.
- Add circuit-breaker logic for repeated execution failures.
- Ensure graceful unwind procedures are documented for partial failures.

## DeFi-Specific Requirements

- Model and account for funding payments where applicable.
- Include slippage and liquidity checks before order submission.
- Flag oracle/mark-price anomalies and define safe fallback behavior.
- Validate behavior under exchange/API degradation scenarios.

## Performance & Optimization Checks

- Measure impact on trading loop latency.
- Avoid repeated expensive parsing or redundant data fetches.
- Cache where safe; invalidate deterministically.
- Validate memory/file I/O growth patterns over long runs.

## Observability Pack

- Required events: signal-generated, order-submitted, order-filled, pair-opened, pair-closed, cleanup-triggered, error-critical.
- Required dimensions: instance id, pair markets, strategy mode, z-score/spread snapshot, latency, status.
- Alerts: critical execution failure, repeated partial fill cleanup, loop stall, state-write failures.
- Runbook note: include first 3 triage checks and emergency close path.

## Quality Gates (Must Pass)

- [ ] Config flow follows single-source pattern (`config/profiles/*.config.enc.json` -> generated `run.json` -> `config/config.py` -> `constants.py`)
- [ ] No repeated runtime parsing pattern introduced
- [ ] All relevant datetimes are timezone-aware UTC
- [ ] Atomic paired execution safety maintained
- [ ] Numeric precision formatting applied before exchange submission
- [ ] Async API calls are properly awaited
- [ ] Relevant tests pass; lint/format pass for touched scope
- [ ] Logs/errors are actionable; critical paths alert+terminate appropriately
- [ ] Strategy-branch checks executed for the affected strategy family
- [ ] Risk controls validated for failure bursts and drawdown scenarios
- [ ] DeFi-specific execution constraints validated (funding/slippage/liquidity)
- [ ] Performance overhead measured and acceptable for loop cadence
- [ ] Observability and alerting signals are present and useful

## Completion Checklist

A task is complete only when:
- Behavior matches requirement and safety constraints
- Verification evidence is captured (what ran + result)
- Todo/checklist is fully marked complete, skipped (with reason), or blocked
- Notes include any assumptions and known limitations

## Suggested Invocation Prompts

- `/defi-python-algo-trading Add a new entry filter using rolling volatility, with config wiring and tests.`
- `/defi-python-algo-trading Fix intermittent orphaned positions when second leg fails to fill.`
- `/defi-python-algo-trading Refactor z-score computation for UTC-safe backtest windows and verify regressions.`
- `/defi-python-algo-trading Add a trade sizing tweak while preserving precision and async safety.`
- `/defi-python-algo-trading Add kill-switch and circuit-breaker logic with observability and runbook updates.`
- `/defi-python-algo-trading Improve strategy loop performance by reducing redundant fetch/compute overhead.`
