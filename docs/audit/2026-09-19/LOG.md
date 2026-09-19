# Audit log — 2026-09-19

## 2026-09-19T17:27Z — run start
- Base branch: `master` (`origin/master` @ `24eb752b`). Work branch: `audit/2026-09-19-all`.
- Pre-existing dirty files (never staged): `monorepo.zip` (untracked).
- Commit-msg guard hook: not installed. The skill's `scripts/` and `references/` directories are absent from the installed skill location, so the guard is run by hand (`check`, `scan-staged`, `check-text`) from a session copy before every commit and PR.
- Project tooling settings file created with the `attribution` block (empty commit and PR trailers, no session link).
- Tools not available: `gitleaks`, `govulncheck`, `staticcheck`. Available: `go`, `uv`, `node` 24, `docker`, `gh`, `kubeconform`, `pip-audit` (bot venv).
- Repository rule noted: `history-budget.yml` allows at most 4 commits per calendar day on `master`, counted over merged history. This branch stays within 4 commits per day; a squash merge is recommended regardless.
- Expert skills: reused the existing service-specific skills and profiles under `zcode-marketplace/plugins/monorepo-experts/`; none created.

## 2026-09-19T17:45Z — REPO investigation
- `gh run list --limit 12 --json workflowName,conclusion,headBranch,createdAt` → 12/12 `success`.
- `git grep -nIE '(AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|ghp_…|xox…|sk_live_…|re_…)'` → only test-name false positives and the detector's own marker.
- `git grep -nIiE '(mnemonic|password|passwd|secret|api_key|apikey|token)…quoted literal'` (tests, docs, lockfiles, examples excluded) → placeholders and one `__main__` self-test literal; no credential.
- `grep -nE 'govulncheck|npm audit|trivy|grype|gitleaks|codeql' .github/workflows/*.yml` → no matches.

## 2026-09-19 — BOT-P0-003, BOT-P0-004, BOT-P0-005
Files: `bot/src/trading/account_manager.py`, `bot/src/trading/bot_agent.py`, `bot/src/trading/position_manager.py`, `bot/tests/test_account_manager_abort_cleanup.py`, `bot/tests/test_bot_agent_emergency_cleanup.py`, `bot/tests/test_trading_network_errors.py`.
Verification (from `bot/`, project venv):
- `python -m pytest tests/ --ignore=tests/test_api_database_integration.py --ignore=tests/test_comprehensive.py -q` → 1430 passed, 13 skipped (baseline 1424 passed).
- `python -m mypy src` → Success: no issues found in 98 source files.
- `python -m isort --check-only src tests`, `python -m black --check src tests` → clean (199 files unchanged); `flake8 --select=E9,F63,F7,F82` → clean.
Notes: BOT-P0-004 keeps the existing behaviour of clearing tracked state when only cancel-all fails (existing test unchanged); state is now kept when the position fetch or any close fails. BOT-P0-005 makes `accept_failsafe_quote_price` a required constructor argument so a caller cannot silently fall back to the market-1 price; 12 test constructors updated. Coverage gate (`--cov-fail-under=82`) not run yet; it runs before the commit.

## 2026-09-19 — INFRA-P0-001, INFRA-P0-002, INFRA-P1-004, INFRA-P1-003
Files: `deploy/k8s-next/applications.yaml`, `deploy/k8s-next/platform-config.yaml`.
Verification:
- `kubectl kustomize --load-restrictor LoadRestrictionsNone deploy/k8s-next/overlays/{staging,production}` piped to `kubeconform -summary -ignore-missing-schemas` → both: 33 resources, Valid: 33, Invalid: 0 (was 34; the bot-api PodDisruptionBudget is removed).
- Rendered production: `bot-api` replicas 1 / Recreate; `bot-worker` replicas 1 / Recreate / args `-m src.main_instance --instance-id bot-1`; `frontend` containerPort 80; PDBs left: backend, frontend.
- `cd bot && python src/main_instance.py --help` → `ModuleNotFoundError: No module named 'src'` (confirms the finding; the worker image sets no PYTHONPATH); `python -m src.main_instance --help` → usage text, exit 0.
- `FRONTEND_PORT` has no consumer in the repo (grep); value aligned to 80.
Not verified: behaviour on a cluster (nothing was applied).

