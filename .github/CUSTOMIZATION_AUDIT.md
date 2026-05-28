# Customization Audit Report (2026-05)

This document provides a comprehensive assessment of all agents, skills, prompts, and instructions in the dYdX Trading Bot monorepo, with cleanup recommendations.

## Executive Summary

**Status**: ✅ Healthy — The customization setup is well-aligned with project scope. Only minor cleanups recommended.

- **Agents**: All 8 agents are relevant and actively used
- **Skills**: All 6 skills are relevant; 1 already marked deprecated  
- **Prompts**: 12 root + service-specific; 1 candidate for review
- **Instructions**: All are actively used and relevant

## Agents Audit (8 total)

### ✅ Core Platform Agents (Root)

| Agent | Purpose | Status |
|-------|---------|--------|
| `senior-defi-monorepo-platform.agent.md` | Consolidated root agent for cross-service platform work, universal repo tasks, and DeFi trading/quant scope | ✅ Active |
| `senior-prod-backtest-defi-auditor.agent.md` | Production audits, backtest debugging, async task monitoring | ✅ Active |
| `senior-deploy-github-actions.agent.md` | CI/CD, deployments, GitHub Actions workflows | ✅ Active |

**Recommendation**: Keep all. Each serves a distinct audience and problem domain.

### ✅ Service-Specific Agents

| Agent | Service | Purpose | Status |
|-------|---------|---------|--------|
| `backend/.github/agents/senior-go-defi-backend.agent.md` | Backend (Go) | API routes, handlers, services, migrations, delegated bot integration | ✅ Active |
| `bot/.github/agents/senior-python-defi-runtime.agent.md` | Bot (Python) | Runtime lifecycle, FastAPI, backtests, websocket, exchange, execution safety | ✅ Active |
| `frontend/.github/agents/senior-react-defi-product.agent.md` | Frontend (React) | Product UI, dashboards, responsive design, fintech UX | ✅ Active |

**Recommendation**: Keep all. Strong alignment with service ownership model.

---

## Skills Audit (6 total)

### ✅ Core Skills

| Skill | Scope | Status |
|-------|-------|--------|
| `.github/skills/defi-python-algo-trading/SKILL.md` | Python bot trading with quality gates | ✅ Active |
| `.github/skills/deployment-github-actions/SKILL.md` | CI/CD workflow safety and rollout | ✅ Active |
| `backend/.github/skills/go-api-db-crypto-trading/SKILL.md` | Go backend API, DB, crypto trading | ✅ Active |
| `frontend/.github/skills/frontend-live-data-safety/SKILL.md` | Websocket/polling/fallback safety | ✅ Active |
| `frontend/.github/skills/senior-ux-designer/SKILL.md` | Fintech UX for operator surfaces | ✅ Active |

### ⚠️ Deprecated (Already Disabled)

| Skill | Status | Reason |
|-------|--------|--------|
| `frontend/.github/skills/senior-ui-designer/SKILL.md` | ⚠️ Deprecated (disabled) | Alias for `senior-ux-designer`; marked `disable-model-invocation: true` |

**Recommendation**: Remove `senior-ui-designer/SKILL.md` — it's already deprecated and disabled. Clean up the unused directory.

---

## Prompts Audit (12 root + service-specific)

### ✅ Root Prompts (Active)

| Prompt | Purpose | Usage | Status |
|--------|---------|-------|--------|
| `defi-risk-review.prompt.md` | Execution/exposure/slippage/funding/recovery | Trading/audit workflows | ✅ Active |
| `defi-predeploy-go-no-go.prompt.md` | Pre-deploy gate with blockers/mitigations | Release preparation | ✅ Active |
| `defi-incident-hotfix-go-no-go.prompt.md` | Emergency hotfix go/no-go | Incident response | ✅ Active |
| `deploy-go-no-go.prompt.md` | Deployment approval + rollback readiness | Deployment workflows | ✅ Active |
| `github-actions-failure-triage.prompt.md` | Pipeline failure root-cause analysis | CI/CD debugging | ✅ Active |
| `codex-dydx-strategy-suggestions.prompt.md` | AI-driven strategy parameter tuning | Codex optimization | ✅ Active |
| `codex-frontend-ux-polish.prompt.md` | Focused frontend UX/UI improvements | Frontend optimization | ✅ Active |

### ⚠️ Candidate for Review

| Prompt | Purpose | Usage | Status |
|--------|---------|-------|--------|
| `codex-deepseek-usage-optimizer.prompt.md` | DeepSeek model optimization | Specialized/optional | ⚠️ Consider |
| `frontend-job-fields-update.prompt.md` | DB-backed job metadata in UI | Potentially outdated | ⚠️ Consider |

**Recommendations**:
1. Keep `codex-deepseek-usage-optimizer.prompt.md` if DeepSeek is used; otherwise consider removing
2. Verify `frontend-job-fields-update.prompt.md` is current; if outdated, archive or remove

### ✅ Service-Specific Prompts (All Active)

| Prompt | Service | Status |
|--------|---------|--------|
| `backend/.github/prompts/delegated-bot-api-review.prompt.md` | Backend | ✅ Active |
| `backend/.github/prompts/postgres-migration-review.prompt.md` | Backend | ✅ Active |
| `backend/.github/prompts/trading-risk-review.prompt.md` | Backend | ✅ Active |
| `bot/.github/prompts/improve-project.prompt.md` | Bot | ✅ Active |
| `bot/.github/prompts/review-migration.prompt.md` | Bot | ✅ Active |
| `bot/.github/prompts/document-bot-flows.prompt.md` | Bot | ✅ Active |
| `frontend/.github/prompts/fintech-copy-tone.prompt.md` | Frontend | ✅ Active |

