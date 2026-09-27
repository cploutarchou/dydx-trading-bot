---
description: Audit and improve an AI feature so its suggestions are grounded in real market and strategy data (inputs, units, secrets, model budget), then implement and verify the improvement
argument-hint: "<feature: market-selection | strategy-suggestions | strategy-chat | backtest-explain | runtime-digest | all> [plan-only]"
---

Ground the AI feature "$1" in real data. Mode: "$2" (empty = plan and implement; "plan-only" = stop after the plan).

The platform is a dYdX v4 statistical-arbitrage system: frontend (React) -> backend (Go, owns every
model call) -> bot (Python, owns market data, backtests and the live runtime). Model calls never leave
the backend and the browser never talks to a provider.

## 1. Investigate (read-only)
For the feature, trace the full path and write down file:line evidence:
- Route -> handler -> service -> prompt builder -> provider call -> output parsing -> what the UI does with it.
- Every input the prompt receives today, and where each value comes from (frontend-supplied, backend
  Postgres, bot HTTP). Mark values the model is asked to judge without data (names only, no numbers).
- Data that exists but is not used: market stats from the bot's perpetual-markets payload (volume,
  open interest, price change, funding), candle history, backtest runs of the same strategy
  (`backtest_runs` mirror, bot run details, per-trade rows with pair, P&L, exit reason, duration),
  live trades, positions and realtime stats of the strategy's runtime, entry-halt state.
- Units: percent vs fraction, USD vs notional, hours vs bars. Find every place a value is scaled twice
  or not at all.
- Secrets and identity: anything that could reach the provider (user ids, e-mails, subaccounts,
  addresses, mnemonics, keys, bot config blobs, raw error strings). Also the strategy filters that are
  ignored (for example a query parameter the handler drops).
- Model and budget: model per task, reasoning effort, output-token limit, client timeout, handler
  deadline, retries, and whether a data-rich prompt still fits them.

## 2. Plan
Produce a plan with, for each improvement: the data source (Go function or bot endpoint, cost per
call, freshness), the compact context schema sent to the model (target a few KB; aggregate per pair
and per market, never raw rows), prompt changes, output schema and validation, model/effort/budget
per task, caching, fallbacks when data is missing, tests, and what the UI must show. Rank by user
value and risk; call out anything that needs a contract change across services.

## 3. Implement (unless plan-only)
- Backend first: context builders that pick fields explicitly (allowlists), prompts that cite the data
  and its caveats, structured outputs validated server-side, deterministic fallbacks that use the same
  data. Fix the unit and filter bugs found in step 1. Keep the layering; the bot is read through the
  existing client. Hermetic tests with fake transports for every new path, including missing data.
- Frontend only where the request or response shape changes; keep the existing UI conventions.
- Never send secrets or identity to a provider. Never claim profitability. Fail closed on unknown
  runtime state. No attribution comments or generated-by notes anywhere.

## 4. Verify and report
Run the canonical validation commands for every touched service and quote the real output. Report:
files changed, behaviour delta (before/after inputs of each prompt), evidence, and remaining
uncertainty (for example: not exercised against a live provider).
