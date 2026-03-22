# Configuration Matrix

This matrix documents required vs optional environment settings by runtime mode.

## Shared core

Required in most modes:

- `ENVIRONMENT`
- `LOG_LEVEL`
- DB settings (`DB_TYPE`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`) when DB-backed mode is used

Optional but recommended:

- Loki settings (`LOKI_*`)
- Redis settings (`REDIS_*`)

## Mode: API server only

Required:

- `BOT_API_HOST`
- `BOT_API_PORT`
- `SECRET_KEY`
- `JWT_ALGORITHM`

Optional:

- `API_BYPASS_AUTH=true` (local/dev only)

## Mode: Worker instance (testnet validation)

Required:

- `IS_TESTNET=true`
- Bot file isolation settings (`BOT_STATE_DIR`, `BOT_AGENTS_FILE`, `BOT_PAIRS_FILE`)

Recommended safe defaults:

- `BOT_PLACE_TRADES=false` for first run
- low trade sizing values

## Mode: Trading with encrypted credentials

Required:

- `CREDENTIALS_ENCRYPTION_KEY`
- Active wallet credentials stored via credentials API path

Optional:

- Legacy direct wallet env values should remain unset/placeholders unless explicitly needed by current runtime path

## Mode: Notification-enabled

Required:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Mode: Email/password recovery

Required:

- `EMAIL_PROVIDER`
- provider-specific settings (`MAILGUN_*` or `SMTP_*`)

## Security notes

- Never commit real secrets in `.env`.
- Rotate any leaked tokens/keys immediately.
- Use different secrets/keys for test and production.
