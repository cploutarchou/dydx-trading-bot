# Development Workflow

## Setup

Follow [LOCAL_SETUP_GUIDE.md](../LOCAL_SETUP_GUIDE.md) first (Python 3.12,
Go, Node 24, Docker). Generate the config key and dev profile with
`make config-keygen` / `make dev-config`, then `make dev` to produce `run.json`.

## Everyday commands

| Area | Command |
| --- | --- |
| Infra (Postgres/Valkey/NATS/ClickHouse/MinIO) | `make infra-up`, `make infra-down` |
| Full dev stack | `make stack-up-dev`, `make stack-logs`, `make stack-down` |
| Bot tests (hermetic; safe with infra running) | `cd bot && python -m pytest tests/` |
| Bot lint / types | `make lint` (bot), `python -m mypy src` (in bot/) |
| Backend | `cd backend && make test && make lint && make build` |
| Frontend | `cd frontend && npm run lint && npm run typecheck && npm run test:contracts && npm run build` |
| Pre-commit hooks | `pre-commit run --all-files` |

## Conventions

- Start every task by reading [`.github/copilot-instructions.md`](../.github/copilot-instructions.md)
  and [`.github/CUSTOMIZATION_INDEX.md`](../.github/CUSTOMIZATION_INDEX.md).
- Trading-code rules (atomic pair execution, UTC datetimes, async awaits,
  precision formatting) are in
  [`.github/skills/defi-python-algo-trading/SKILL.md`](../.github/skills/defi-python-algo-trading/SKILL.md).
- Commit style: Conventional Commits (see [`.github/git-commit-instructions.md`](../.github/git-commit-instructions.md)).
- Behavior changes update the touched service's docs in the same change.

## Testing posture

The bot test suite is hermetic by design: it runs against in-memory/file
stores and ignores locally running infrastructure (DB/artifact backends are
force-isolated in `bot/tests/conftest.py`). CI mirrors this via
`.ci-run.json`. Never weaken assertions or disable tests to make a run pass.
