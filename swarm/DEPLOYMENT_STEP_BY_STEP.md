# dYdX Swarm Deployment — Step-by-Step Guide

This guide is the operator runbook for installing prerequisites and deploying this project with `swarmctl`.

It covers:

- local machine prerequisites
- Swarm cluster prerequisites
- domain setup
- secret setup
- manual deployment
- GitHub Actions deployment automation

Start here navigation:

- Monorepo overview: [`README.md`](../README.md)
- HA-focused deployment details: [`swarm/HA_DEPLOYMENT.md`](HA_DEPLOYMENT.md)

---

## 1) Local prerequisites

Install on your workstation:

- `git`
- `docker` CLI
- `ssh`
- `jq`
- `base64`
- `swarmctl` (recommended: `v0.1.19` or newer)

Optional (only if building swarmctl from source):

- `go` (1.22+)

Verify:

```bash
swarmctl version
docker version
ssh -i ~/.ssh/<your_key> <user>@<swarm-manager-host>
swarmctl infra ips --env staging
swarmctl infra topology --env staging
```

---

## 2) Swarm cluster prerequisites

Your target environment must have:

- Docker Swarm initialized and healthy
- at least one manager reachable from your workstation
- required overlay networks (`internal`; and `public` where needed)
- DNS records pointing to your ingress IP

Check basic status:

```bash
swarmctl node list --env staging
swarmctl network list --env staging
swarmctl infra ips --env staging
swarmctl infra topology --env staging
```

> **Note**: Starting with `swarmctl v0.1.17`, domain onboarding is smarter and less manual. The `swarmctl domain add` command now resolves ingress IPs automatically in the following order:
> 1. Explicit `--ingress-ip` flag (highest priority).
> 2. Context `ingressIP`.
> 3. DNS resolution from the context `managerHost`.

---

## 3) Configure swarmctl context

Set and select your deployment context:

```bash
swarmctl context set staging \
  --manager <manager-host> \
  --user <ssh-user> \
  --key ~/.ssh/<ssh-key> \
  --environment staging

swarmctl context use staging
swarmctl context current
```

> In `swarmctl v0.1.17+`, `domain add` ingress IP resolution order is:
> 1) explicit `--ingress-ip`, 2) context `ingressIP`, 3) auto-detect by resolving context `managerHost` to IPv4.

---

## 4) Domain setup (register + verify + claim)

Register your base domains:

- `your-domain.com`
- `domain1.com`
- `domain2.com`
- `domain3.com`

Replace placeholders above with your real domains.

Example:

```bash
swarmctl domain add your-domain.com --env staging --owner platform --allow-subdomains
swarmctl domain verify your-domain.com --env staging
```

Claim the app hosts:

```bash
swarmctl domain claim staging.your-domain.com --env staging --app dydx-trading-bot-frontend --owner platform
swarmctl domain claim api.staging.your-domain.com --env staging --app dydx-trading-bot-backend --owner platform
```

---

## 5) Required secrets in Swarm

Create these once on a Swarm manager.

### 5.1 Infra secrets

- `pg_su_password`
- `pg_app_password`
- `pg_repmgr_password`
- `pgpool_admin_password`
- `redis_password`

### 5.2 App secrets

- `dydx-bot-db-password`
- `dydx-db-password`
- `dydx-postgres-password`
- `dydx-redis-password`
- `dydx-jwt-secret-key`
- `dydx-secret-key`
- `dydx-encryption-key`
- `dydx-bot-api-token`

Creation pattern:

```bash
echo -n '<value>' | docker secret create <secret-name> -
```

---

## 6) Deployment source-of-truth policy

To avoid manifest confusion:

- App deployment source of truth:
  - `app.yml`
  - `app-api.yml`
  - `app-backend.yml`
  - `app-worker.yml`
- Infra deployment source of truth:
  - `swarm/stack-traefik.yml`
  - `swarm/stack-postgres-ha.yml`
  - `swarm/stack-redis-ha.yml`
- `platform.yml` is legacy/meta mapping and must stay synced when edited.

CI enforces this policy.

---

## 7) Manual deployment (first run recommended)

Run from repo root:

```bash
swarmctl validate -f app-api.yml --env staging
swarmctl validate -f app-backend.yml --env staging
swarmctl validate -f app-worker.yml --env staging
swarmctl validate -f app.yml --env staging
```

Deploy HA infra:

```bash
swarmctl stack deploy traefik -c swarm/stack-traefik.yml --env staging
swarmctl stack deploy dydx-postgres-ha -c swarm/stack-postgres-ha.yml --env staging
swarmctl stack deploy dydx-redis-ha -c swarm/stack-redis-ha.yml --env staging

swarmctl stack status traefik --env staging
swarmctl stack status dydx-postgres-ha --env staging
swarmctl stack status dydx-redis-ha --env staging
```

