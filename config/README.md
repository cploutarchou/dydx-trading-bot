# Shared Environment Configuration

This directory is the structured source of truth for monorepo runtime configuration.

## Layout

- `environments/development.env.json`
- `environments/production.env.json`
- `secrets/development.secrets.example.json`
- `secrets/production.secrets.example.json`

Optional local files that should not be committed:

- `secrets/development.secrets.json`
- `secrets/production.secrets.json`
- `secrets/development.secrets.sops.json`
- `secrets/production.secrets.sops.json`

## Security model

- Passwords in the database remain hashed only.
- Runtime secrets that the app must actually use cannot be hash-only.
- For reversible secrets, use encryption:
  - SOPS for repo-managed config files
  - the existing backend encryption-at-rest for DB-stored API keys and seed phrases

Hashing is one-way. It is not possible to safely "hash and unhash" the same secret.

## How apps use this

The frontend, backend, and bot still consume the shared repo-root `.env`, because that is the common runtime format across Vite, Go, and Python in this monorepo.

Generate that file from the structured config with:

```bash
python3 scripts/render_env.py --environment development --output .env
```

or:

```bash
make stack-env
```

## SOPS usage

If `sops` is installed and `config/secrets/<environment>.secrets.sops.json` exists, the render script will decrypt it automatically.

Typical flow:

1. Copy `config/secrets/development.secrets.example.json` to `config/secrets/development.secrets.json`
2. Fill in the real values
3. Encrypt it with your own SOPS/age or KMS setup
4. Remove the plain JSON copy once the encrypted file exists

The render order is:

1. base profile from `config/environments/<environment>.env.json`
2. encrypted secrets from `config/secrets/<environment>.secrets.sops.json`
3. plain secrets from `config/secrets/<environment>.secrets.json`
4. example secrets from `config/secrets/<environment>.secrets.example.json`

Earlier layers are overridden by later ones.
