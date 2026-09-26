---
name: dydx-pairs-arbitrage
description: 'Design, tune, and debug the dYdX bot's pairs/arbitrage trading stack: cointegration-based pair selection, the pair-priority engine, z-score entry/exit decisions, runtime feature flags, arbitrage observability, and account-level portfolio risk interplay. Use for any change to pair discovery/ranking, spread or z-score logic, arbitrage runtime settings, decision audit trails, or arbitrage backtest parity.'
argument-hint: 'What arbitrage/pairs change should this skill deliver?'
user-invocable: true
---

# dYdX Pairs-Arbitrage Workflow

Use this skill for changes to the statistical-arbitrage core of the bot. It complements
`defi-python-algo-trading` (general trading safety) with the pairs-specific decision stack.
You are acting as a senior Python quant developer: every change must be deterministic,
fail-safe, auditable, and validated against both the live-decision tests and backtest parity.

## The arbitrage stack (where things live)

| Concern | Module | Notes |
| --- | --- | --- |
| Cointegration analysis | `src/trading/analysis/cointegration.py` | Engle-Granger style tests feeding pair viability |
| Pair ranking (live) | `src/trading/pair_priority.py` | Pair-priority engine scoring candidate pairs |
| Backtest pair selection | `src/infrastructure/use_cases/backtest_pair_selection.py` | `_prioritize_pairs*` + `_pair_cointegration_score`; must stay behaviorally aligned with live ranking |
| Entry/exit decisions | `src/trading/position_manager.py` (`open_positions`) | Z-score/entry gates; portfolio guard wired right after `max_positions` |
| Atomic pair execution | `src/trading/bot_agent.py` | Leg-1-filled + leg-2-failed ⇒ emergency cleanup of leg 1 |
| Tracked-position state | `src/trading/bot_agents_state.py` | Concurrency-safe per-instance state; DB primary, JSON fallback |
| Runtime feature flags | `src/trading/arbitrage_runtime_config.py` | Runtime-overridable (env vars are startup defaults only) |
| Decision audit trail | `src/trading/arbitrage_observability.py` | Counters + rejection reasons + snapshots |
| Live trade records | `src/trading/trade_persistence.py` | Exit gated on exchange-flat confirmation |
| Portfolio entry guard | `src/trading/portfolio_risk.py` | Account-level caps on the SHARED subaccount |
| Operator API | `src/api/v1/arbitrage.py` | `/api/v1/arbitrage/*` visibility + runtime-settings PUT |

## Runtime flags (check before touching behavior)

Feature flags live in `arbitrage_runtime_config.FEATURE_FLAG_KEYS`:
`ARBITRAGE_IMPROVEMENTS_ENABLED`, `PAIR_PRIORITY_ENGINE_ENABLED`, `POLYMARKET_SIGNALS_ENABLED`,
`DEFILLAMA_SIGNALS_ENABLED`, `NEWS_SIGNALS_ENABLED`, `AUTO_EXECUTION_CHANGES_ENABLED`, `COST_GATE_ENABLED` — plus
integer/float settings `PAIR_PRIORITY_MAX_PAIRS`, `PAIR_PRIORITY_STALE_SECONDS` and the cost-gate settings
(`COST_GATE_EDGE_MULTIPLE`, `COST_GATE_TAKER_FEE`, `COST_GATE_SLIPPAGE_BPS`, `FUNDING_SAME_SIDE_THRESHOLD`; see
`src/trading/entry_cost_gate.py`). Runtime overrides reach the bot API process only, not trading workers, which read
the bot-api environment at spawn.

Rules:
- Env vars are **startup defaults**; the backend/admin may override at runtime via
  `PUT /api/v1/arbitrage/runtime-settings`. Never read the env var directly in a decision path.
- New flags must be added to `FEATURE_FLAG_KEYS` (or the typed setting keys) so the
  runtime-settings route, clamping, and snapshots stay coherent.
- Any new executable-behavior flag ships **default-off** (enforce-only-proven-controls).

## Procedure

1. **Frame the decision change.** Write down the exact entry/exit predicate before/after,
   the regime it targets (mean-reversion spread vs trend vs carry), and the failure mode
   it must NOT introduce ( orphan legs, unbounded sizing, stale-data entries).
2. **Establish decision parity surfaces.** Identify every place the same logic runs:
   live (`position_manager` / `bot_agent`), ranking (`pair_priority`),
   backtest (`backtest_pair_selection` + `service_backtest._simulate_pair`). A change to
   spread/z-score semantics in one surface without the others silently forks live vs backtest.
