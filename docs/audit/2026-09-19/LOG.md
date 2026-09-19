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

## 2026-09-19T20:12Z — merge and decisions
- PR #40 squash-merged into `master` as `95b7409a`; `History Budget` on the merge commit: success.
- Owner answered the open questions (recorded in OPEN-QUESTIONS.md). Read-only cluster check: app runs in `executionlab-staging` behind Traefik, deployed by Flux from a separate GitOps repository; Postgres is a three-instance CloudNativePG cluster with the barman-cloud plugin; cert-manager and external-dns present; `dns-guard` CronJob failing.
- MASTER-PLAN.md: 13 tasks moved to a second queue (`todo`); in-repo Kubernetes findings moved to the GitOps repository.
- 2026-09-19T20:17Z: at the owner's request the remaining eleven proposals (eight order-path items, BACK-P1-001, INFRA-P1-010, REPO-P3-004) were moved to queue 2 as `todo`, each with its own task record and verification. Queue 2 now holds 24 tasks.

## 2026-09-19T20:52Z — resume (queue 2)
- Base `master` @ e673ed0c. The branch recorded in the plan header (`audit/2026-09-19-all`) was squash-merged and has diverged, so work continues on `audit/2026-09-19-queue2`. Pre-existing dirty files (never staged): `monorepo.zip`.
- Branching: low-risk tasks are batched on this branch. High-blast-radius tasks get their own branch and pull request: INFRA-P0-001L (live start-up lock), BOT-P1-011 (signing SDK), BOT-P1-003 (entry intent + migration).
- Guard hook still not installed (skill `scripts/` absent from the installed location); guard run by hand before each commit and PR.

## 2026-09-19 — BOT-P0-002
Files: `bot/src/api/v1/auth/__init__.py`, `bot/src/api/v1/bot_lifecycle.py`, `bot/tests/test_bot_lifecycle_routes.py`, `bot/tests/test_auth_self_registration_gate.py` (new), `bot/README.md`.
Checks before the change: the backend never calls the bot's register route (`grep -rn auth/register backend/internal` → only the backend's own route list); the backend sends the service token when `BOT_API_TOKEN` is configured (`bot_api_client.go:225-236`), and that token maps to a superuser principal (`auth_middleware.py:159`), so delegated lifecycle calls keep working. A deployment that forwards end-user JWTs instead gets 403 for non-admins (documented in the README).
Test changes: the lifecycle fixture user is now an admin (the routes require one); the dependency assertion is stricter (admin on mutations, active user on reads). The bot user model has `is_admin` only, so "admin/operator" maps to the existing `get_admin_user` dependency.
Verification (from `bot/`): full suite → 1458 passed, 13 skipped; `mypy src` clean; black/isort clean.

## 2026-09-19 — BACK-P1-003, BACK-P1-004
Files: `backend/internal/db/db.go`, `backend/internal/db/migration_force_recovery_test.go` (new), `docker-compose.stack.yml`, `docker-compose.stack.arm64.yml`, `LOCAL_SETUP_GUIDE.md`.
Verification: `go vet ./internal/db/`, `go test -race -count=1 ./internal/db/ ./cmd/...` → ok; `docker compose -f docker-compose.stack{,.arm64}.yml config -q` → ok; rendered config: `backend-migrate` command `["up"]`, `backend-api` depends on it with `service_completed_successfully`, `DB_AUTO_MIGRATE: "false"`; `make docs-governance` → OK.
Notes: the cluster already runs per-release `backend-migrate` / `bot-migrate` jobs (observed). Whether the cluster's backend config still sets `DB_AUTO_MIGRATE=true` lives in the GitOps repository and must be checked there. Migration 000070 itself is unchanged: rehearsing it on a copy is a human step. `Force` recovery keeps an explicit local escape hatch because historical migrations contain non-idempotent index creation; it is off by default everywhere. The stack was not started here (config rendered only).

