# Shared Config

This directory is the structured configuration source of truth for the monorepo.

## Files

- `profiles/development.config.enc.json`
- `profiles/production.config.enc.json`
- `profiles/example.config.json`

## Model

- encrypted profiles are committed to the repo
- the repo key lives at root `.configkey.bin`
- local startup reads the generated root `run.json`
- services can override the default runtime path with `APP_RUN_CONFIG_FILE`

## Standard Flow

```bash
make config-keygen
make dev-config
make dev
```

For production:

```bash
make prod-config
make prod
```

## Important Runtime Notes

- `run.json` is generated, not hand-maintained
- backend and bot can use different database targets from the same structured profile
- the bot supports dedicated database fields via `BOT_DB_*` and `BOT_DB_CUTOVER_MODE`

## Security Rules

- never commit decrypted secrets beyond the intended generated runtime file flow
- never replace encryption with hashing for recoverable runtime secrets
- rotate the key with `make config-key-rotate` when needed

## Related Docs

- [Root README](/home/chris/workspace/dydx-trading-bot/README.md)
- [Development Workflow](/home/chris/workspace/dydx-trading-bot/docs/DEVELOPMENT.md)
- [Operations Guide](/home/chris/workspace/dydx-trading-bot/docs/OPERATIONS.md)