**Recommendation**: Keep all. Each is tightly scoped to its service's concerns.

---

## Instructions Audit

### ✅ Root Instructions (Active)

| File | Scope | Status |
|------|-------|--------|
| `.github/copilot-instructions.md` | Cross-repo defaults, architecture, build/test commands | ✅ Active |
| `.github/git-commit-instructions.md` | Commit message and branch naming conventions | ✅ Active |
| `.github/instructions/workflow-yaml.instructions.md` | GitHub Actions workflow safety | ✅ Active |
| `.github/instructions/python-trading.instructions.md` | DEPRECATED (marked as legacy, scoped to `DO_NOT_USE/**`) | ⚠️ Archive |

### ✅ Service-Specific Instructions (All Active)

| File | Service | Status |
|------|---------|--------|
| `backend/.github/copilot-instructions.md` | Backend | ✅ Active |
| `backend/.github/instructions/go-backend-api.instructions.md` | Backend | ✅ Active |
| `backend/.github/instructions/go-tests.instructions.md` | Backend | ✅ Active |
| `bot/.github/copilot-instructions.md` | Bot | ✅ Active |
| `bot/.github/instructions/runtime-safety.instructions.md` | Bot | ✅ Active |
| `bot/.github/instructions/migration-safety.instructions.md` | Bot | ✅ Active |
| `bot/.github/instructions/improvement-output.instructions.md` | Bot | ✅ Active |
| `frontend/.github/copilot-instructions.md` | Frontend | ✅ Active |

**Recommendation**: Keep all active instructions. Archive `python-trading.instructions.md` since it's already marked deprecated.

---

## Cleanup Actions

### Remove (Not Used / Deprecated)

1. **`frontend/.github/skills/senior-ui-designer/SKILL.md`**
   - Already deprecated and disabled
   - Replaced by `senior-ux-designer/SKILL.md`
   - Safe to remove

2. **`.github/instructions/python-trading.instructions.md`**
   - Already marked deprecated in index
   - Scoped to `DO_NOT_USE/**`
   - Safe to remove or archive

### Review & Decide

1. **`.github/prompts/codex-deepseek-usage-optimizer.prompt.md`**
   - Keep if DeepSeek is actively used in codex workflows
   - Remove if not part of active optimization workflow
   - **Recommendation**: Review with team; likely keep for AI optimization flexibility

2. **`.github/prompts/frontend-job-fields-update.prompt.md`**
   - Verify currency of DB-backed job field mapping
   - If outdated, remove or consolidate into `frontend-ux-polish`
   - **Recommendation**: Verify with frontend team; likely keep for now

### Consider Creating (Optional Enhancements)

1. **Config & Infrastructure Skill** (`config-infrastructure-management/SKILL.md`)
   - Focus: encrypted profiles, run.json generation, deployment config, environment management
   - Audience: DevOps, ops, platform engineers
   - **Priority**: Medium (nice to have, not critical)

2. **Observability & Metrics Skill** (`defi-observability-metrics/SKILL.md`)
   - Focus: Prometheus metrics, log aggregation, dashboard setup, health monitoring
   - Audience: Platform, SRE, operators
   - **Priority**: Low (currently not in critical path)

---

## Alignment Matrix: Project Scope → Customization

### Project Functionalities Covered

| Functionality | Agent/Skill | Coverage |
|---------------|-------------|----------|
| Trading strategies & arbitrage | `senior-defi-monorepo-platform`, `defi-python-algo-trading` | ✅ Complete |
| Runtime lifecycle & execution | `senior-python-defi-runtime`, `runtime-safety.instructions` | ✅ Complete |
| Backtesting & performance | `senior-prod-backtest-defi-auditor` | ✅ Complete |
| API & backend orchestration | `senior-go-defi-backend`, `go-api-db-crypto-trading` | ✅ Complete |
| Frontend UX & dashboards | `senior-react-defi-product`, `senior-ux-designer` | ✅ Complete |
| CI/CD & deployments | `senior-deploy-github-actions`, `deployment-github-actions` | ✅ Complete |
| Database & persistence | `go-api-db-crypto-trading`, `postgres-migration-review` | ✅ Complete |
| Live data & websockets | `frontend-live-data-safety`, `delegated-bot-api-review` | ✅ Complete |
| Production audits & risk | `senior-prod-backtest-defi-auditor`, `defi-risk-review` | ✅ Complete |
| Configuration management | None (candidate for new skill) | ⚠️ Partial |
| Observability & metrics | None (candidate for new skill) | ⚠️ Partial |

---

## Final Recommendations

### Priority 1: Immediate Cleanup ✅

1. Remove `frontend/.github/skills/senior-ui-designer/` (deprecated)
2. Archive or remove `.github/instructions/python-trading.instructions.md` (deprecated)

### Priority 2: Review & Validate 📋

1. Confirm `.github/prompts/codex-deepseek-usage-optimizer.prompt.md` usage
2. Verify `.github/prompts/frontend-job-fields-update.prompt.md` currency
3. Ensure all service-specific CUSTOMIZATION_INDEX.md files are current

### Priority 3: Enhancement (Optional) 🚀

1. Consider creating `config-infrastructure-management/SKILL.md` for deployment/config workflows
2. Consider creating `defi-observability-metrics/SKILL.md` for monitoring/SRE workflows

### Priority 4: Documentation 📚

1. Update `.github/CUSTOMIZATION_INDEX.md` to reflect cleanups
2. Add this audit report to version control for future reference
3. Link to this audit from main README.md for transparency

---

## Conclusion

The dYdX Trading Bot monorepo has a **well-designed, focused customization setup** with clear agent/skill ownership aligned to project scope. All active customizations serve concrete purposes. Only minor cleanups are needed to remove deprecated items.

**Overall health: ✅ Excellent**
