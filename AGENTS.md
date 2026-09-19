# AGENTS.md

Repository-level startup guidance for coding agents working in this monorepo.

> ZCode loads ONLY this workspace-root file (plus the user-global
> `~/.zcode/AGENTS.md`); it does not merge child `AGENTS.md` files, follow
> imports, or pick rule files by task. Service-specific detail lives in the
> expert-system profiles linked below — read the relevant one before changing
> that service. The `.github/*` files referenced here are used by other
> agent toolchains (Copilot/Claude) and remain useful reading.

## Start every new task with this checklist

1. Read `.github/copilot-instructions.md`
2. Read `.github/CUSTOMIZATION_INDEX.md`
3. Load and apply the most relevant skill/agent/prompt from the index before implementation
4. Read the expert-system service profile for every service you will touch:
   `zcode-marketplace/plugins/monorepo-experts/references/`

## Monorepo purpose and topology

Self-hosted statistical-arbitrage trading system for dYdX v4 perpetuals with
a web control plane. Strict one-directional boundary:
`frontend/ (React :5173) -> backend/ (Go :8888) -> bot/ (Python :8889) ->
workers + infra (Postgres/Valkey/NATS/ClickHouse/MinIO)`. Never bypass a
layer. Correctness ≠ profitability — never claim the strategy is profitable.

## Package managers and orchestration rules

- Root `Makefile` is the canonical orchestration entry (stack, infra, config,
  migrations, images). No Nx/Turborepo.
- `bot/`: Python 3.12 + uv (`uv.lock`, `requirements.txt`).
- `backend/`: Go modules (`go.mod`/`go.sum`).
- `frontend/`: npm (`package-lock.json`, Node 26).
- Tested and shipped toolchains move together: `backend/go.mod` with the `golang:` image tags, CI `node-version`
  with the `node:` image tag (`python3 scripts/check_toolchain_drift.py`, enforced in CI).
- Dependencies stay pinned per area; no lockfile churn without a dedicated,
  explained change; never install packages just to complete a task.

## Universal engineering conventions

- Evidence-first: verify claimed facts in code before asserting them;
  distinguish observed facts from inferences in every report.
- Smallest complete change; follow each service's conventions (profile
  details); UTC-aware datetimes; awaited async calls; parameterized SQL.
- No unrelated refactoring — diffs stay scoped to the task.
- Completion reports must be evidence-backed: files changed, behavior delta,
  exact commands run with their real results, and remaining uncertainty.
  Never claim a test passed that was not run.

## Canonical validation commands

| Scope | Command(s) |
| --- | --- |
| Bot | `cd bot && python -m pytest tests/ --ignore=tests/test_api_database_integration.py --ignore=tests/test_comprehensive.py --cov=src --cov-fail-under=82` ; `python -m isort --check-only src tests && python -m black --check src tests && python -m flake8 src tests --select=E9,F63,F7,F82` ; `python -m mypy src` |
| Backend | `cd backend && go build ./... && go vet ./... && go test -race -count=1 ./...` |
| Frontend | `cd frontend && npm run lint && npm run typecheck && npm run test:contracts && npm run build` |
| Docs | `make docs-governance` |
| Infra | `docker compose -f docker-compose.infra.yml config` ; `docker compose -f docker-compose.stack.yml config` ; `python3 scripts/check_toolchain_drift.py` |

The bot suite is hermetic (conftest-enforced); safe to run with local infra up.

## Generated-file and security-sensitive boundaries

- Never hand-edit: `run.json` (generated from encrypted profiles via
  `make dev`), `bot/openapi.json` (regenerate), `bot_states/**` runtime
  state, build outputs (`dist/`, `coverage.out`, caches).
- Never commit or print: `.configkey.bin`, mnemonics, API keys, tokens,
  `.env` values. Credentials live only in encrypted stores.
- Live-trading safety: never place/modify/cancel real orders and never
  connect to a live account without explicit user authorization. Tests use
  fakes. Never run migrations against shared/production databases.
- Fail-closed is the house rule for unknown order/position/balance states.

## Service routing table (read the profile before changing the service)

| Service | Profile (under `zcode-marketplace/plugins/monorepo-experts/references/`) | Specialist agent | Skill |
| --- | --- | --- | --- |
| bot/ (Python trading runtime) | `bot-service.md` | bot-trading-expert | $bot-trading-service |
| backend/ (Go gateway) | `backend-service.md` | backend-go-expert | $backend-gateway-service |
| frontend/ (React dashboard) | `frontend-service.md` | frontend-react-expert | $frontend-dashboard-service |
| Platform/infra/config | `platform-infra.md` | platform-cicd-specialist | $monorepo-architecture |
| Data + migrations | `data-migrations.md` | monorepo-principal-architect | $db-migrations |
| CI/release | `ci-release.md` | platform-cicd-specialist | $ci-release-analysis |
| Cross-service / contracts | `monorepo-map.md` | monorepo-principal-architect | $monorepo-architecture |

Review/quality agents: appsec-specialist, dependency-boundary-reviewer,
test-quality-specialist, docs-contracts-specialist. Commands:
`/monorepo-check`, `/service-check <svc>`, `/service-change <svc> <req>`,
`/architecture-review`, `/security-review`, `/test-plan`, `/docs-check`,
`/refresh-monorepo-experts`. All are provided by the local `monorepo-experts`
plugin (`zcode-marketplace/`); a new ZCode session is required after
installing or changing it.

## Primary customization files (other toolchains)

- Workspace defaults: `.github/copilot-instructions.md`
- Customization index: `.github/CUSTOMIZATION_INDEX.md`
- Consolidated root agent (platform + universal + trading/quant): `.github/agents/senior-defi-monorepo-platform.agent.md`
- Python trading skill: `.github/skills/defi-python-algo-trading/SKILL.md`
- Service indexes:
  - `backend/.github/CUSTOMIZATION_INDEX.md`
  - `bot/.github/CUSTOMIZATION_INDEX.md`
  - `frontend/.github/CUSTOMIZATION_INDEX.md`
- Risk/deploy prompts: `.github/prompts/*.prompt.md`

## Operating notes

- Treat this file as a startup pointer; keep details in `.github/*` customization files.
- If there is any conflict, prefer the more specific instruction file for the affected scope.

## Latest platform context (2026-05)

- Integration boundary remains strict: `frontend -> backend -> bot`.
- Frontend now has a dedicated `Backtests` intelligence surface with dashboard/new/runs views and an **Active Runs Quick Access** panel with live status polling + freshness indicators.
- Strategy operations UX is centered in `frontend/src/components/StrategyManager.tsx` with runtime heartbeat visibility and operator/analyst density presets.
- Backend delegated backtest routes in `backend/internal/routes/bot_api_delegate_routes.go` normalize status/progress fields for compatibility and expose DB-backed backtest list responses via `backtest_runs`.
- Recent MariaDB migrations were hardened for explicit deployment execution; do not depend on startup schema changes.
