# Shared Runtime Configuration

This directory is the structured source of truth for monorepo runtime configuration.

## Layout

- `profiles/development.config.enc.json`
- `profiles/production.config.enc.json`
- `profiles/example.config.json`

## Security model

- Each environment uses one encrypted profile file committed to the repo.
- The example file is plain JSON only to document structure and bootstrap new profiles.
- The repo-owned binary key lives at `.configkey.bin` in the monorepo root.
- Passwords in the database remain hashed only.
- Runtime secrets that the app must use stay encrypted and are decrypted only at load time.

Hashing is one-way. It is not possible to safely "hash and unhash" the same secret, so config files use encryption, not hashing.

## How apps use this

The encrypted profile is the secure source of truth, but local service startup uses a shared decrypted runtime file:

- source profile: `config/profiles/<environment>.config.enc.json`
- generated runtime file: `run.json`
- optional runtime override: `APP_RUN_CONFIG_FILE=/absolute/path/to/run.json`
- optional profile override: `APP_CONFIG_FILE=/absolute/path/to/file.config.enc.json`
- optional key override: `APP_CONFIG_KEY_FILE=/absolute/path/to/.configkey.bin`

Open and edit the active config profile with:

```bash
make dev-config
make prod-config
```

Then generate the shared runtime file with:

```bash
make dev
make prod
```

Those commands decrypt the encrypted profile into `run.json`, which is what the services read by default.

## Key workflow

Bootstrap the repo-owned key flow with:

```bash
make config-keygen
```

That command:

- creates repo-root `.configkey.bin`
- prints a shareable config token
- can be repeated on other machines with `make install-config-key TOKEN=...`

Rotate the key later with:

```bash
make config-key-rotate
```

That command:

- decrypts the committed encrypted profiles with the current key
- re-encrypts them with a fresh key
- saves the previous key as `.configkey.bin.bak`
- prints the new shareable token for DevOps

Typical flow:

1. Run `make config-keygen`
2. Run `make dev-config`
3. Save the encrypted profile
4. Run `make dev`
5. Start or restart the services