## 2026-09-19 — BACK-P1-005
Files: `backend/internal/app/router.go`, `backend/internal/app/trusted_proxies.go` (new), `backend/internal/app/trusted_proxies_test.go` (new), `backend/internal/routes/password_reset_routes.go`, `backend/internal/routes/auth_routes.go`, `backend/internal/routes/auth_credential_rate_limit_test.go` (new), `backend/README.md`, `.env.example`.
Verification (from `backend/`): `go build ./...`, `go vet ./...`, `go vet -tags integration ./internal/routes/` ok; `go test -race -count=1 ./...` → every package ok.
Deployment note: until the GitOps repository sets `TRUSTED_PROXIES` to the pod CIDR, all users behind Traefik share one client IP, so the new credential budget (1 rps, burst 20) is shared by everyone. Set the variable in the same release.

## 2026-09-20 — FRONT-P1-006, FRONT-P1-002
Files: `frontend/src/utils/runtimeForm.ts` (new), `frontend/src/utils/runtimeForm.test.ts` (new), `frontend/src/components/BotManager.tsx`, `frontend/src/components/StrategyManager.tsx`.
Verification (from `frontend/`): `npm run lint` clean; `npm run typecheck` clean; `npm test` → 27 files / 148 tests passed; `npx playwright test` → 10 passed.
Notes: the "Use Testnet" checkbox is replaced by a read-only network line derived from the chain id (mainnet is labelled as trading real funds). The stop dialog text makes no claim about positions being closed or kept, because that behaviour was not verified.

## 2026-09-20 — REPO-P2-003, REPO-P2-001, REPO-P3-001, INFRA-P3-001
- REPO-P2-003: `.github/workflows/container-images.yml` gains `wait-for-quality-gate`; `bot-quality.yml` path filters now cover `docker/**`, the image workflow and the drift script. The wait script was extracted from the YAML and run locally: gate success on `95b7409a` → exit 0; pull_request event → exit 0; commit with no gate check → exit 1 after the (shortened) appearance window. The first version looped forever on a missing check (empty API output was not mapped to `missing`); fixed and re-run. The failed-gate branch was not exercised against a real failed check.
- REPO-P2-001: `backend/go.mod` → `go 1.27.0`; with go1.27.0: `go build ./...`, `go vet ./...`, `go vet -tags integration ./internal/routes/`, `go test -race -count=1 ./...` → all ok. CI Node → 26 (local Node is 24.21, so lint/typecheck/tests/e2e on Node 26 are verified by PR CI only). `python3 scripts/check_toolchain_drift.py` → exit 1 before the Node bump, `OK (Go 1.27, Node 26)` after; wired into the `Docker Compose validation` job.
- REPO-P3-001: version statements corrected. The devcontainer base tag stays at `go:1-1.25-bookworm`: `docker manifest inspect` could not confirm any tag (it also failed for the tag in use), so only the comment was made truthful.
- INFRA-P3-001: `git rm -r deploy`, `git rm scripts/check_no_plaintext_k8s_secrets.py`; CI jobs `k8s-secret-scan` and `kustomize-validate` removed from the workflow and from the gate's `needs` (13 jobs left, YAML parses); `validate-k8s-secrets` make target removed; README, setup guide, AGENTS.md, expert profiles updated. Dated reports (`docs/FINAL_*`, `bot/tasks.md`) keep their historical references; the blocked item P4.1 carries a resolution note. `make docs-governance` → OK; compose configs ok. The GitOps repository URL is not recorded because it is not known from this repository.

## 2026-09-20 — INFRA-P1-010
Files: `Makefile`, `docker-compose.stack.yml`, `docker-compose.stack.arm64.yml`, `docker-compose.infra.yml`, `docker-compose.infra.arm64.yml`, `LOCAL_SETUP_GUIDE.md`.
Verification: `docker compose -f <file> config -q` → ok for all five compose files; `grep` for published ports not starting with `127.0.0.1` → none; `make -n stack-up-prod` → "No rule to make target"; `make docs-governance` → OK.
Deviation from the plan record: the `${VAR:?missing}` change for secrets was not made. CI validates the compose files with no environment set and the local bootstrap relies on the placeholders; with the production path removed and every port on loopback, the placeholders no longer guard anything reachable. The stacks were not started here.