3. **Keep decisions deterministic.** Same inputs ⇒ same decision, always: no wall-clock
   reads inside scoring (pass timestamps in), no dict-iteration-order dependence, no
   unsorted candidate sets. Tie-breaks must be explicit (stable sort on a total key).
4. **Fail safe on bad data.** Missing/short candle history, NaN spreads, or failed
   cointegration math must reject the pair (record the rejection reason), never fall back
   to a default trade. Fresh accounts/404s are handled by the indexer circuit-breaker
   predicate — do not add new broad catches around these paths.
5. **Size and risk-check before submit.** Entry passes the per-instance checks AND
   `check_portfolio_entry_guard` (aggregate open-market cap, margin utilization,
   free-collateral floor, optional drawdown cap). Every guard denial must be
   rejection-counted and audit-logged (`trade_entry_rejected_portfolio_risk` for the
   portfolio guard) — denial observability is part of the feature, not optional.
6. **Make it auditable.** Every accept/reject in the decision path increments
   `arbitrage_observability` counters with a machine-readable reason string. If a human
   can't reconstruct why a pair traded today from metrics + logs, the change isn't done.
7. **Validate.** Run the mandated suites for touched areas — at minimum
   `tests/test_arbitrage_observability.py`, `tests/test_arbitrage_cycle_cache.py`,
   `tests/test_pair_priority_engine.py`, `tests/test_arbitrage_routes.py`; add
   `tests/test_portfolio_risk.py` and `tests/test_position_manager_entry_backoff.py` /
   `tests/test_position_manager_exit_safety.py` when entry/exit behavior changes;
   `tests/test_backtest_api_contract.py` when backtest payloads change. Then a
   backtest smoke over a period that contains the regime the change targets.

## Pair-selection quality bar (quant review)

- Cointegration scores must degrade gracefully with sample size — clamp p-values to [0,1]
  and never let a short-history pair outrank a well-tested one on noise.
- Liquidity and volatility extraction must handle missing market metadata without
  inventing values (missing ⇒ penalize, don't assume average).
- Stale pairs (no fresh decisions within `PAIR_PRIORITY_STALE_SECONDS`) must fall out of
  the ranking deterministically; the stale threshold is runtime-tunable, not hardcoded.
- The pair cache (`test_arbitrage_cycle_cache.py`) must never serve a decision computed
  under a different feature-flag snapshot — key caches by the settings that produced them
  when adding new inputs.

## Hard invariants (never break)

1. **Atomic legs**: leg-1 filled + leg-2 failed ⇒ emergency cleanup, no orphan exposure.
2. **Exit truth**: DB says closed only after exchange-flat confirmation
   (`_confirm_exchange_flat_after_close`); fill data is telemetry, never state.
3. **UTC everywhere**: all windowing/backtests timezone-aware UTC.
4. **Precision before submit**: format sizes/prices with the exchange metadata helpers.
5. **Fail closed**: transport/malformed account data ⇒ no entry (guards propagate errors;
   only the Redis peak-equity store is allowed to skip itself, by design).
6. **No new broad `except Exception`** in decision paths — the ratchet
   (`tests/test_exception_handling_ratchet.py`) must stay flat or drop.

## Quality gates (must pass)

- [ ] Decision logic deterministic (timestamps/iteration order inputs, not environment)
- [ ] Live ↔ backtest parity surfaces updated together (or divergence documented)
- [ ] New settings wired through `arbitrage_runtime_config` typed keys with clamping
- [ ] Rejections observable (counter + reason string) for every new gate
- [ ] Mandated test suites green (see step 7) + full suite + coverage floor
- [ ] Portfolio-risk guard interplay validated when entry behavior changes
- [ ] Runtime settings route contract intact (`tests/test_arbitrage_routes.py`)
- [ ] Docs synced if operator-visible behavior changed (`openapi.json`, README/AGENTS notes)

## Suggested invocation prompts

- `/dydx-pairs-arbitrage Tighten the cointegration sample-size penalty and keep backtest parity.`
- `/dydx-pairs-arbitrage Add a spread-volatility regime filter to entries, default-off flag, with audit reasons.`
- `/dydx-pairs-arbitrage Expose pair-priority ranking scores in the observability snapshot.`
- `/dydx-pairs-arbitrage Investigate why pair BTC/ETH was rejected all day using the audit trail.`
