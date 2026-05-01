# dYdX Trading Bot — Workspace Instructions

Use this file for cross-repo defaults. Keep edits concise, actionable, and current.

## Task startup checklist

For each new task, first consult:

1. `.github/copilot-instructions.md`
2. `.github/CUSTOMIZATION_INDEX.md`
3. Any relevant skill/agent/prompt listed in the index

Preferred agent selection:

- root or cross-service work: `.github/agents/senior-defi-monorepo-platform.agent.md`
- trading/quant-heavy mixed-stack work: `.github/agents/senior-defi-dev.agent.md`
- backend-only work: `backend/.github/agents/senior-go-defi-backend.agent.md`
- bot-only work: `bot/.github/agents/senior-python-defi-runtime.agent.md`
- frontend-only work: `frontend/.github/agents/senior-react-defi-product.agent.md`

## Architecture

This is a monorepo with 3 practical areas:

- `bot/` (active): Python FastAPI control plane + async trading worker (`bot/src/main_instance.py`)
- `frontend/` (active): React + TypeScript + Vite dashboard
- `backend/` (active): Go API gateway/orchestration layer used by the UI and delegating bot actions to Python Bot API

Current integration path is: `frontend` → Go backend in `backend/` → Python API in `bot/` → worker subprocesses + DB/Redis.

## Build and test

Prefer these canonical commands:

- Runtime config prep: `make config-keygen` (first-time), `make dev-config`, `make dev` (generates repo-root `run.json`)
- Root stack: `make stack-up-dev`, `make stack-ps`, `make stack-logs`, `make stack-down`
- Infra-only daily flow: `make infra-up`, `make infra-ps`, `make infra-logs`, `make infra-down`
- Bot API (local): from `bot/`, run `python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8889 --reload`
- Bot worker (local): from `bot/`, run `python src/main_instance.py --instance-id "bot-1"`
- Bot tests: `python -m pytest bot/tests/ -v`
- Frontend: from `frontend/`, run `npm run dev`, `npm run lint`, `npm run build`
- Go backend (if touching it): from `backend/`, run `make test`, `make lint`, `make build`

Configuration source of truth:

- Prefer encrypted profiles in `config/profiles/*.config.enc.json` + generated `run.json`.
- Treat repo-root `.env` as legacy/deprecated unless a specific task explicitly requires it.

Default dev ports in this repo:

- Frontend: `5173`
- Go Backend API: `8888`
- Python Bot API: `8889` in stack/dev workflows (some standalone scripts/docs may still mention `8000`)

## Python trading conventions (critical)

When editing `bot/src/**`, follow these rules:

1. Configuration flow: env/config loader → `bot/src/constants.py` → runtime imports.
   - Import constants in hot paths; avoid repeated config parsing.
2. Load `.env` before config-dependent imports in executable entry points.
3. dYdX/API interactions are async: always `await` client calls.
4. Paired execution must remain atomic:
   - if leg 1 fills and leg 2 fails, trigger emergency cleanup of leg 1.
5. Exchange precision safety:
   - format numeric order inputs with existing precision helpers before submission.
6. Backtesting/time comparisons must use timezone-aware UTC timestamps.

## State and persistence

- Runtime state is primarily file-backed under `bot/bot_states/` (per-instance files) plus DB/Redis.
- Preserve per-instance isolation; do not mix state files across instance IDs.
- Prefer existing repository/service patterns for DB writes over ad-hoc SQL.

## Key files to learn patterns fast

- `bot/src/main_instance.py` — worker orchestration + startup sequencing
- `bot/src/trading/bot_agent.py` — atomic pair execution + emergency cleanup
- `bot/src/constants.py` — runtime config constants
- `bot/src/api/server.py` — API assembly and routers
- `frontend/src/api.ts` — API client, auth token handling, interceptors
- `README.md` — monorepo stack and service roles

## Pitfalls to avoid

- Stale paths from older docs (`app/...`, `bot_api_server.py`) — prefer `bot/src/...` paths.
- Mixing port assumptions (`8888` vs `8889` or `8000`) without checking target workflow.
- Missing `await` on async trading/API methods.
- Breaking atomic two-leg trade safety.
- Deprecated command drift (`stack-env`, `env-setup`, `db-*` aliases, `worker-run`) — prefer canonical targets in root `Makefile`.
- Behavior/doc drift: when behavior changes, update linked service docs in the same PR.

## Key reference docs (link, don't embed)

- Monorepo runtime and workflows: `README.md`
- Customization map: `.github/CUSTOMIZATION_INDEX.md`
- Bot deep guidance: `bot/.github/copilot-instructions.md`, `bot/README.md`
- Backend deep guidance: `backend/.github/copilot-instructions.md`, `backend/README.md`, `backend/tasks.md`
- Frontend deep guidance: `frontend/.github/copilot-instructions.md`, `frontend/README.md`, `frontend/docs/architecture/README.md`
- Specialized customization: `.github/skills/defi-python-algo-trading/SKILL.md`, `.github/agents/senior-defi-dev.agent.md`, `.github/prompts/*.prompt.md`

## Scope guidance

- Keep this file minimal and cross-cutting.
- Put area-specific details in:
  - `bot/.github/copilot-instructions.md`
  - `frontend/.github/copilot-instructions.md`
  - `backend/.github/copilot-instructions.md`

## Recent implementation snapshot (2026-05)

- Frontend backtest UX now emphasizes a dedicated dashboard flow in `frontend/src/pages/Backtests.tsx` with live active-run quick access (status + progress + freshness cues).
- Frontend strategy runtime UX in `frontend/src/components/StrategyManager.tsx` includes heartbeat-driven runtime health surfaces and activity cues for operators.
- Backend delegated backtest contract normalization is centralized in `backend/internal/routes/bot_api_delegate_routes.go` (status/progress aliasing and envelope normalization).
- Backend migration posture assumes transaction-safe SQL for startup migrations; avoid `CONCURRENTLY`-only operations in migration files used by standard startup flow.