## 2026-09-20 — BACK-P1-001, REPO-P3-004
Files: `backend/internal/routes/quick_deploy_attribution.go` (new), `backend/internal/routes/quick_deploy_attribution_test.go` (new), `backend/internal/routes/bot_api_delegate_routes.go`, `.github/CODEOWNERS` (new).
Verification (from `backend/`, go1.27.0): `go build ./...`, `go vet ./...`, `go vet -tags integration ./internal/routes/` ok; `go test -race -count=1 ./...` → every package ok.
Notes: the ownership row stores trading parameters only; credentials from the request body are never persisted (asserted by test). The quota race is closed by a re-count after the insert rather than a transaction, because the count and insert go through the existing repository methods on separate statements. A handler-level HTTP test was not added: the delegate routes' HTTP tests live under the `integration` tag whose harness is broken (BACK-P2-011); the logic is covered through the extracted function.

## 2026-09-19T21:15Z — commit f0dbc203
Tasks: BOT-P0-002, BACK-P1-001, BACK-P1-003, BACK-P1-004, BACK-P1-005, FRONT-P1-006, FRONT-P1-002, REPO-P2-003, REPO-P2-001, REPO-P3-001, INFRA-P3-001, INFRA-P1-010, REPO-P3-004
Verification: per-task entries above. Guard: scan-staged OK, check OK. Staged-diff secret grep: no hits.

## 2026-09-20 — BOT-P1-001, BOT-P1-006 (uncommitted); BOT-P1-007 deferred
Branch: `audit/2026-09-19-orderpath`, stacked on `audit/2026-09-19-queue2`.
Files: `bot/src/exceptions.py`, `bot/src/trading/account_manager.py`, `bot/src/trading/bot_agent.py`, `bot/tests/test_account_manager_order_lookup.py`, `bot/tests/test_bot_agent_emergency_cleanup.py`, `bot/tests/test_exception_handling_ratchet.py`.
Verification (from `bot/`): full suite → 1473 passed, 13 skipped; `mypy src` clean.
Notes:
- BOT-P1-001: the old `"code" in str(order)` check only logged. Leg-1 rejection still goes through the existing reduce-only cleanup in `open_trades` (a no-op for an order that never existed), which was left as is.
- BOT-P1-006: the first version returned quietly when every placement failed and the indexer reported the position flat. The existing test `test_bot_agent_open_trades_connection_error` requires escalation in that case, and indexer lag makes the flat reading untrustworthy right after an unknown-outcome entry, so a flat reading now counts only after a close order was actually placed. The broad-catch ratchet baseline moves 306 → 307 with the justification the ratchet asks for.
- BOT-P1-007 deferred: chain semantics unknown (question recorded).

## 2026-09-20 — BOT-P1-012, BOT-P1-008 (uncommitted)
Files: `bot/src/shared/environment.py` (new), `bot/src/shared/credentials_cipher.py`, `bot/src/middleware/auth_middleware.py`, `bot/src/exceptions.py`, `bot/src/trading/entry_halt.py` (new), `bot/src/trading/bot_agent.py`, `bot/src/trading/position_manager.py`, `bot/tests/test_credentials_encryption_requirement.py` (new), `bot/tests/test_entry_halt_latch.py` (new), `bot/README.md`, `bot/AGENTS.md`.
Verification (from `bot/`): full suite → 1491 passed, 13 skipped; `mypy src` → no issues in 100 files; isort, black, flake8 clean; `make docs-governance` → OK.
Notes:
- BOT-P1-012: no new re-seal command was needed; `make encrypt-bot-credentials` already exists. The worker image bakes `APP_ENV=prod`/`ENVIRONMENT=prod` while the local stack adds `APP_CONFIG_ENV=development`; mixed labels are not "explicit dev", so a worker in the local stack that writes credentials needs a key. The API image (where instance creation writes credentials) carries only the development label in the stack.
- BOT-P1-008: `UnhedgedExposureError` also subclasses `RuntimeError`, so existing handlers and tests that expect `RuntimeError` are unchanged. The scan uses `break` so its DataFrame cleanup still runs. A first full run failed `test_portfolio_risk` because the new test module leaked per-pair backoff state; its fixture now clears it on teardown.
- PR #54 CI (first batch): all 25 checks passed, including the frontend on Node 26, the backend on Go 1.27 and `Wait for quality gate`; GitHub reports 0 CODEOWNERS errors.
