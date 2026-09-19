# Inventory — dydx-trading-bot — 2026-09-19

Self-hosted statistical-arbitrage trading system for dYdX v4 perpetuals with a web control plane.
Strict one-directional boundary: `frontend -> backend -> bot -> workers + infra`.
Sizes are tracked files / lines (`git ls-files`), measured on `origin/master` @ `24eb752b`.

| Code | Path | Language / framework | Domain | Size |
| :--- | :--- | :--- | :--- | :--- |
| BOT | `bot/` | Python 3.12 (`requires-python >=3.12,<3.13`), FastAPI control plane, Celery/NATS workers, uv | trading runtime, orders, positions, backtests | 305 files / 109,753 lines |
| BACK | `backend/` | Go (`go 1.25.0` in `go.mod`), Gin API gateway | auth, gateway, analytics, delegated bot routes | 423 files / 76,913 lines |
| FRONT | `frontend/` | React + TypeScript + Vite, npm, Node 24 | operator dashboard | 301 files / 86,709 lines |
| INFRA | `deploy/`, `docker/`, `docker-compose.*.yml`, `config/`, `scripts/` | Kustomize, Dockerfiles, Compose, Python/shell scripts | platform, deployment, config encryption | 53 files / 6,987 lines |
| REPO | root, `.github/`, `docs/`, `zcode-marketplace/` | GitHub Actions, Makefile, docs | CI/CD, tooling, dependency policy, secrets handling, release | 72 files / 7,643 lines (+ root Makefile 810) |

## BOT — `bot/`

- Entrypoints: `src/main_instance.py` (per-instance worker), `src/api` (FastAPI, :8889), `src/bot_instance_manager.py`, `src/infrastructure/workers` (Celery / NATS consumers).
- Build/install: `pip install -r requirements.txt` (CI); local `uv` (`uv.lock`).
- Test (CI, blocking): `cd bot && python -m pytest tests/ --ignore=tests/test_api_database_integration.py --ignore=tests/test_comprehensive.py --cov=src --cov-fail-under=82`
- Lint/format (CI, blocking): `python -m isort --check-only src tests && python -m black --check src tests && python -m flake8 src tests --select=E9,F63,F7,F82`
- Types (CI, blocking): `python -m mypy src`
- Security (CI): `python -m bandit -r src -c pyproject.toml -ll`; `pip-audit -r requirements.txt`
- Databases / migrations: Postgres (`bot/migrations/postgres`, 9 files; `bot/migrations/versions`, 12 files), ClickHouse writer, Valkey, MinIO.
- External integrations: dYdX v4 (indexer + validator), NATS, email delivery.
- Deploy target: `docker/Dockerfile.api`, `docker/Dockerfile.worker`; `deploy/k8s-next`.
- Owner: none recorded (no `CODEOWNERS`).

## BACK — `backend/`

- Entrypoints: `cmd/server` (:8888), `cmd/migrate`.
- Build/test (CI, blocking): `cd backend && go build ./... && go vet ./... && go vet -tags integration ./internal/routes/ && go test -race -count=1 ./...`
- Lint (CI, reporting-only): `golangci-lint run ./...` (v2.12.0).
- Databases / migrations: Postgres, `backend/migrations/postgres` (145 files), run by `cmd/migrate` / `docker/Dockerfile.backend-migrator`.
- External integrations: bot API (:8889), NATS publisher, ClickHouse/Postgres readers.
- Deploy target: `docker/Dockerfile.backend`, `docker/Dockerfile.backend-migrator`; `deploy/k8s-next`.
- Owner: none recorded.

## FRONT — `frontend/`

- Entrypoints: Vite app (`npm run dev`, :5173); portal variants `client`, `backoffice`, `ib`.
- CI (blocking): `cd frontend && npm ci && npm run lint && npm run typecheck && npm run build && npm run test:e2e`. Documented locally: `npm run test:contracts`. Unit tests: `npm run test` (vitest).
- Format: `npm run format:check`.
- Integrations: backend API only (`src/api.ts`).
- Deploy target: `docker/Dockerfile.frontend`.
- Owner: none recorded.

## INFRA

- Validate (CI): `docker compose -f docker-compose.infra.yml config`; `docker compose -f docker-compose.stack.yml config`; kustomize build of `deploy/k8s-next` overlays (staging, production); `python3 scripts/check_no_plaintext_k8s_secrets.py`.
- Test command: none found for `scripts/*.py` beyond the checks above.
- Encrypted config: `config/profiles/*.config.enc.json`, key `.configkey.bin` (untracked, never printed).

## REPO

- CI: `.github/workflows/bot-quality.yml` (15 jobs + `quality-gate`; path-filtered on push/PR to master), `container-images.yml`, `history-budget.yml` (max 4 commits per day on master, `scripts/check_commit_history_budget.py`), `local-dev-setup.yml`. Last 12 runs on GitHub: all `success` (2026-09-13).
- Docs governance: `make docs-governance` (`scripts/validate_docs_governance.py`).
- Release process: consolidated daily commits on master; container images built by CI.
- Pre-commit: `.pre-commit-config.yaml`.

## Expert skills

Reused (service-specific, already in the repo): `zcode-marketplace/plugins/monorepo-experts/skills/{bot-trading-service,backend-gateway-service,frontend-dashboard-service,monorepo-architecture,db-migrations,ci-release-analysis,trading-security-review}` and the profiles in `zcode-marketplace/plugins/monorepo-experts/references/`.

## Tools available in this environment

Present: `go`, `uv`, `node` 24, `docker`, `gh`, `kubeconform`, `pip-audit` (bot venv). Missing: `gitleaks`, `govulncheck`, `staticcheck`.
