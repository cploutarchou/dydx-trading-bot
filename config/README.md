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

Open and edit the active config profile with:

```bash
make dev-config
make prod-config
```

Those commands open the profile in your editor, let you edit the matching secrets file, and then re-render the repo-root `.env` after the editor closes.

## SOPS usage

If `sops` is installed and the selected secrets file is SOPS-encrypted, the render script will decrypt it automatically.

Typical flow:

1. Copy `config/secrets/development.secrets.example.json` to `config/secrets/development.secrets.json`
2. Fill in the real values
3. Copy `config/.sops.example.yaml` to `.sops.yaml` and replace the age recipient with your own
4. Encrypt it with your own SOPS/age or KMS setup
   Example: `sops --encrypt --in-place config/secrets/development.secrets.json`
5. Remove the plain JSON copy once the encrypted file exists

To install local tooling:

```bash
make install-sops
```

That command now:

- installs `sops`, `age`, and `age-keygen` into `~/.local/bin` when needed
- creates `~/.config/sops/age/keys.txt` if it does not already exist
- prints your public age recipient
- bootstraps repo-root `.sops.yaml` from the example template if it is missing

The render order is:

1. base profile from `config/environments/<environment>.env.json`
2. encrypted secrets from `config/secrets/<environment>.secrets.sops.json`
3. local secrets from `config/secrets/<environment>.secrets.json`
4. example secrets from `config/secrets/<environment>.secrets.example.json`

Earlier layers are overridden by later ones.
