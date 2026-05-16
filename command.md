# Full DB-Backed Config Migration — Codex Agent Command

## Objective
Migrate all strategy configuration handling in the dydx-trading-bot platform to use the database as the single source of truth, deprecating YAML config files for all environments (dev, staging, prod).

---

## Command for Codex Agent

**Agent, perform the following steps to fully migrate config handling to the database:**

1. **Audit Codebase for YAML Config Usage**
   - Search for all code that loads, writes, or references YAML config files (e.g., `*.yaml`, `yaml.safe_load`, `open('...yaml')`).
   - List all affected files and functions.

2. **Centralize Config CRUD in Database**
   - Ensure the backend exposes full CRUD endpoints for strategy configs (create, read, update, delete).
   - If missing, implement or extend these endpoints.
   - Ensure the bot fetches configs from the DB via API or direct DB access, never from YAML.

3. **Refactor Bot Startup and Runtime**
   - Remove YAML config loading from all bot startup and runtime paths.
   - On instance start, fetch config from the DB (by instance ID or strategy ID).
   - Add a fast-fail validation if DB config is missing or incomplete.

4. **Migrate Existing YAML Data to DB**
   - Write a migration script to load all important YAML config data into the DB.
   - Validate that all required fields are present in the DB after migration.

5. **Update Dev/Local Flows**
   - Ensure local/dev environments use the same DB-backed config path (no YAML fallback).
   - Update documentation (README, runbooks) to reflect this change.

6. **Deprecate YAMLs**
   - Remove or clearly mark all YAML config files as deprecated.
   - Add a warning if any code tries to load a YAML config in any environment.

7. **Test End-to-End**
   - Run full lifecycle tests (create, update, run, backtest, delete) using only DB configs.
   - Confirm all environments (dev, staging, prod) work without YAMLs.

---

## Output
- Provide a summary of all code changes, new/updated endpoints, and migration scripts.
- List any manual steps required for operators.
- Confirm that YAML configs are no longer used in any environment.

---

**Codex Agent: Execute this plan and report progress at each step.**
