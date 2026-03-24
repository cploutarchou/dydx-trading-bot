# Environment Matrix (Dev / Staging / Production)

Use this as the source of truth when preparing `.env.stack` values.

## Quick profile commands

- Dev stack: `make stack-up-dev`
- Prod-like stack: `make stack-up-prod`
- Baseline env check: `make stack-env-check`
- Strict prod check: `make stack-env-check-prod`

## Core matrix

| Variable | Development | Staging | Production |
|---|---|---|---|
| `ENVIRONMENT` | `development` | `staging` | `production` |
| `IS_TESTNET` | `true` | `true` (or `false` for pre-mainnet dress rehearsal) | `false` |
| `API_BYPASS_AUTH` | `false` | `false` | `false` |
| `SECRET_KEY` | strong non-placeholder | strong non-placeholder | strong non-placeholder |
| `POSTGRES_USER` | `dydx_bot` | dedicated staging user | dedicated prod user |
| `POSTGRES_PASSWORD` | local secret | staging secret | prod secret |
| `POSTGRES_DB` | `dydx_bot` | `dydx_bot_staging` | `dydx_bot_prod` |
| `POSTGRES_PORT` | `5432` | env-specific | env-specific |
| `REDIS_PORT` | `6379` | env-specific | env-specific |
| `API_PORT` | `8889` | `8889` | `8889` |
| `PROXY_HTTP_PORT` | `8080` | `8081` (example) | `80` / `443` via ingress |
| `BOT_API_WORKERS` | `1` | `2` | `2+` |
| `VITE_API_URL` | `http://localhost:8889` | staging API URL | production API URL |
| `DYDX_TESTNET_ADDRESS` | optional | required if `IS_TESTNET=true` | empty |
| `DYDX_TESTNET_MNEMONIC` | optional | required if `IS_TESTNET=true` | empty |
| `DYDX_MAINNET_ADDRESS` | empty | optional (`IS_TESTNET=false` only) | required |
| `DYDX_MAINNET_MNEMONIC` | empty | optional (`IS_TESTNET=false` only) | required |
| `LOKI_ENABLED` | `false` or `true` | `true` recommended | `true` recommended |
| `LOKI_URL` | optional | required if Loki enabled | required if Loki enabled |

## Security minimums

1. `SECRET_KEY` must be at least 32 chars and non-placeholder.
2. `API_BYPASS_AUTH` must stay `false` outside local experiments.
3. Never commit real secrets to git.
4. Rotate `BOT_API_TOKEN` and keep overlap via `BOT_API_TOKEN_PREVIOUS` during rotation windows.

## Recommended deployment flow

1. Copy `.env.stack` from template and fill environment-specific values.
2. Run `make stack-env-check`.
3. For staging/prod candidates, run `make stack-env-check-prod`.
4. Start profile (`make stack-up-dev` or `make stack-up-prod`).
5. Verify health endpoints and login/auth behavior before traffic.

## Notes for your current workspace

- `.env.stack` now exists and passes baseline validation.
- Strict prod validation currently fails until `SECRET_KEY` is replaced with a strong non-placeholder value.
