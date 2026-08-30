# Service Profile — platform, infrastructure, and configuration

Read before touching docker-compose files, `deploy/`, `config/`, root
Makefile targets, or scripts.

## Scope

Local/stack infrastructure, encrypted configuration, k8s deployment
manifests, operational tooling.

## Components

- `docker-compose.infra.yml` — Postgres, Valkey, NATS, ClickHouse, MinIO (dev defaults; arm64 variant available)
- `docker-compose.stack.yml` — full stack: frontend, backend-api, bot-api, bot-worker + infra
- `docker-compose.bot-worker.yml` — worker-only composition
- `deploy/k8s/`, `deploy/k8s-next/` — kustomize base + overlays (staging/production); CI validates builds
- `config/profiles/*.config.enc.json` — encrypted runtime profiles (source of truth); `run.json` generated
- `scripts/` — governance + secret scanners (`validate_docs_governance.py`, `check_no_plaintext_k8s_secrets.py`)

## Configuration flow (strict)

`config/profiles/*.config.enc.json` --(`make dev-config`/`make dev`)--> `run.json`
--> exported env at service start --> parsed by service config loaders
(bot: `BotSettings.from_env`; frontend: `vite.config.ts` startup). `.env` is
legacy. Never hand-edit `run.json`; never commit keys (`run.json`,
`.configkey.bin` are gitignored).

## Canonical commands

```
make config-keygen            # first-time key
make dev                      # generate run.json from dev profile
make infra-up / infra-ps / infra-down
make stack-up-dev / stack-logs / stack-down
make validate-k8s-secrets
make docs-governance
```

## Validation

CI: compose `config` validation, required-service presence checks,
kustomize build for base/staging/production, plaintext-secret scan. Local
equivalents run via root Makefile targets above.

## Security concerns

- Placeholder infra credentials (`change-me-*`) must not survive into any
  non-dev environment (backend baseline enforces for the app; infra envs
  are operator responsibility).
- k8s secrets: only `*.local-secret.yaml`/generated patterns; scanner is a
  blocking CI gate.
- Ports: frontend 5173, backend 8888, bot API 8889, infra on published
  container ports (5432/6379/4222/8123/9010).

## Common failure modes

Editing generated `run.json`; forgetting the arm64 compose variant; adding
services without updating the required-services CI list; plaintext secrets
in kustomize overlays.

## Evidence sources

Root `Makefile`, `docker-compose.*.yml`, `deploy/k8s-next/`, `.gitignore`,
`.github/workflows/bot-quality.yml`, `config/profiles/`.