## 2026-09-19 — BOT-P0-001
Files: `bot/src/infrastructure/domain/bot_api_models.py`, `bot/tests/test_bot_instance_manager.py`.
Consumer check: `grep -rnE 'credentials\??\.(mnemonic|address|chain_id)|\.mnemonic|"mnemonic"|telegram\??\.(token|bot_token|chat_id)' frontend/src backend/internal` → the only hits send a mnemonic in create requests (`BotManager.tsx:679-696`, `strategy_runtime_service.go:185,522,566`); nothing reads it from a bot response. `BotInstanceStatus.config` is `Dict[str, Any]`, so `bot/openapi.json` is unaffected.
Verification: `python -m mypy src` → clean; full bot suite → 1431 passed, 13 skipped.
Not changed: `instances.json` still persists the config as before (BOT-P1-012, proposal).

## 2026-09-19 — FRONT-P1-001, FRONT-P1-003, FRONT-P1-004, FRONT-P1-005
Files: `frontend/src/api/queryClient.ts`, `frontend/src/api/queryClient.test.ts` (new), `frontend/src/store/auth.ts`, `frontend/src/store/auth.test.ts`, `frontend/src/utils/apiErrors.ts`, `frontend/src/utils/apiErrors.test.ts`, `frontend/src/utils/format.ts`, `frontend/src/utils/format.test.ts`, `frontend/src/components/BotManager.tsx`, `frontend/src/components/StrategyManager.tsx`.
Verification (from `frontend/`): `npm run lint` → clean (0 warnings); `npm run typecheck` → clean; `npm test` → 26 files / 137 tests passed (baseline 25 / 132).
Notes:
- FRONT-P1-005 deviates from the finding's proposed fix. `formatUsd`/`formatUsdFixed` are documented as unsigned, with tests asserting `formatUsd(-42) === '$42'` and `formatUsdFixed(undefined) === '$0.00'`, and they serve ~40 commission/ledger call sites. Changing them would rewrite valid tests and alter every ledger. A separate `formatUsdBalance` now renders the four go-live dialog figures (free collateral, trade size, capital allocation, minimum collateral).
- `grep -rn retry src | grep -i mutation` → no mutation relied on the global retry.
- `prettier --check` flags `src/utils/format.ts` and `src/utils/apiErrors.test.ts`; both were already unformatted at HEAD (checked with `git show HEAD:… | prettier`), left as is. `format:check` is not part of CI.

## 2026-09-19 — BACK-P1-002, BACK-P2-001, BACK-P3-001
Files: `backend/internal/services/nats_command_service.go`, `backend/internal/services/nats_command_reconciler_test.go` (new), `backend/internal/auth/session_store.go`, `backend/internal/auth/session_store_require_redis_test.go` (new), `backend/internal/services/bot_api_client_extended.go`, `backend/internal/services/bot_api_client_query_escape_test.go` (new).
Verification (from `backend/`): `go build ./...` ok; `go vet ./internal/services/ ./internal/auth/` ok; `go test -race -count=1 ./internal/services/` ok; `go test -race -count=1 ./internal/auth/` ok.
Notes:
- BACK-P1-002 was wider than reported. Besides the missing correlation id, the reconciler re-published the stored run config as the message body, while the consumer (`bot/src/infrastructure/workers/nats_backtest_consumer.py:209-215`) reads `command_id`, `run_id`, `owner_id` and `idempotency_key` from the body. Setting only the correlation id would have started delivering messages with an empty run id. Both publish paths now share `buildCommandPayload`.
- BACK-P2-001: `GIN_MODE=release` is deliberately not treated as production here (the two existing `isProductionEnvironment` helpers do); it would turn a missing Redis into a fatal start in release-mode staging.
- `gofmt -l` reports `internal/services/password_reset_service.go` and `internal/routes/password_reset_routes.go`; both are untouched by this run (pre-existing).

## 2026-09-19 — BACK-P0-001
Files: `backend/internal/routes/admin_user_routes.go`, `backend/internal/routes/admin_user_session_revocation_test.go` (new, `integration` tag like the harness it uses).
Verification (from `backend/`):
- `go test -tags integration -race -count=1 -run 'TestAdminUserRoutes' ./internal/routes/` → ok (39.3s).
- With the handler change stashed: `TestAdminUserRoutes_DeactivateRevokesSessions`, `_RoleChangeRevokesSessions`, `_ResetPasswordRevokesSessions` FAIL; `_ProfileOnlyUpdateKeepsSessions` passes (the tests detect the bug).
- `go test -tags integration -count=1 ./internal/routes/` (whole tagged package) → FAIL with 20+ failures in MFA, refresh and delegated-backtest tests (`no such function: hashtext`, login 401, 404). None touches the changed handlers; a baseline run of the tagged package on `master` was not performed. Recorded as BACK-P2-011.
Notes: admin MFA reset does not revoke sessions (left out: not part of the deactivate/demote exposure). The refresh-time `is_active` re-check was not added: `SessionStore.Get`/`Refresh` already reject sessions older than the user's generation.

