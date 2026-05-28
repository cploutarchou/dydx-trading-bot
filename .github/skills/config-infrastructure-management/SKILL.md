---
name: "config-infrastructure-management"
description: "Design, implement, and validate runtime configuration, encrypted profiles, deployment config, environment management, and infrastructure-as-code for this dYdX trading bot monorepo. Use when: setting up new environments, managing encrypted profiles, generating run.json, deploying Docker stacks, managing secrets, configuring infrastructure, or troubleshooting config loading."
argument-hint: "Describe the environment target, config layer (profiles/run.json/.env), and whether the change affects local dev, testnet, or production."
user-invocable: true
disable-model-invocation: false
---

# Config & Infrastructure Management

Design and maintain production-grade runtime configuration, encrypted profiles, deployment manifests, and infrastructure orchestration for the dYdX trading bot platform.

## Scope

This skill owns:

- **Structured config**: encrypted profiles in `config/profiles/*.config.enc.json`
- **Generated config**: `run.json` generation and validation
- **Environment setup**: `.env` files, environment variable precedence
- **Docker/Compose**: `platform.yml`, Dockerfile configurations
- **Deployment config**: environment-specific overrides, rollout playbooks
- **Secrets management**: encrypted key handling, credential rotation, security boundaries
- **Infrastructure tooling**: Makefile targets, setup scripts, bootstrapping

## When to Use

Use this skill when you need to:

- Add a new environment (e.g., `staging.config.enc.json`)
- Troubleshoot config loading failures ("env var not found" errors)
- Set up local dev environment with proper secrets/profiles
- Modify Docker Compose stack configuration
- Implement secret rotation or credential management
- Design environment-specific runtime behavior
- Document infrastructure setup procedures
- Validate config integrity across environments

## Operating Principles

1. **Config flows from profiles**: Treat `config/profiles/` as the source of truth. All runtime values should ultimately come from there or from explicit environment overrides.

2. **Generate, don't hand-edit**: `run.json` is generated from profiles. Never manually edit `run.json` for long-term changes; update the profile and regenerate.

3. **Keep secrets encrypted**: All sensitive values in profiles must be AES-256 encrypted. Use `make config-keygen` and the configured key file.

4. **Preserve per-environment isolation**: Never share encrypted keys across environments. Mainnet and testnet profiles must remain separate and encrypted independently.

5. **Document fallback chains**: If a config key can come from multiple sources (env var, profile, `.env`, default), document that chain clearly.

## Quality Checklist

- [ ] New config values are added to appropriate profile, not hardcoded in code
- [ ] Encrypted profiles use consistent key format and cipher
- [ ] Environment variable precedence is explicit (profile override precedence is clear)
- [ ] Secrets are never logged or exposed in outputs
- [ ] Docker Compose environment variables match profile exports
- [ ] New environments have corresponding encrypted profiles
- [ ] Makefile targets for `config-keygen`, `dev-config`, and `stack-up-dev` still work
- [ ] Setup documentation reflects any new config requirements
- [ ] Rollout playbook includes env-specific steps if applicable

## Related Docs

- `config/README.md` — Structured config guide
- `.github/copilot-instructions.md` — Root config flow defaults
- `Makefile` — Config generation and stack management targets
- `bot/.github/copilot-instructions.md` — Bot config loading behavior
- `backend/.github/copilot-instructions.md` — Backend env handling

## Common Workflows

### Add a New Runtime Flag

1. Identify the target environment(s): local dev, testnet, mainnet
2. Add the key to the appropriate profile in `config/profiles/`
3. Update `bot/src/constants.py` or backend config handler to import it
4. Regenerate `run.json` via `make dev-config`
5. Test locally with `make stack-up-dev` or service-level startup

### Troubleshoot Config Loading

1. Check `run.json` exists and is not stale (regenerate if unsure)
2. Trace env var usage in service code (search in `constants.py`, `config.go`, etc.)
3. Verify profile file matches target environment
4. Check decryption key exists and matches profile encryption
5. Review load order: file env values → dotenv → profile → defaults
6. Run `make validate-config` or equivalent to check for errors

### Deploy to New Environment

1. Generate encrypted profile: `make config-keygen && cp config/profiles/development.config.enc.json config/profiles/staging.config.enc.json` (then encrypt with new key)
2. Update `Makefile` or environment setup to reference new profile
3. Configure CI/CD or manual deploy script to load new profile
4. Test with `make infra-up` + service startup in target environment
5. Document fallback behavior if config is incomplete

## Validation

After any config change, verify:

- Plaintext secrets are NOT in code, logs, or git history
- `run.json` is regenerated and up-to-date
- Local stack can start: `make stack-up-dev && make stack-ps`
- All required env vars are present (no missing required config errors)
- Service ports and addresses match expected values
- Encrypted profiles decrypt correctly with the configured key
