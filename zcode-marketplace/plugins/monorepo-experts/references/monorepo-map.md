# Monorepo Map — dydx-trading-bot

Source of truth for topology. Read this before any cross-service change.
Sibling profiles: `bot-service.md`, `backend-service.md`, `frontend-service.md`,
`platform-infra.md`, `data-migrations.md`, `ci-release.md` (same directory).

## Purpose

Self-hosted statistical-arbitrage trading system for dYdX v4 perpetuals with a
web control plane. Software correctness ≠ profitability; never claim the
strategy is profitable from test results.

## Topology and strict integration boundary

```
frontend/ (React 19 + TS + Vite, dev :5173)
  -> backend/ (Go 1.26 / Gin API gateway, :8888)
       -> bot/ (Python 3.12 FastAPI control plane, :8889)
            -> per-instance worker processes + infra (Postgres, Valkey, NATS, ClickHouse, MinIO)
```

The boundary is one-directional: `frontend -> backend -> bot`. Never let
frontend call the bot API directly or backend import bot code.

## Orchestration and package managers

- Root `Makefile` is the canonical orchestration entry (stack, infra, config,
  migrations, backtests). No Nx/Turborepo/Lerna; three independent package
  areas:
  - `bot/`: uv-managed (`uv.lock`, `requirements.txt`, Python 3.12 only)
  - `backend/`: Go modules (`go.mod`/`go.sum`)
  - `frontend/`: npm (`package.json`/`package-lock.json`, Node 24)

## Canonical validation matrix (derived from CI + service configs)

| Scope | Command(s) | Gate |
| --- | --- | --- |
| Bot unit+integration | `cd bot && python -m pytest tests/ --ignore=tests/test_api_database_integration.py --ignore=tests/test_comprehensive.py --cov=src --cov-fail-under=82` | blocking |
| Bot format/lint | `cd bot && python -m isort --check-only src tests && python -m black --check src tests && python -m flake8 src tests --select=E9,F63,F7,F82` | blocking |
| Bot types | `cd bot && python -m mypy src` (0-error baseline) | blocking |
| Backend | `cd backend && go build ./... && go vet ./... && go test -race -count=1 ./...` | blocking |
| Backend lint | `cd backend && golangci-lint run ./...` (config v2) | reporting-only (phase 1) |
| Frontend | `cd frontend && npm run lint && npm run typecheck && npm run test:contracts && npm run build` | blocking (lint has --max-warnings 0) |
| Docs | `make docs-governance` (runs `scripts/validate_docs_governance.py`) | blocking in CI |
| K8s secrets | `python3 scripts/check_no_plaintext_k8s_secrets.py` | blocking |

The bot suite is hermetic (conftest forces `.ci-run.json`, closed-port DB,
artifact gates off, file-mode tracked state); it is safe with local infra up.

## Security-sensitive boundaries (never edit by hand, never print values)

- `run.json` (generated), `.configkey.bin`, `config/profiles/*.config.enc.json`
  (encrypted). Regenerate via `make dev` / `make config-keygen`.
- `bot/bot_states/`, `bot_states/` runtime state; per-instance isolation.
- Secrets: mnemonics/API keys live only in encrypted stores; logs and test
  output must never contain them.
- Live-trading safety: never place/cancel real orders, never connect to live
  accounts without explicit authorization; tests use fakes only.

## Dependency-change rules

- Pin as the repos already do (bot via requirements/uv; frontend exact-ish
  semver; backend go.mod). No lockfile churn without a dedicated, explained
  change. Never install packages just to complete a task.

## Service routing table

| Service | Profile | Implementation skill | Specialist agent | Review agent |
| --- | --- | --- | --- | --- |
| bot/ (Python trading runtime) | bot-service.md | bot-trading-service | bot-trading-expert | appsec-specialist, test-quality-specialist |
| backend/ (Go gateway) | backend-service.md | backend-gateway-service | backend-go-expert | appsec-specialist, dependency-boundary-reviewer |
| frontend/ (React dashboard) | frontend-service.md | frontend-dashboard-service | frontend-react-expert | docs-contracts-specialist |
| Platform/infra/config | platform-infra.md | monorepo-architecture | platform-cicd-specialist | dependency-boundary-reviewer |
| Data + migrations | data-migrations.md | db-migrations | monorepo-principal-architect | — |
| CI/release | ci-release.md | ci-release-analysis | platform-cicd-specialist | — |

## Cross-service coordination

API contracts move in lockstep: `bot/openapi.json` (bot), backend delegated
routes (`backend/internal/routes/bot_api_delegate_routes.go`), frontend API
client (`frontend/src/api.ts`). A contract change requires coordinated
updates in the same change set. Behavior changes update the owning service's
docs in the same commit (governance enforced by `make docs-governance`).

## Evidence sources

Root `Makefile`, `.github/workflows/bot-quality.yml`, `bot/pyproject.toml`,
`backend/go.mod`, `frontend/package.json`, `docker-compose.*.yml`, root
`AGENTS.md` history, repo docs tree (`docs/`).
