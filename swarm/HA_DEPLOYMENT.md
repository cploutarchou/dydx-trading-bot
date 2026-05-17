# Swarm HA deployment (PostgreSQL + Redis)

This repository now includes production-oriented Docker Swarm stacks for:

- PostgreSQL HA (3-node `postgresql-repmgr` + 2-node `pgpool` endpoint)
- Redis HA (1 primary + 2 replicas + 3 sentinels + 2-node TCP proxy endpoint)

Files:

- `swarm/stack-postgres-ha.yml`
- `swarm/stack-redis-ha.yml`
- `swarm/config/redis-haproxy.cfg`
- `app.yml` (frontend)
- `app-api.yml`
- `app-backend.yml`
- `app-worker.yml`

## 1) Prerequisites

- Swarm cluster initialized and healthy
- Overlay network `internal` exists (shared by app/backend/bot/worker)
- `swarmctl` context selected for `staging` (or your target env)

## 2) Create required Docker secrets (one-time)

Run on a Swarm manager:

- `pg_su_password`
- `pg_app_password`
- `pg_repmgr_password`
- `pgpool_admin_password`
- `redis_password`

Example pattern (interactive):

```bash
echo -n 'replace-me' | docker secret create pg_su_password -
echo -n 'replace-me' | docker secret create pg_app_password -
echo -n 'replace-me' | docker secret create pg_repmgr_password -
echo -n 'replace-me' | docker secret create pgpool_admin_password -
echo -n 'replace-me' | docker secret create redis_password -
```

## 2.1) Create required application secrets (one-time)

These are referenced by `app-api.yml`, `app-backend.yml`, and `app-worker.yml`:

- `dydx-bot-db-password`
- `dydx-db-password`
- `dydx-postgres-password`
- `dydx-redis-password`
- `dydx-jwt-secret-key`
- `dydx-secret-key`
- `dydx-encryption-key`
- `dydx-bot-api-token`

Example pattern:

```bash
echo -n 'replace-me' | docker secret create dydx-bot-db-password -
echo -n 'replace-me' | docker secret create dydx-db-password -
echo -n 'replace-me' | docker secret create dydx-postgres-password -
echo -n 'replace-me' | docker secret create dydx-redis-password -
echo -n 'replace-me' | docker secret create dydx-jwt-secret-key -
echo -n 'replace-me' | docker secret create dydx-secret-key -
echo -n 'replace-me' | docker secret create dydx-encryption-key -
echo -n 'replace-me' | docker secret create dydx-bot-api-token -
```

## 3) Deploy with swarmctl

From this repo root (`/home/chris/workspace/dydx-trading-bot`):

```bash
swarmctl stack deploy dydx-postgres-ha -c swarm/stack-postgres-ha.yml --env staging
swarmctl stack deploy dydx-redis-ha -c swarm/stack-redis-ha.yml --env staging

swarmctl stack status dydx-postgres-ha --env staging
swarmctl stack status dydx-redis-ha --env staging
```

Then deploy app manifests in this order:

```bash
swarmctl validate -f app-api.yml --env staging
swarmctl validate -f app-backend.yml --env staging
swarmctl validate -f app-worker.yml --env staging
swarmctl validate -f app.yml --env staging

swarmctl apply -f app-api.yml --env staging --wait --timeout 5m
swarmctl apply -f app-backend.yml --env staging --wait --timeout 5m
swarmctl apply -f app-worker.yml --env staging --wait --timeout 10m
swarmctl apply -f app.yml --env staging --wait --timeout 5m
```

## 4) App connection endpoints

Use these service endpoints from your backend/bot/worker app manifests:

- PostgreSQL endpoint: `pgpool:5432`
- Redis endpoint (compatible host:port): `redis-master-proxy:6379`
- Redis sentinel endpoint (for future sentinel-aware clients): `redis-sentinel:26379`, master set `mymaster`

## 5) Env updates to apply in app manifests

For backend/bot/worker env blocks, replace old external IPs with:

- `DB_HOST=pgpool`
- `POSTGRES_HOST=pgpool`
- `BOT_DB_HOST=pgpool`
- `DB_PORT=5432`, `POSTGRES_PORT=5432`, `BOT_DB_PORT=5432`
- `REDIS_HOST=redis-master-proxy`
- `REDIS_PORT=6379`

## 6) Operational notes

- Postgres writes go through `pgpool`, with automatic failover managed by `repmgr`.
- Redis failover is managed by Sentinel; the proxy gives existing host:port clients a stable endpoint.
- For strict Redis master-awareness and richer failover behavior, upgrade backend/bot clients to Sentinel-aware clients over time.
- Keep all DB/Redis traffic on internal overlay networks only.

## 7) GitHub Actions automation with swarmctl

A workflow has been added at:

- `.github/workflows/swarmctl-deploy.yml`
- `.github/workflows/swarmctl-auto-deploy.yml`

It supports:

- automatic manifest validation on push/PR changes for `app*.yml` and `swarm/**`
- manual deploy (`workflow_dispatch`) with inputs for:
	- environment
	- image_tag (immutable tag recommended, e.g. commit SHA)
	- deploy_infra (true/false)
	- deploy_apps (true/false)
	- dry_run (true/false)

Required GitHub secret:

- `SWARMCTL_CONFIG_BASE64`: base64-encoded content of `~/.swarmctl/config.yaml`

Manifest source-of-truth policy (to avoid `platform.yml` confusion):

- `app.yml`, `app-api.yml`, `app-backend.yml`, `app-worker.yml` are the deployment source of truth for `swarmctl apply`.
- `swarm/stack-postgres-ha.yml` and `swarm/stack-redis-ha.yml` are the source of truth for infra stacks via `swarmctl stack deploy`.
- `platform.yml` is retained for legacy/meta mapping and must be kept in sync with `app*.yml` when changed.
- CI enforces this policy: if `platform.yml` changes without corresponding `app*.yml` updates, validation fails.

Optional GitHub repository variables (for auto-deploy behavior):

- `SWARMCTL_AUTO_ENV` (default: `staging`)
- `SWARMCTL_AUTO_DEPLOY_INFRA` (default: `false`)
- `SWARMCTL_AUTO_DEPLOY_APPS` (default: `true`)
- `SWARMCTL_AUTO_DRY_RUN` (default: `false`)
- `SWARMCTL_REPO_REF` (default: `swarmctl-v0.1.17`)

Credential hardening implemented in workflow:

- decoded `~/.swarmctl/config.yaml` is created with `umask 077` and `chmod 600`
- sensitive config file is shredded/removed in a final cleanup step
- use GitHub Environments + required reviewers for production deploy approvals

Generate and set it from your operator workstation:

```bash
base64 -w 0 ~/.swarmctl/config.yaml
```

Then save output into GitHub repository/environment secret `SWARMCTL_CONFIG_BASE64`.

Recommended production flow:

1. Run workflow with `dry_run=true`, `deploy_infra=false`, `deploy_apps=true`.
2. Review validation/plan output.
3. Run workflow with `dry_run=false`, `deploy_infra=true` (first run only), `deploy_apps=true`.
4. For subsequent app-only releases, keep `deploy_infra=false` and set `image_tag` to the published immutable tag.

Tag policy guardrail:

- `image_tag=latest` is allowed only for `staging`.
- For non-staging environments (for example `production`), workflow deploy is blocked unless `image_tag` is immutable (for example `sha-<commit>`).
- Non-staging allowlist patterns:
	- `sha-<hex>` (7 to 64 hex chars), e.g. `sha-214d3b7`
	- semantic version tags, e.g. `v1.2.3`, `1.2.3`, `1.2.3-rc.1`
- Non-staging examples that are blocked: `latest`, `dev`, `test`, `main`, `feature-x`.

Auto-deploy flow:

1. `Build and Push Docker Images` completes successfully on `master`/`main` push.
2. `swarmctl-auto-deploy.yml` computes `image_tag=sha-<short_sha>` from that commit.
3. It runs a preflight tag-policy check (blocks invalid non-staging tags before dispatch).
4. It dispatches `swarmctl-deploy.yml` with your configured env/flags.
