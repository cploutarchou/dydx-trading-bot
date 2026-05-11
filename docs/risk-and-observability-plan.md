# Risk And Observability Plan

## Preserved Risk Logic

- Atomic two-leg open semantics.
- Emergency cleanup when second leg fails.
- Reduce-only exit retries.
- Orphaned leg recovery.
- Collateral and collateral-buffer checks.
- Min order size checks.
- Precision formatting.
- Z-score crossing exit logic.

## Added Visibility

- Scan cycle ID in live entry logs.
- Pair-level skip/rejection reasons.
- Opportunity detected/rejected/executed counters.
- Cache hit/miss and saved-call counters.
- Stale pair-analysis counter.
- Bot `/metrics` endpoint for backend probing.
- Bot `/api/v1/arbitrage/improvement-metrics` and `/api/v1/arbitrage/pair-priority` endpoints.
- Authenticated backend proxy routes for the arbitrage diagnostics endpoints.
- Frontend bot-manager panel for feature-flag state, saved-call counters, and pair-priority explanations.
- Admin-only `Settings -> Arbitrage Runtime` controls backed by `bot_settings` and synchronized to the bot runtime.
- Audit logs for admin arbitrage runtime setting updates, including changed keys and bot sync status.

## Secure Storage Model

- Non-secret arbitrage toggles and numeric tuning values live in `bot_settings` section `arbitrage`.
- dYdX addresses and mnemonics stay in the existing encrypted dYdX key storage.
- Provider API keys stay in `external_api_credentials` through the existing encrypted credential service.
- User login credentials remain in the existing auth tables and must not be copied into runtime settings.

## Future Safe Additions

- Net-profit estimate logs after fees/slippage before execution.
- Stale-price guard behind `AUTO_EXECUTION_CHANGES_ENABLED`.
- Single account snapshot per opportunity.
- Abnormal spread detector behind a non-execution flag first.

## Rollback

Set all feature flags false in `Settings -> Arbitrage Runtime` or in env defaults, then save and sync.
The added logs, metrics, and settings rows are passive and do not require schema rollback.