Deploy apps (order matters):

```bash
swarmctl apply -f app-api.yml --env staging --wait --timeout 5m
swarmctl apply -f app-backend.yml --env staging --wait --timeout 5m
swarmctl apply -f app-worker.yml --env staging --wait --timeout 10m
swarmctl apply -f app.yml --env staging --wait --timeout 5m
```

Check rollout:

```bash
swarmctl rollout status dydx-trading-bot-api --env staging
swarmctl rollout status dydx-trading-bot-backend --env staging
swarmctl rollout status dydx-trading-bot-worker --env staging
swarmctl rollout status dydx-trading-bot-frontend --env staging
```

---

## 8) GitHub prerequisites for CI/CD deployment

### 8.1 Required secrets

- `SWARMCTL_CONFIG_BASE64`
- `SWARM_SSH_PRIVATE_KEY`
- `ORCHESTRATOR_WORKFLOW_TOKEN` (PAT with read access to `cploutarchou/server-orchestrator`)

Generate locally:

```bash
base64 -w 0 ~/.swarmctl/config.yaml
```

For SSH key (the key used by your swarmctl context), copy the private key content into GitHub as a multiline secret:

```bash
cat ~/.ssh/<your-ssh-key>
```

Copy outputs into GitHub repository/environment secrets.

`ORCHESTRATOR_WORKFLOW_TOKEN` should be a GitHub PAT that can read private repositories (or at minimum has access to `cploutarchou/server-orchestrator`) so cross-repository checkout in workflows can succeed.

### 8.2 Recommended repository variables

- `SWARMCTL_REPO_REF=master`
- `SWARMCTL_AUTO_ENV=staging`
- `SWARMCTL_AUTO_DEPLOY_INFRA=false`
- `SWARMCTL_AUTO_DEPLOY_APPS=true`
- `SWARMCTL_AUTO_DRY_RUN=false`

### 8.3 Recommended GitHub Environments

Create `staging` and `production` environments with:

- required reviewers for production
- environment-scoped secrets (if applicable)

---

## 9) GitHub Actions workflows used

- `.github/workflows/swarmctl-deploy.yml`
  - validates manifests on push/PR
  - manual `workflow_dispatch` deploy path
- `.github/workflows/swarmctl-auto-deploy.yml`
  - triggers after successful Docker image publish on `main/master`
  - computes `image_tag=sha-<short_sha>`
  - preflight-checks tag policy before dispatch

---

## 10) Tag security policy

- `staging`: flexible tags allowed (including `latest`)
- non-staging (e.g., production): only immutable/controlled tags allowed
  - `sha-<hex>` (7-64 chars)
  - semver-like tags (`v1.2.3`, `1.2.3`, `1.2.3-rc.1`)

Examples blocked in non-staging:

- `latest`
- `dev`
- `test`
- `main`
- `feature-x`

---

## 11) Recommended production deployment flow

1. Run `swarmctl-deploy` with `dry_run=true` first.
2. Review validate/plan output.
3. Run with `dry_run=false`, immutable `image_tag`.
4. Keep `deploy_infra=false` unless infra changed.
5. Verify rollout status and logs.

> **Production Tag Policy**:
> - Only immutable tags are allowed (e.g., `sha-<commit>` or semver-like tags `v1.2.3`).
> - Examples of blocked tags: `latest`, `dev`, `test`, `main`, `feature-x`.

> **Production Environment Validation**:
> - Ensure all nodes are `ready/active` using `swarmctl infra ips --env production`.
> - Verify cluster topology with `swarmctl infra topology --env production`.
> - Confirm required networks (`internal`, `public`) are attachable.

---

## 12) Quick troubleshooting

- `swarmctl context current` fails:
  - verify `~/.swarmctl/config.yaml`
  - verify manager SSH reachability
- `domain claim` fails:
  - ensure base domain is registered + verified for the same environment
- `swarmctl infra` commands fail:
  - Starting with `swarmctl v0.1.21`, infra commands (`infra ips`, `infra topology`) include robust fallbacks for mixed/legacy environments. Ensure Docker nodes are reachable via `docker node ls` or `docker inspect`.
- secret-related app failures:
  - verify all required secrets exist in Swarm
- deploy blocked by tag policy:
  - use `sha-<commit>` or semver tag for non-staging

---

## 13) Files you should know

- `swarm/HA_DEPLOYMENT.md`
- `swarm/stack-traefik.yml`
- `swarm/stack-postgres-ha.yml`
- `swarm/stack-redis-ha.yml`
- `app.yml`, `app-api.yml`, `app-backend.yml`, `app-worker.yml`
- `.github/workflows/swarmctl-deploy.yml`
- `.github/workflows/swarmctl-auto-deploy.yml`
