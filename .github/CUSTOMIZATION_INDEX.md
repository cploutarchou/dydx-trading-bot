# .github Customization Index

Use this index to quickly find the agent/instruction/skill/prompt/workflow setup for this repository.

## Start-of-task rule

For each new task, review:

1. `.github/copilot-instructions.md`
2. This file (`.github/CUSTOMIZATION_INDEX.md`)
3. The most relevant skill/agent/prompt listed below

## Core workspace instructions

- `.github/copilot-instructions.md`  
  Cross-repo defaults for architecture, ports, build/test commands, and critical trading safety constraints.

## File-scoped instructions

- `.github/instructions/python-trading.instructions.md`  
  Deprecated file (historical only), scoped to `DO_NOT_USE/**`.

## Agents

- `.github/agents/senior-defi-dev.agent.md`  
  Agent mode for trading strategy, DeFi execution, quant/stat-arb, and full-stack bot changes.

## Skills

- `.github/skills/defi-python-algo-trading/SKILL.md`  
  Production-safe Python trading workflow with quality gates:
  - atomic paired execution safety
  - exchange precision handling
  - UTC-safe datetime usage
  - async API correctness
  - risk/DeFi/performance validation

## Prompts

- `.github/prompts/defi-risk-review.prompt.md`  
  Focused risk review (execution, exposure, slippage/liquidity, funding, recovery).

- `.github/prompts/defi-predeploy-go-no-go.prompt.md`  
  Pre-deploy go/no-go gate with blockers and mitigations.

- `.github/prompts/defi-incident-hotfix-go-no-go.prompt.md`  
  Incident-mode emergency go/no-go gate.

## Workflow automation

- `.github/workflows/ci.yml`  
  CI checks for Python lint/tests, Go WS smoke tests, and Docker image smoke validation.

## Additional repo guidance

- `.github/git-commit-instructions.md`  
  Commit message, branch naming, and PR hygiene guidance.
