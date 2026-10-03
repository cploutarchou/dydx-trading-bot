# Platform Overview

## What this is

A self-hosted statistical-arbitrage trading system for dYdX v4 perpetuals,
operated through a web dashboard. It is **software for running a strategy**;
it makes no claims about profitability.

## Services and integration boundary

The integration boundary is strict and one-directional:

```
frontend (React/Vite, :5173)
    -> backend (Go/Gin API gateway, :8888)
        -> bot (Python FastAPI control plane, :8889)
            -> worker subprocesses + PostgreSQL/Valkey/NATS/ClickHouse/MinIO
```

- **frontend/** — operator dashboard: strategies, backtests, live positions.
- **backend/** — authn/authz (JWT + sessions + MFA), tenancy, delegation of
  bot actions, PostgreSQL persistence for platform data.
- **bot/** — trading runtime: cointegration pair selection, z-score entries,
  atomic paired execution, exit management, backtests, per-instance workers.

## Runtime model

- Bot instances run as **separate worker processes** managed by
  `bot/src/bot_instance_manager.py`, with isolated state files under
  `bot_states/` and per-instance trading parameters injected as `BOT_*` env
  vars at spawn.
- Structured configuration flows from encrypted profiles
  (`config/profiles/*.config.enc.json`) through generated `run.json` into
  service env. See [`.github/skills/config-infrastructure-management/SKILL.md`](../.github/skills/config-infrastructure-management/SKILL.md).
- Exchange interaction is dYdX v4 (indexer REST + node gRPC). Testnet and
  mainnet are selected per instance via its credentials.

## Safety posture

- Fail-closed behavior on unknown order, position, balance, and risk states.
- Atomic paired execution: a filled leg whose pair leg fails is emergency
  closed (reduce-only) with critical alerts.
- Kill switches: `abortAllPositions`, portfolio risk guard, circuit breakers.
  See the risk-control matrix in [bot/docs/bot-risk-control-matrix.md](../bot/docs/bot-risk-control-matrix.md).
