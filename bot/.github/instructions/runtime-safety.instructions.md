---
name: "Runtime Safety and Ops Sync"
description: "Use when editing trading runtime, instance lifecycle, process management, async loops, or operational controls. Enforces async safety, exception propagation, interpreter consistency, and documentation synchronization."
applyTo: "src/**/*.py"
---

# Runtime Safety and Ops Sync

Apply these rules for runtime and lifecycle changes.

## Mandatory rules

1. **Async safety first**
   - Do not introduce `time.sleep(...)` in async call paths.
   - Use async-friendly delays and avoid blocking the event loop.

2. **Exception-first internals**
   - Do not add `exit(1)` to service/helper modules.
   - Raise explicit exceptions; keep process exits in entrypoints only.

3. **Lifecycle ownership**
   - Keep process orchestration inside `BotInstanceManager`.
   - Do not add unmanaged subprocess patterns in routes/services.

4. **Interpreter consistency**
   - Ensure launch/test paths use project `.venv` interpreter.

5. **State and reconciliation safety**
   - For changes touching `bot_states/*` or position tracking, include restart/recovery notes and mismatch handling.

## Required co-changes

When behavior changes, update relevant docs in the same PR:

- `README.md`
- `openapi.json`
- `../docs/OPERATIONS.md`
- `tasks.md`

## Validation expectations

- Confirm import/startup path in active interpreter.
- Validate one lifecycle operation (create/start/stop/status).
- Document rollback approach for runtime safety changes.
