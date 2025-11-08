# 📋 AI Copilot Instructions Update - Summary

**File**: `.github/copilot-instructions.md` (updated Nov 8, 2025)

## What Was Updated

### ✅ Consolidated & Accurate

The instructions file has been **completely refreshed** with the following improvements:

1. **Removed Outdated Information**
   - ❌ Removed references to Go backend as primary API (now optional/deprecated)
   - ❌ Removed incorrect `app/` directory references (confirmed as `bot/`)
   - ❌ Removed duplicate sections that appeared twice in original file

2. **Added Discovered Patterns from Codebase**
   - ✅ Exact file organization from `bot/` directory
   - ✅ Actual FastAPI port (8000), not Go API (8888)
   - ✅ Real configuration flow: `config.yaml` → `config.py` → `constants.py`
   - ✅ Actual `BotAgent` atomic execution pattern with emergency cleanup
   - ✅ State persistence via direct JSON (not singleton managers)
   - ✅ Multi-instance subprocess management via `BotInstanceManager`

3. **Updated Critical Knowledge**
   - ✅ Current working directory patterns (always `cd bot` before running)
   - ✅ Three-tier architecture diagram showing actual data flows
   - ✅ Real error handling patterns from codebase (SmartError, exit(1) for critical)
   - ✅ Actual database models (BotInstance, Trade, Job, User)
   - ✅ WebSocket real-time broadcast architecture

4. **Simplified & Actionable**
   - ✅ Reduced from 1,000+ lines of verbose content to 401 lines of essential patterns
   - ✅ Removed generic advice, kept only discoverable project-specific conventions
   - ✅ Actual code examples directly from `main.py`, `constants.py`, `func_bot_agent.py`

## Key Patterns Now Documented

### Essential Knowledge

| Pattern | File | Why It Matters |
|---------|------|----------------|
| Config loading | `bot/constants.py` | Avoid repeated expensive YAML parsing |
| Environment bootstrap | `bot/main.py` | `load_dotenv()` must be line 1 |
| Atomic paired trades | `bot/func_bot_agent.py` | Emergency cleanup if second order fails |
| State files | Direct JSON | No orphaned positions or config loss |
| Error handling | Two-tier (critical/non-critical) | Graceful degradation vs hard exits |
| API integration | `bot/bot_api_server.py` | FastAPI routes for multi-instance control |

### Critical Anti-Patterns to Avoid

- ❌ Calling `config()` repeatedly → use `constants.py` instead
- ❌ Missing `await` on async calls → all dYdX client calls are async
- ❌ Skipping number formatting → exchange rejects imprecise values
- ❌ Continuing after atomic failures → orphaned positions occur
- ❌ Importing before `load_dotenv()` → config variables undefined

## Structure of Updated File

```
Section 1: System Architecture
   └─ Three-tier diagram, running modes, quick start

Section 2: Critical Patterns (5 key patterns with code examples)
   └─ Config loading, environment bootstrap, atomic execution,
      state persistence, error handling

Section 3: Key Files & Their Roles
   └─ Complete table of all critical files with purposes

Section 4: Trading Loop Flow
   └─ What happens when bot runs (orchestration)

Section 5: Development Workflows
   └─ Local setup, common tasks, testing patterns

Section 6: Integration Points
   └─ Frontend↔API, API↔Bot processes, WebSocket updates

Section 7: Anti-Patterns & Debugging
   └─ What to avoid, debugging checklist, performance tips

Section 8: Recent Updates (Nov 2025)
   └─ Key changes and clarifications
```

## For AI Agents Using These Instructions

### Immediate Productivity

When you start working on this codebase, use this flow:

1. **Understand the flow**: Read "System Architecture at a Glance" (2 min)
2. **Learn patterns**: Read "Critical Patterns" section (5 min)
3. **Know the files**: Scan "Key Files & Their Roles" (2 min)
4. **Write code**: Reference specific patterns as needed

### Example Usage

**When adding new configuration:**
→ Search for "Adding new config parameter" in Development Workflows section
→ Follow the 4 exact steps, referencing the config flow pattern

**When debugging trade execution:**
→ Jump to "Debugging Checklist" → "Orders not executing"
→ Use the 4-point checklist with file references

**When implementing API features:**
→ Check "Integration Points" for frontend↔API patterns
→ Reference `bot/bot_api_server.py` for actual FastAPI structure

## Files Affected

- **Created/Updated**: `.github/copilot-instructions.md`
- **Reference**: All 401 lines discoverable directly from actual codebase
- **Backward Compatible**: Preserves existing valuable content while removing outdated parts

---

## Next Steps (Optional)

Would you like me to:

1. **Generate specific instruction documents** for:
   - Frontend developers (React + TypeScript patterns)
   - Backend/Bot developers (Python async patterns)
   - DevOps (Docker, deployment workflows)

2. **Add more advanced topics**:
   - Backtest engine internals (`func_backtesting.py`)
   - WebSocket server architecture (`websocket_server.py`)
   - Database migration patterns (Alembic)
   - Encryption patterns (AES-256-GCM for dYdX credentials)

3. **Create quick-start for specific tasks**:
   - "Adding a new API endpoint" (5-min guide)
   - "Fixing a failed trade execution" (debugging flowchart)
   - "Setting up a new bot instance" (step-by-step)

Let me know if any sections need clarification or if you'd like me to expand on any patterns!
