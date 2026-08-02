# AI Agents for dYdX Trading Bot Project

This directory contains AI agent definitions that provide specialized expertise for working on the dYdX trading bot project.

## Available Agents

### 🎯 Senior Bot Project Manager
**File**: [`senior-bot-project-manager.agent.md`](./senior-bot-project-manager.agent.md)
**Description**: Comprehensive agent with all required skills to manage the entire bot project

**Expertise Areas**:
- ✅ **Python & Async Development** - Async/await, performance, testing
- ✅ **Trading Domain** - Arbitrage, market-making, risk management
- ✅ **dYdX Protocol** - v4 API, perpetual futures, collateral management
- ✅ **API & Backend** - FastAPI, WebSocket, authentication
- ✅ **Database & Persistence** - PostgreSQL, Alembic, SQLAlchemy
- ✅ **Distributed Systems** - Celery, Redis/Valkey, NATS
- ✅ **DevOps & Deployment** - Docker, CI/CD, monitoring
- ✅ **Security & Compliance** - Authentication, encryption, audit
- ✅ **Operations & Reliability** - Incident response, disaster recovery
- ✅ **Project Management** - Architecture, documentation, stakeholder communication

**When to Use**:
- Managing the entire project
- Complex multi-component tasks
- Architectural decisions
- Incident response and troubleshooting
- Production deployments
- Cross-cutting concerns

### 🐍 Senior Python DeFi Runtime Agent
**File**: [`senior-python-defi-runtime.agent.md`](./senior-python-defi-runtime.agent.md)
**Description**: Specialized agent for bot implementation, trading runtime, and DeFi arbitrage

**Expertise Areas**:
- Python async development
- Trading systems implementation
- DeFi protocol integration
- Runtime safety and operational concerns

**When to Use**:
- Bot implementation work
- Trading strategy development
- Runtime/lifecycle changes
- Operational safety improvements

## Quick Reference
**File**: [`senior-agent-quick-reference.md`](./senior-agent-quick-reference.md)

A concise reference guide with:
- Immediate commands for common operations
- Project structure overview
- Critical safety rules
- Environment variables
- Emergency procedures
- Testing matrix
- Common workflows

## Usage

### Invoking Agents

To use the Senior Bot Project Manager:
```bash
# With Mistral Vibe
vibe --agent .github/agents/senior-bot-project-manager.agent.md "Your task here"
```

### Agent Selection Guide

| Task Type | Recommended Agent |
|-----------|------------------|
| Full project management | Senior Bot Project Manager |
| Trading strategy implementation | Senior Bot Project Manager or Senior Python DeFi Runtime |
| API endpoint development | Senior Bot Project Manager |
| Database migrations | Senior Bot Project Manager |
| Incident response | Senior Bot Project Manager |
| Code reviews | Senior Bot Project Manager |
| Runtime-specific changes | Senior Python DeFi Runtime |
| Quick reference needed | Quick Reference Guide |

## Agent Hierarchy

```
Senior Bot Project Manager (Most Comprehensive)
├── Senior Python DeFi Runtime Agent
└── Quick Reference Guide
```

The **Senior Bot Project Manager** is the most comprehensive agent that encompasses all skills required for the project. It should be your default choice for most tasks, especially those involving:

- Multiple components or systems
- Production-critical changes
- Architectural decisions
- Complex troubleshooting
- Project-wide concerns

## Best Practices

1. **Start with the Senior Bot Project Manager** for most tasks
2. **Use the Quick Reference** for common commands and patterns
3. **Consult AGENTS.md** in the repository root for project-specific constraints
4. **Always prioritize safety** - this is live-trading-facing software
5. **Follow the validation checklists** in the agent definitions

## Related Files

- `../AGENTS.md` - Repository-level guidance for all agents
- `../instructions/` - Task-specific instruction files
- `../prompts/` - AI prompt templates

## Maintaining Agents

When updating agents:
1. Keep expertise descriptions accurate and current
2. Reference the latest project structure and conventions
3. Update validation checklists with new requirements
4. Ensure consistency with `AGENTS.md` constraints
5. Test agent behavior with real project tasks