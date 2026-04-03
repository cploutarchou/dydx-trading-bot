# AGENTS.md

Repository-level guidance for coding agents working on this project.

## Primary goals

- Preserve trading safety over convenience.
- Keep multi-instance behavior deterministic.
- Prefer fail-safe behavior with explicit, actionable error reporting.

## Mandatory engineering rules

1. **Environment load order**
   - Entry points must load dotenv before importing config/constants.
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
   - If runtime behavior or operations change, update relevant docs in `docs/` and `PRODUCTION_READINESS.md` in the same change.
8. **Canonical API entrypoints**
   - Treat `src/api/server.py` as the canonical API; keep `app.py` and `start_api.py` as compatibility wrappers around `src.api.server` / `src.api.start_api`.
9. **API/auth contract stability**
   - Preserve the standardized `api_response(...)` envelope in `src/api/server.py` routes and keep websocket auth aligned with `authenticate_bearer_token(...)`.
10. **Service-token rotation support**
   - Keep overlap support for `BOT_API_TOKEN`, `BOT_API_TOKEN_PREVIOUS`, and `BOT_API_TOKENS`; if changed, update `tests/test_auth_middleware_service_token.py`.

## Required checks for bot-runtime changes

- Verify startup/import works in configured interpreter.
- Verify one instance lifecycle path (create/start/status/stop).
- Verify no new placeholders are introduced in production paths.
- Verify auth behavior with service-token overlap path (`tests/test_auth_middleware_service_token.py`) when touching auth middleware/routes.
- Run `make preflight-testnet` (and `make preflight-testnet-strict` for release-oriented changes) for runtime/safety-impacting edits.
- Document failure-mode impact and rollback plan.

## Key documentation map

- `PRODUCTION_READINESS.md`
- `LOCAL_SETUP.md`
- `.github/copilot-instructions.md`
- `tasks.md`
