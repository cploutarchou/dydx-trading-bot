# AGENTS.md

Repository-level guidance for coding agents working on this project.

## Start-of-task checklist

1. Read `../.github/copilot-instructions.md`
2. Read `.github/copilot-instructions.md`
3. Read `.github/CUSTOMIZATION_INDEX.md`
4. Read `.github/instructions/runtime-safety.instructions.md`
5. Prefer `.github/agents/senior-python-defi-runtime.agent.md` for bot implementation work

## Primary goals

- Preserve trading safety over convenience.
- Keep multi-instance behavior deterministic.
- Prefer fail-safe behavior with explicit, actionable error reporting.

## Mandatory engineering rules

1. **Environment load order**
    - Entry points must call `load_repo_env(__file__)` before importing config/constants (see `src/api/server.py`,
      `src/api/start_api.py`, `app.py`, `start_api.py`, `main.py`, `src/main_instance.py`,
      `src/bot_instance_manager.py`).
    - Runtime config is structured (`run.json` or `config/profiles/*`), not `bot/.env`.
2. **No direct process management outside manager layer**
    - Manage worker lifecycle through `src/bot_instance_manager.py`.
3. **Async correctness**
    - Avoid `time.sleep(...)` inside async workflows; use async-friendly delay patterns.
4. **Error propagation**
    - Avoid `exit(1)` in library/service functions; raise typed exceptions and let entrypoints decide process exit.
5. **Interpreter consistency**
    - Use project `.venv` interpreter across tasks/scripts/tests/launchers.
6. **State safety**
    - Any change touching `bot_states/*` handling must include restart/recovery reconciliation notes.
7. **Documentation sync**
    - If runtime behavior or operations change, update `README.md`, `../docs/OPERATIONS.md`, `openapi.json`, and
      `tasks.md` in the same change.
8. **Canonical API entrypoints**
    - Treat `src/api/server.py` as the canonical API; keep `app.py` and `start_api.py` as compatibility wrappers around
      `src.api.server` / `src.api.start_api`.
9. **API/auth contract stability**
    - Preserve the standardized `api_response(...)` envelope in `src/api/server.py` routes and keep websocket auth
      aligned with `authenticate_bearer_token(...)`.
    - Preserve request trace propagation (`trace_id` + `X-Trace-Id`) and strict `/ready` semantics (`200` only when bot
      manager is available, otherwise `503`).
10. **Service-token rotation support**

- Keep overlap support for `BOT_API_TOKEN`, `BOT_API_TOKEN_PREVIOUS`, and `BOT_API_TOKENS`; if changed, update
  `tests/test_auth_middleware_service_token.py`.
11. **Supervised async background work**
    - Launch long-running/background tasks via `src/infrastructure/use_cases/async_job_manager.py` so task
      failures/progress persist to job state and are visible to operators.

## Required checks for bot-runtime changes

- Verify startup/import works in configured interpreter.
- Verify one instance lifecycle path (create/start/status/stop).
- Verify no new placeholders are introduced in production paths.
- Verify auth behavior with service-token overlap path (`tests/test_auth_middleware_service_token.py`) when touching
  auth middleware/routes.
- Verify `/ready` behavior remains strict (`200` when bot manager is available, `503` otherwise) when touching API
  startup/readiness paths.
- Verify strategy runtime websocket behavior (`/ws/strategies`) still sends `strategy_status_snapshot` on connect and
  lifecycle updates after runtime state changes.
- Verify per-instance subprocess logs still write to `bot_states/bot_<instance_id>.log` and dead-process cleanup remains
  active when touching `src/bot_instance_manager.py`.
- Run `tests/test_backtest_api_contract.py` when touching backtest routes/payloads to preserve backend-facing
  status/progress and alias contracts.
- Run `tests/test_async_job_manager.py` when touching background task orchestration (`async_job_manager`) behavior.
- Run `make test-execution-safety` when touching order execution, emergency cleanup, or position-reconciliation safety paths.
- Run `make preflight-testnet` (and `make preflight-testnet-strict` for release-oriented changes) for
  runtime/safety-impacting edits.
- When touching database runtime selection/cutover logic, run `tests/test_database_config_runtime.py` and verify
  `BOT_DB_CUTOVER_MODE=dedicated` behavior remains valid.
- Document failure-mode impact and rollback plan.

## Key documentation map

- `README.md`
- `openapi.json`
- `../docs/OPERATIONS.md`
- `.github/copilot-instructions.md`
- `tasks.md`

## Latest bot context (2026-05)

- Keep `src/api/server.py` as canonical API entrypoint and preserve compatibility wrappers (`app.py`, `start_api.py`).
- Preserve backend-facing normalized status/progress fields (and compatibility aliases) used by delegated runtime/backtest contracts.
- Service-token overlap behavior (`BOT_API_TOKEN`, `BOT_API_TOKEN_PREVIOUS`, `BOT_API_TOKENS`) and readiness semantics remain active contracts with backend delegation.
- Strategy runtime websocket expectations remain operator-critical: snapshot on connect plus lifecycle/status updates after runtime changes.
