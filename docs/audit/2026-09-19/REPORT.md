# Audit report — dydx-trading-bot — 2026-09-19

Branch `audit/2026-09-19-all` from `master` @ `24eb752b`. Full detail: `MASTER-PLAN.md`, `plans/`, `findings/`, `LOG.md`, `OPEN-QUESTIONS.md`.

## 1. Repository architecture discovered

Self-hosted statistical-arbitrage system for dYdX v4 perpetuals with a strict one-way boundary `frontend (React/Vite) -> backend (Go/Gin, :8888) -> bot (Python/FastAPI, :8889) -> per-instance trading processes + Postgres / Valkey / NATS / ClickHouse / MinIO`. Three independent package areas (uv, Go modules, npm), a root `Makefile`, one path-filtered CI workflow with 15 jobs and an aggregate `quality-gate`, an image-publishing workflow, and a history-budget rule (max 4 commits per day on `master`). Kubernetes manifests live in `deploy/k8s-next` (PostgreSQL) next to a legacy MariaDB set in `deploy/k8s`. Inventory: `00-inventory.md`.

Findings: 90 (BOT 24, BACK 20, FRONT 19, INFRA 20, REPO 7), 6 merged as duplicates. By priority: P0 8, P1 33, P2 37, P3 12.

## 2. Implemented changes (21 tasks)

P0
- BOT-P0-003 scoped abort / cancel-all with an empty market scope is now a no-op instead of widening to the whole subaccount.
- BOT-P0-004 a failed position fetch during abort fails closed; tracked state is kept whenever the account could not be confirmed flat.
- BOT-P0-005 leg-2 emergency closes are priced with a market-2 fail-safe price (new required `BotAgent` argument).
- BOT-P0-001 bot status responses no longer contain the wallet mnemonic or Telegram token (presence flags instead).
- BACK-P0-001 admin deactivation, role change and admin password reset revoke the user's sessions before the write.
- INFRA-P0-001 / INFRA-P0-002 `bot-worker` and `bot-api` use `strategy: Recreate`; `bot-api` runs one replica, its PDB is removed.

P1
- BACK-P1-002 the NATS reconciler publishes a valid envelope with the same payload shape as the first publish.
- BOT-P1-005 fill pagination advances (cursor = oldest fill of the page, with a no-progress guard).
- BOT-P1-010 the auth bypass needs an explicit dev/test environment label and no conflicting label.
- FRONT-P1-001 mutations are never retried automatically. FRONT-P1-003 the create-runtime error log is sanitised. FRONT-P1-004 every logged-out transition clears the query cache. FRONT-P1-005 the go-live dialog shows signed balances and `—` for missing values.
- INFRA-P1-004 worker runs `python -m src.main_instance`. INFRA-P1-003 frontend containerPort matches nginx (80).

P2 / P3
- BACK-P2-001 Redis sessions required for `prod` and `production`. BACK-P3-001 upstream query strings built with `url.Values`.
- REPO-P2-002 update config covers Go modules and npm. REPO-P3-002 checkout action v7. INFRA-P2-004 `.dockerignore` excludes secret-bearing files.

## 3. Exact files changed

- bot: `src/trading/account_manager.py`, `src/trading/bot_agent.py`, `src/trading/position_manager.py`, `src/infrastructure/domain/bot_api_models.py`, `src/middleware/auth_middleware.py`, `README.md`; tests `test_account_manager_abort_cleanup.py`, `test_account_manager_fill_pagination.py` (new), `test_auth_bypass_environment_guard.py`, `test_bot_agent_emergency_cleanup.py`, `test_bot_instance_manager.py`, `test_trading_network_errors.py`.
- backend: `internal/routes/admin_user_routes.go`, `internal/services/nats_command_service.go`, `internal/services/bot_api_client_extended.go`, `internal/auth/session_store.go`; new tests `internal/routes/admin_user_session_revocation_test.go`, `internal/services/nats_command_reconciler_test.go`, `internal/services/bot_api_client_query_escape_test.go`, `internal/auth/session_store_require_redis_test.go`.
- frontend: `src/api/queryClient.ts`, `src/api/queryClient.test.ts` (new), `src/store/auth.ts`, `src/store/auth.test.ts`, `src/utils/apiErrors.ts`, `src/utils/apiErrors.test.ts`, `src/utils/format.ts`, `src/utils/format.test.ts`, `src/components/BotManager.tsx`, `src/components/StrategyManager.tsx`.
- infra / repo: `deploy/k8s-next/applications.yaml`, `deploy/k8s-next/platform-config.yaml`, `.dockerignore`, `.github/dependabot.yml`, `.github/workflows/history-budget.yml`, project tooling settings file, `docs/audit/2026-09-19/**`.

