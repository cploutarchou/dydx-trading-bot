# .github Customization Index

Use this index to quickly find the agent/instruction/skill/prompt/workflow setup for this repository.

## Start-of-task rule

For each new task, review:

1. `.github/copilot-instructions.md`
2. This file (`.github/CUSTOMIZATION_INDEX.md`)
3. The most relevant skill/agent/prompt listed below

## Core workspace instructions

- `.github/copilot-instructions.md`  
  Cross-repo defaults for architecture, ports, build/test commands, and critical trading safety constraints.

## File-scoped instructions

- `.github/instructions/workflow-yaml.instructions.md`
  GitHub Actions workflow guardrails for explicit triggers, deterministic job ordering, safe secret handling, and StackForge-aware production deployment checks.

## Agents

Root-agent selection:

1. Use `senior-defi-monorepo-platform` for all root-level DeFi monorepo tasks (platform + universal + trading/quant-heavy scope).
2. Prefer service-specific agents (`backend/`, `bot/`, `frontend/`) when scope is single-service.

- `.github/agents/senior-defi-monorepo-platform.agent.md`
  Consolidated root agent mode for platform architecture, universal repo tasks, and DeFi trading/quant work.

- `.github/agents/senior-prod-backtest-defi-auditor.agent.md`
  Agent mode for production-readiness audits, Python/Go service hardening, long-running backtest hangs, and DeFi bot-instance risk reviews.

- `.github/agents/senior-deploy-github-actions.agent.md`
  Agent mode for CI/CD workflow design, deployment safety gates, rollout/rollback planning, and GitHub Actions hardening.

- `.github/agents/senior-stackforge-cli-deployer.agent.md`
  Agent mode for StackForge CLI cluster operations: preflight validation, app+DB deployment with `stackforge deploy`, post-deploy verification, and rollback-safe execution.

- `backend/.github/agents/senior-go-defi-backend.agent.md`
  Service-specific backend expert for Go APIs, PostgreSQL, delegated bot integration, auth, and websocket proxying.

- `bot/.github/agents/senior-python-defi-runtime.agent.md`
  Service-specific bot expert for FastAPI, runtime safety, backtests, websocket streams, and dYdX execution flows.

- `frontend/.github/agents/senior-react-defi-product.agent.md`
  Service-specific frontend expert for React product UX, live dashboards, responsive design, and fintech-grade UI.

## Skills

- `.github/skills/defi-python-algo-trading/SKILL.md`  
  Production-safe Python trading workflow with quality gates:
  - atomic paired execution safety
  - exchange precision handling
  - UTC-safe datetime usage
  - async API correctness
  - risk/DeFi/performance validation

- `.github/skills/deployment-github-actions/SKILL.md`
  Deployment and GitHub Actions workflow for CI/CD reliability and safe rollout:
  - deterministic job dependencies and failure gating
  - branch/environment trigger safety
  - secret/config handling hygiene
  - rollback-aware deployment validation

- `.github/skills/config-infrastructure-management/SKILL.md`
  Runtime configuration, encrypted profiles, deployment config, environment management, infrastructure-as-code:
  - encrypted profile design and management
  - run.json generation and validation
  - Docker/Compose infrastructure
  - secrets and credentials handling

- `.github/skills/defi-observability-metrics/SKILL.md`
  Observability, metrics, logging, dashboards, health monitoring, and alerting for trading platform:
  - Prometheus metrics and custom counters
  - Grafana dashboards and operator visibility
  - structured logging and trace correlation
  - alerting thresholds and runbooks

## Prompts

- `.github/prompts/defi-risk-review.prompt.md`  
  Focused risk review (execution, exposure, slippage/liquidity, funding, recovery).

- `.github/prompts/defi-predeploy-go-no-go.prompt.md`  
  Pre-deploy go/no-go gate with blockers and mitigations.

- `.github/prompts/defi-incident-hotfix-go-no-go.prompt.md`  
  Incident-mode emergency go/no-go gate.

- `.github/prompts/deploy-go-no-go.prompt.md`
  StackForge-aware deployment approval gate for CI/CD, release, rollback readiness, and operator go/no-go decisions.

- `.github/prompts/stackforge-deploy-go-no-go.prompt.md`
  StackForge CLI app+API+DB deployment gate that checks preflight evidence, production safety flags, deploy manifest/env integrity, and rollback/restore readiness.

- `.github/prompts/stackforge-post-deploy-verify.prompt.md`
  StackForge post-deploy verification gate that returns PASS/FAIL from cluster/component health, app/API smoke checks, DB safety, config drift, and rollback confidence.

- `.github/prompts/stackforge-incident-verify.prompt.md`
  Incident-mode StackForge verification gate that returns PASS_NOW/FAIL_NOW with critical blockers, minimum immediate actions, 30-minute safeguards, and explicit rollback triggers.

- `.github/prompts/github-actions-failure-triage.prompt.md`
  Focused GitHub Actions / release pipeline failure triage with root-cause, retry posture, and smallest-safe-fix guidance.

- `.github/prompts/codex-dydx-strategy-suggestions.prompt.md`
  Codex command for dYdX strategy-aware AI parameter suggestion tuning.

## Workflow automation

- `.github/workflows/ci.yml`  
  CI checks for Python lint/tests, Go WS smoke tests, and Docker image smoke validation.

## Additional repo guidance

- `.github/git-commit-instructions.md`  
  Commit message, branch naming, and PR hygiene guidance.

## Latest high-impact context (2026-05)

- Frontend backtest operational UX is concentrated in `frontend/src/pages/Backtests.tsx` and `frontend/src/components/StrategyManager.tsx`.
- Backend backtest delegation and normalization behavior is concentrated in `backend/internal/routes/bot_api_delegate_routes.go`.
- Recent index migrations were adjusted for transaction-safe execution in:
  - `backend/migrations/postgres/000047_backtest_list_perf_index.up.sql`
  - `backend/migrations/postgres/000051_phase1_missing_indexes.{up,down}.sql`
  - `backend/migrations/postgres/000053_phase4_drop_redundant_indexes.up.sql`

## Customization Audit (2026-05)

- Removed deprecated `frontend/.github/skills/senior-ui-designer/` (superseded by `senior-ux-designer`)
- Removed deprecated `.github/instructions/python-trading.instructions.md`
- Added `.github/skills/config-infrastructure-management/SKILL.md` for config/deployment workflows
- Added `.github/skills/defi-observability-metrics/SKILL.md` for metrics/monitoring/observability
- See `.github/CUSTOMIZATION_AUDIT.md` for full audit report