## 2026-09-19 — BOT-P1-005, BOT-P1-010
Files: `bot/src/trading/account_manager.py`, `bot/tests/test_account_manager_fill_pagination.py` (new), `bot/src/middleware/auth_middleware.py`, `bot/tests/test_auth_bypass_environment_guard.py`, `bot/README.md`.
Notes: the first cursor fix (last fill of the page) broke the existing `TestGetOrderFillsPagination::test_get_order_fills_pages_until_order_found`, whose fixture is not newest-first; the cursor is now the minimum `createdAt` of the page, which satisfies the existing test unchanged and the four new ones. BOT-P1-010 removes the now-unused `_normalized_environment_name` and `_AUTH_BYPASS_FORBIDDEN_ENVIRONMENTS`. Behaviour change for developers: `API_BYPASS_AUTH=true` with no environment variable set now refuses to start; set `ENVIRONMENT=development`.

## 2026-09-19 — REPO-P2-002, REPO-P3-002, INFRA-P2-004
Files: `.github/dependabot.yml`, `.github/workflows/history-budget.yml`, `.dockerignore`.
Verification: both YAML files parse (`yaml.safe_load`); update config lists pip, gomod, npm, github-actions, docker; `docker compose -f docker-compose.{stack,infra,bot-worker}.yml config -q` → ok. Every Dockerfile `COPY` source (`bot/`, `backend/`, `frontend/`, `docker/nginx.conf`) is outside the new ignore rules; images create their own stub `run.json`. No image build was run.

## 2026-09-19 — final gates before commit
- bot: `pytest … --cov=src --cov-fail-under=82` → 1441 passed, 13 skipped, coverage 83.29%; `mypy src` clean; `isort --check-only`, `black --check` clean (200 files); `flake8 --select=E9,F63,F7,F82` clean.
- backend: `go build ./...`, `go vet ./...`, `go vet -tags integration ./internal/routes/` ok; `go test -race -count=1 ./...` → all 12 packages ok (routes 56.8s).
- frontend: `npm run lint` clean, `npm run typecheck` clean, `npm test` → 26 files / 137 tests passed. `npm run build` and `npm run test:e2e` not run.
- infra: both overlays render → kubeconform 33/33 valid; compose configs ok.
- docs: `make docs-governance` → OK (31 markdown files).

## 2026-09-19T18:10Z — commit 36723306
Tasks: BOT-P0-001, BOT-P0-003, BOT-P0-004, BOT-P0-005, BACK-P0-001, INFRA-P0-001, INFRA-P0-002, BACK-P1-002, BOT-P1-005, BOT-P1-010, FRONT-P1-001, FRONT-P1-003, FRONT-P1-004, FRONT-P1-005, INFRA-P1-003, INFRA-P1-004, BACK-P2-001, REPO-P2-002, INFRA-P2-004, BACK-P3-001, REPO-P3-002
Verification: see "final gates before commit" above. Staged-diff secret grep: no hits beyond the quoted scan command in this log. Guard: scan-staged OK, check OK.

## 2026-09-19T18:20Z — CI failure on the pull request and fix (FRONT-P1-004)
- PR CI: every job passed except `Frontend quality` (and therefore `Quality gate`): 6 of 10 Playwright smoke tests failed with a blank page. All four image builds passed, which exercises the new `.dockerignore` for real.
- Root cause: the first FRONT-P1-004 change called `queryClient.clear()` on every logged-out transition. Session bootstrap also ends in the logged-out state, so the in-flight `['public', 'app-config']` query the app shell renders from was removed; a removed query never notifies its observer and the shell stayed blank. Unit tests, lint and typecheck could not see this; the e2e suite had not been run locally before the push.
- Fix: `clearUserScopedQueries()` removes every query whose key does not start with `public`; test added that public data survives and user data does not.
- Verification (from `frontend/`): `npm run lint` clean; `npm run typecheck` clean; `npm test` → 26 files / 138 tests passed; `npx playwright test` → 10 passed (reproduced 6 failures before the fix).
