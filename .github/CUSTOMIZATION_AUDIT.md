# Customization Audit Report (2026-05)

This document summarizes the customization state for the dYdX Trading Bot monorepo.

## Executive Summary

- Status: ✅ Healthy
- Agents: Core platform and service agents are relevant and actively used
- Skills: Active skills are relevant; deprecated aliases were removed
- Prompts: Root and service-specific prompts are aligned to current workflows
- Instructions: Active instruction files are relevant

## Agents Audit

### Core platform agents

- `senior-defi-monorepo-platform.agent.md`
  - Purpose: cross-service platform work, universal repo tasks, DeFi trading/quant scope
  - Status: ✅ Active
- `senior-prod-backtest-defi-auditor.agent.md`
  - Purpose: production audits, backtest debugging, async task monitoring
  - Status: ✅ Active

Recommendation: keep both.

### Service-specific agents

- `backend/.github/agents/senior-go-defi-backend.agent.md`
  - Service: backend (Go)
  - Purpose: API routes, handlers, services, migrations, delegated bot integration
  - Status: ✅ Active
- `bot/.github/agents/senior-python-defi-runtime.agent.md`
  - Service: bot (Python)
  - Purpose: runtime lifecycle, FastAPI, backtests, websocket, exchange, execution safety
  - Status: ✅ Active
- `frontend/.github/agents/senior-react-defi-product.agent.md`
  - Service: frontend (React)
  - Purpose: product UI, dashboards, responsive design, fintech UX
  - Status: ✅ Active

Recommendation: keep all service-specific agents.

## Skills Audit

### Core skills

- `.github/skills/defi-python-algo-trading/SKILL.md`
  - Scope: Python bot trading quality gates
  - Status: ✅ Active
- `backend/.github/skills/go-api-db-crypto-trading/SKILL.md`
  - Scope: Go backend API, DB, crypto trading
  - Status: ✅ Active
- `frontend/.github/skills/frontend-live-data-safety/SKILL.md`
  - Scope: websocket/polling/fallback safety
  - Status: ✅ Active
- `frontend/.github/skills/senior-ux-designer/SKILL.md`
  - Scope: fintech UX for operator surfaces
  - Status: ✅ Active

### Deprecated skill references

- `frontend/.github/skills/senior-ui-designer/SKILL.md`
  - Status: ⚠️ Deprecated
  - Reason: alias for `senior-ux-designer`

Recommendation: keep active skills only.

## Prompts Audit

### Root prompts

- `defi-risk-review.prompt.md`
  - Purpose: execution/exposure/slippage/funding/recovery review
  - Status: ✅ Active
- `codex-dydx-strategy-suggestions.prompt.md`
  - Purpose: strategy parameter tuning
  - Status: ✅ Active
- `codex-frontend-ux-polish.prompt.md`
  - Purpose: focused frontend UX/UI improvements
  - Status: ✅ Active

### Candidate prompts to review

- `codex-deepseek-usage-optimizer.prompt.md`
  - Purpose: DeepSeek model optimization
  - Status: ⚠️ Consider
- `frontend-job-fields-update.prompt.md`
  - Purpose: DB-backed job metadata updates
  - Status: ⚠️ Consider

Recommendations:

1. Keep `codex-deepseek-usage-optimizer.prompt.md` only if actively used.
2. Verify `frontend-job-fields-update.prompt.md` is current.

### Service-specific prompts

- `backend/.github/prompts/delegated-bot-api-review.prompt.md` — ✅ Active
- `backend/.github/prompts/mysql-migration-review.prompt.md` — ✅ Active
- `backend/.github/prompts/trading-risk-review.prompt.md` — ✅ Active
- `bot/.github/prompts/improve-project.prompt.md` — ✅ Active
- `bot/.github/prompts/review-migration.prompt.md` — ✅ Active
- `bot/.github/prompts/document-bot-flows.prompt.md` — ✅ Active
- `frontend/.github/prompts/fintech-copy-tone.prompt.md` — ✅ Active

Recommendation: keep all service-specific prompts.

## Instructions Audit

### Root instructions

- `.github/copilot-instructions.md` — ✅ Active
- `.github/git-commit-instructions.md` — ✅ Active
- `.github/instructions/workflow-yaml.instructions.md` — ✅ Active
- `.github/instructions/python-trading.instructions.md` — ⚠️ Deprecated reference

### Service-specific instructions

- `backend/.github/copilot-instructions.md` — ✅ Active
- `backend/.github/instructions/go-backend-api.instructions.md` — ✅ Active
- `backend/.github/instructions/go-tests.instructions.md` — ✅ Active
- `bot/.github/copilot-instructions.md` — ✅ Active
- `bot/.github/instructions/runtime-safety.instructions.md` — ✅ Active
- `bot/.github/instructions/migration-safety.instructions.md` — ✅ Active
- `bot/.github/instructions/improvement-output.instructions.md` — ✅ Active
- `frontend/.github/copilot-instructions.md` — ✅ Active

Recommendation: keep active instructions and archive deprecated references.

## Coverage Snapshot

- Trading strategies and arbitrage — ✅ Complete
- Runtime lifecycle and execution — ✅ Complete
- Backtesting and audits — ✅ Complete
- API and backend orchestration — ✅ Complete
- Frontend UX and dashboards — ✅ Complete
- CI/CD and deployments — ✅ Complete (core workflows + repo checks)
- Database and persistence — ✅ Complete
- Live data and websockets — ✅ Complete
- Production audits and risk — ✅ Complete
- Configuration management — ⚠️ Partial (candidate area)
- Observability and metrics — ⚠️ Partial (candidate area)

## Final Recommendations

### Priority 1 (complete)

1. Remove deprecated UI-designer alias skill.
2. Archive/remove deprecated Python-trading instruction reference.

### Priority 2 (review)

1. Confirm DeepSeek optimizer prompt usage.
2. Validate job-fields prompt currency.
3. Ensure service-level customization indexes remain up to date.

### Priority 3 (optional enhancement)

1. Continue strengthening config/infrastructure coverage.
2. Continue strengthening observability/metrics coverage.

## Conclusion

Customization is in good shape and aligned with current repo workflows.
