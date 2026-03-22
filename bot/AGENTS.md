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

## Required checks for bot-runtime changes

- Verify startup/import works in configured interpreter.
- Verify one instance lifecycle path (create/start/status/stop).
- Verify no new placeholders are introduced in production paths.
- Document failure-mode impact and rollback plan.

## Key documentation map

- `PRODUCTION_READINESS.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/FAILURE_MODES.md`
- `docs/MULTI_INSTANCE_ARCHITECTURE.md`
- `docs/FEATURE_STATUS.md`
- `docs/CONFIG_MATRIX.md`