## 4. Database migrations added

None.

## 5. API endpoints added or changed

- Bot `GET /api/v1/bots` and `GET /api/v1/bots/{instance_id}`: `config.credentials.mnemonic` and `config.telegram.token` removed; `mnemonic_configured` / `token_configured` booleans added. No consumer in `backend/` or `frontend/` read the removed fields (grep in LOG.md). `config` is typed `Dict[str, Any]`, so `bot/openapi.json` is unchanged.
- Backend `PUT /api/v1/admin/users/:id`, `/role`, `/status`, `POST /users/:id/reset-password`: new `503` when session revocation is unavailable (no change is made in that case). Success responses unchanged.

## 6. Tests added or updated

bot +17 (1424 → 1441 passing), backend +4 tagged route tests, +3 reconciler, +2 query-escape, +1 table test (9 cases), frontend +5 (132 → 137). Two existing bot tests were extended with price assertions; 12 test constructors gained the new required argument. No test was removed or weakened.

## 7. Commands executed

See `LOG.md` for every command with its result. Gates: bot pytest with the 82% coverage floor, mypy, isort, black, flake8; backend `go build`, `go vet` (both tag sets), `go test -race -count=1 ./...`; frontend lint, typecheck, vitest; `kubectl kustomize` + kubeconform for both overlays; `docker compose config -q`; `make docs-governance`.

## 8. Validation results (real output)

- bot: `1441 passed, 13 skipped`, coverage `83.29%` (floor 82%); `mypy`: `Success: no issues found in 98 source files`; isort/black/flake8 clean.
- backend: `go test -race -count=1 ./...` → all 12 packages `ok`; build and vet clean.
- frontend: `26 files / 137 tests passed`; lint 0 warnings; typecheck clean.
- infra: staging and production overlays → `33 resources, Valid: 33, Invalid: 0`.
- docs governance: `[OK] Documentation governance validated across 31 markdown files`.
- Not run: `npm run build`, Playwright e2e, any image build, anything against a cluster, an exchange, or a shared database. `govulncheck`, `staticcheck`, `gitleaks` are not installed; `npm audit` could not complete (registry advisory endpoint returned HTTP 503).

## 9. Remaining risks and limitations

- The order path still has nine P1 proposals (no write-ahead entry intent, SIGTERM raising into arbitrary frames, order-result detection by string match, reduce-only close re-sent with a new client id, no halt latch after failed cleanup, realised P&L never recorded, plaintext mnemonics at rest without a key). These need design decisions and were not changed.
- No single-writer lock per trading instance exists; `Recreate` only protects Kubernetes rollouts, not a second process started by other means.
- BOT-P0-002 (open self-registration on the bot API, lifecycle routes open to any active user) is unchanged pending a decision.
- `deploy/k8s-next` still cannot run as committed: nonexistent PgBouncer tag, image names no pipeline builds, NetworkPolicies that block DNS and exchange egress, no TLS, no backups.
- The backend `integration`-tagged route tests are not run by CI and 20+ fail (BACK-P2-011); the four new revocation tests live under that tag and pass in isolation only.
- `quality-gate` is not a required check on `master`, and images publish without it (REPO-P2-003).
- Behaviour change for developers: `API_BYPASS_AUTH=true` now requires an explicit environment variable such as `ENVIRONMENT=development`.
- Merge note: squash-merge this branch; `master` allows at most 4 commits per day counted over merged history.

## 10. Screens requiring manual visual verification

- Strategy go-live dialog (`StrategyManager`): Free Collateral, Trade Size, Capital Allocation, Minimum Collateral now render through `formatUsdBalance` (negative sign, `—` when missing).
- Runtime creation form (`BotManager`): seed phrase input (autocomplete/spellcheck off) and the failure toast path.
- Logout then login as a different user: no cached data from the previous user appears.

## Open questions

See `OPEN-QUESTIONS.md` (12 questions, each tied to the task it blocks).
