# Improvements Roadmap

This file is the implementation backlog derived from the current canonical documentation set:

- [README.md](/home/chris/workspace/dydx-trading-bot/README.md)
- [docs/PLATFORM.md](/home/chris/workspace/dydx-trading-bot/docs/PLATFORM.md)
- [backend/README.md](/home/chris/workspace/dydx-trading-bot/backend/README.md)
- [bot/README.md](/home/chris/workspace/dydx-trading-bot/bot/README.md)
- [frontend/README.md](/home/chris/workspace/dydx-trading-bot/frontend/README.md)

The goal is to move the platform from “working integrated stack” to “production-ready DeFi product and runtime”.

## Execution Rule

Implement these items one by one using the matching expert profile:

- cross-service/platform work:
  [senior-defi-monorepo-platform.agent.md](/home/chris/workspace/dydx-trading-bot/.github/agents/senior-defi-monorepo-platform.agent.md)
- backend work:
  [senior-go-defi-backend.agent.md](/home/chris/workspace/dydx-trading-bot/backend/.github/agents/senior-go-defi-backend.agent.md)
- bot work:
  [senior-python-defi-runtime.agent.md](/home/chris/workspace/dydx-trading-bot/bot/.github/agents/senior-python-defi-runtime.agent.md)
- frontend work:
  [senior-react-defi-product.agent.md](/home/chris/workspace/dydx-trading-bot/frontend/.github/agents/senior-react-defi-product.agent.md)

## Priority Order

### P0. Platform Contract and Runtime Safety

1. [x] Frontend-to-backend-only contract audit
Owner: monorepo platform + frontend + backend
Why: this is the most important architectural rule in the docs and must stay locked.
Deliverables:
- audit all frontend HTTP and websocket entry points
- remove any remaining direct bot assumptions or hardcoded bot-origin helpers
- add a contract-lock checklist or tests for backend-only communication
Status:
- completed 2026-04-10
- audited frontend HTTP and websocket entry points against backend-origin helpers
- removed stale direct-websocket instruction drift from frontend guidance
- tightened frontend origin tests to lock backend-only websocket routing

2. End-to-end live strategy launch safety
Owner: monorepo platform + bot + backend + frontend
Why: the platform can launch strategies, but operator safety needs a stronger deployment flow.
Deliverables:
- finish the live deployment readiness panel
- show selected environment, credential presence, subaccount, collateral, trade size, and blockers
- prevent unsafe starts when readiness fails

3. Runtime contract and websocket resilience coverage
Owner: backend + bot + frontend
Why: the product now depends heavily on websocket-first behavior.
Deliverables:
- stronger tests for progress streams, reconnect behavior, stale socket recovery, and fallback HTTP recovery
- contract-lock coverage for key backtest and strategy runtime payloads

4. Dedicated database ownership hardening
Owner: backend + bot
Why: the docs establish separate backend and bot databases, so this should be enforced and observable.
Deliverables:
- startup validation that blocks accidental shared-DB regressions
- better health diagnostics for backend DB vs bot DB
- operator documentation for cutover and rollback

### P1. Trading and Execution Readiness

5. Testnet and mainnet live deployment workflow
Owner: bot + backend + frontend
Why: the docs now support environment-aware launches, but the operator workflow can be safer and clearer.
Deliverables:
- explicit environment selection every time a strategy is launched
- network-aware credential validation
- clearer testnet vs production risk messaging in UI

6. Capital allocation and subaccount management
Owner: bot + backend
Why: runtime readiness checks exist, but collateral management is still partly operational/manual.
Deliverables:
- improved per-strategy capital allocation model
- better available collateral display and guardrails
- explicit handling for insufficient funds and minimum collateral buffers

7. Live runtime reconciliation and fail-safe behavior
Owner: bot + backend
Why: production readiness depends on restart, recovery, and state reconciliation.
Deliverables:
- stronger reconciliation after restarts
- better dead-worker detection and operator-visible recovery state
- explicit incident-safe runtime statuses

### P1. Product and Commercial Platform

8. Profit-share subscriptions as a real product flow
Owner: monorepo platform + backend + frontend
Why: the website now communicates profit-only pricing, but product enforcement is not real yet.
Deliverables:
- backend subscription model
- frontend billing/subscription state
- gating for live and premium features

9. Public website conversion and trust layer
Owner: frontend
Why: the site looks better now, but still needs the trust, conversion, and clarity expected from a DeFi platform.
Deliverables:
- stronger enterprise/trust/compliance content
- better subscription funnel and onboarding flow
- clearer risk disclosures and “how it works” sections

### P1. Operator UX and Product Quality

10. Terminal-grade tables across the whole workspace
Owner: frontend
Why: backtest tables improved, but the same product standard should apply across all live surfaces.
Deliverables:
- unified fintech data-grid patterns for Strategy Runtime, Bot Manager, dashboards, and history views
- filters, pagination, density controls, export actions, and better empty states

11. Unified charting system
Owner: frontend
Why: the UI direction is production DeFi, and chart behavior should feel consistent everywhere.
Deliverables:
- standardize on `lightweight-charts` where it adds real trading value
- shared chart wrapper patterns for live data, overlays, markers, and period filters
- remove older charting inconsistencies page by page

12. Full mobile and tablet operating quality
Owner: frontend
Why: the docs commit to responsive design across device classes.
Deliverables:
- review all major authenticated routes at mobile/tablet breakpoints
- improve command palette, tables, filters, and chart usability on smaller screens
- finish screenshot-based responsive signoff process

### P2. Observability, Operations, and Governance

13. Platform observability baseline
Owner: backend + bot
Why: production-readiness depends on fast debugging across services.
Deliverables:
- consistent health, readiness, and trace visibility
- dashboard-quality operational metrics for live runtimes and backtests
- better websocket and upstream delegation diagnostics

14. CI and integration confidence
Owner: monorepo platform + backend + bot + frontend
Why: many of the critical guarantees are cross-service and should be enforced automatically.
Deliverables:
- targeted end-to-end smoke coverage for strategy start, backtest run, live progress, and readiness checks
- stronger contract-lock CI for frontend-facing routes

15. Documentation automation and discipline
Owner: monorepo platform
Why: we just cleaned up docs; now we need to keep them clean.
Deliverables:
- doc-update checklist tied to service behavior changes
- link validation for canonical docs
- explicit archival rules for temporary task/handoff docs

## Recommended Implementation Sequence

1. P0.1 Frontend-to-backend-only contract audit
2. P0.2 End-to-end live strategy launch safety
3. P0.3 Runtime contract and websocket resilience coverage
4. P0.4 Dedicated database ownership hardening
5. P1.5 Testnet and mainnet live deployment workflow
6. P1.6 Capital allocation and subaccount management
7. P1.10 Terminal-grade tables across the whole workspace
8. P1.11 Unified charting system
9. P1.8 Profit-share subscriptions as a real product flow
10. P2.13 Platform observability baseline

## Definition of Done

An item is complete only when:

- the owning service code is updated
- the affected contract or UI behavior is verified
- the relevant service README or root docs are updated
- the change preserves the documented service boundary:
  `frontend -> backend -> bot`
