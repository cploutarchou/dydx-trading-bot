---
name: swarmctl-production-deployment
description: "Deploy, validate, and troubleshoot production releases for this dYdX monorepo using swarmctl, Docker Swarm, GHCR, and GitHub Actions. Use for production deploys, master-merge auto-deploy setup, image tag selection, HA infra secret checks, swarmctl workflow debugging, and rollout verification."
argument-hint: "What production deployment outcome do you need: manual deploy, auto-deploy setup, swarmctl failure triage, GHCR fix, or rollout verification?"
user-invocable: true
---

# Swarmctl Production Deployment Workflow

Use this skill when you need to deploy this monorepo to production, harden the deploy pipeline, debug `swarmctl` failures, or verify that `master` pushes trigger a safe production rollout.

This skill is optimized for the deployment path used in this repository:

- `docker-publish.yml`
- `swarmctl-auto-deploy.yml`
- `swarmctl-deploy.yml`
- `scripts/bootstrap_production_prereqs.sh`
- `scripts/deploy_production_swarmctl.sh`
- `swarm/stack-postgres-ha.yml`
- `swarm/stack-redis-ha.yml`

## Outcome

Produce a production-ready deployment result with:

1. Correct image tag selection (prefer immutable `sha-<short>` tags)
2. Working swarmctl workflow resolution and environment setup
3. Verified GHCR pullability for app images
4. Verified HA infra prerequisites (networks, secrets, valid infra images)
5. Clear rollout evidence for API, backend, worker, and frontend
6. A short summary of what was deployed, what was verified, and what remains risky

## When to Use

Use this skill for any of these situations:

- Deploy the app to production with `swarmctl`
- Make push/merge to `master` auto-deploy production
- Debug `swarmctl` workflow failures in GitHub Actions
- Fix `invalid refspec`, `denied`, missing secret, or `No such image` errors
- Validate Docker Swarm manager connectivity and rollout health
- Provision or audit GHCR access, swarm secrets, and HA infra readiness
- Decide between `latest`, pinned release, and `sha-<short>` image strategies

## Decision Logic

1. **Is the task about manual local deployment or GitHub Actions automation?**
   - Local/manual -> prefer `scripts/deploy_production_swarmctl.sh`
   - GitHub automation -> inspect `docker-publish.yml`, `swarmctl-auto-deploy.yml`, and `swarmctl-deploy.yml`

2. **Is the failure before deploy, during preflight, or during runtime/rollout?**
   - Before deploy -> check workflow syntax, `SWARMCTL_REPO_REF`, dispatch conditions, and image tag selection
   - Preflight -> check GHCR pullability, manager connectivity, required networks, and required secrets
   - Runtime/rollout -> inspect `docker service ps`, exit codes, and health endpoints

3. **Are you deploying app services, HA infra, or both?**
   - App only -> validate app manifests and image pullability first
   - Infra only -> verify external swarm secrets and image validity for HA stack files first
   - Both -> bootstrap infra prerequisites before app deploy

4. **What image strategy should be used?**
   - Production app deploy -> prefer immutable `sha-<short>` tags
   - Emergency/manual override -> allow `latest` only when explicitly intended and supported by `swarmctl`
   - Infra images -> pin or validate working upstream tags before deploy

5. **Is the error registry-related?**
   - `denied` / manifest access failure -> inspect GHCR token/package permissions and local/manager auth
   - `No such image` -> verify image tag exists upstream; do not assume Swarm auth is the issue

## Standard Procedure

### Phase 1: Identify the deployment path

Determine which path is in use:

- Local deploy script
- Manual GitHub `workflow_dispatch`
- Auto-deploy after push/merge to `master`

Record:

- target environment
- target image tag
- whether `deploy_infra` is true
- whether `deploy_apps` is true
- whether the deployment should be dry-run or real apply

### Phase 2: Validate control-plane prerequisites

Check:

- `SWARMCTL_REPO_REF` or latest-release behavior
- `SWARMCTL_CONFIG_BASE64`
- `SWARM_SSH_PRIVATE_KEY`
- `ORCHESTRATOR_WORKFLOW_TOKEN`
- optional `GHCR_TOKEN`
- repo variables for auto-deploy defaults

For auto-deploy on `master`, confirm:

- `docker-publish.yml` runs on push to `master`/`main`
- `swarmctl-auto-deploy.yml` is triggered by successful image publishing
- `swarmctl-deploy.yml` receives the computed immutable SHA tag

### Phase 3: Validate production cluster prerequisites

Inspect:

- `swarmctl infra ips --env production`
- `swarmctl infra topology --env production`
- manager reachability
- overlay networks `internal` and `public`
- required swarm secrets for app services
- required swarm secrets for HA stacks

Required HA stack secrets include:

- `pg_su_password`
- `pg_app_password`
- `pg_repmgr_password`
- `pgpool_admin_password`
- `redis_password`

### Phase 4: Validate image pullability

For app services:

- verify `ghcr.io/cploutarchou/dydx-trading-bot/<service>:sha-<short>` exists
- verify manager-side pullability or manifest access
- prefer immutable SHA tags over `latest`

For HA infra images:

- verify stack image tags exist upstream before deploy
- if upstream tags drift, patch stack files to known-good image names/tags

### Phase 5: Render and validate manifests

For app manifests:

- render the selected `image_tag`
- validate with `swarmctl validate`
- plan with `swarmctl plan`

For infra stacks:

- validate with `docker compose config`
- verify required external secrets exist before `stack deploy`

### Phase 6: Deploy incrementally

Suggested order:

1. bootstrap prerequisites
2. deploy HA infra stacks
3. wait for infra tasks to schedule and become healthy
4. deploy app manifests
5. verify rollout status and health endpoints

### Phase 7: Triage failures by class

#### Class A: GitHub workflow control failure

Examples:

- invalid refspec
- missing secret/variable
- workflow skipped unexpectedly
- malformed YAML step

Actions:

- inspect workflow conditions
- inspect current repo variables
- ensure committed workflow version contains the latest fix
- avoid relying on local-only workflow edits

#### Class B: Registry/image failure

Examples:

- `denied`
- `manifest unknown`
- `No such image`

Actions:

- distinguish app GHCR images from third-party infra images
- validate token/package access for GHCR
- validate exact image tag existence
- replace broken third-party tags with real pullable tags

#### Class C: Swarm secret/network failure

Examples:

- secret not found
- missing external network

Actions:

- use `scripts/bootstrap_production_prereqs.sh`
- verify manager secret names exactly match stack/app manifest expectations
- fail before deploy if required secrets are absent

#### Class D: Runtime container failure

Examples:

- task exits non-zero
- service stuck at `0/N`
- health endpoint down after rollout

Actions:

- inspect `docker service ps --no-trunc`
- identify node placement and exit codes
- separate scheduling, image pull, and app runtime errors
- verify dependent infra is healthy before app rollout

## Production Quality Gates

- [ ] GitHub workflow path is correct for the intended deployment mode
- [ ] `SWARMCTL_REPO_REF` is pinned or intentionally auto-resolved
- [ ] App deployment uses immutable SHA tags unless there is an explicit exception
- [ ] GHCR pullability is verified for deployed app images
- [ ] HA stack image references are verified and pullable
- [ ] Required app and HA secrets exist on the manager
- [ ] Required overlay networks exist
- [ ] `swarmctl validate` and `swarmctl plan` pass before apply
- [ ] Infra rollout is healthy enough for app startup dependency expectations
- [ ] App rollout status and health endpoints are checked after apply
- [ ] Remaining risks and rollback path are documented

## Repository-Specific References

- Deployment bootstrap: `./scripts/bootstrap_production_prereqs.sh`
- Manual app deploy: `./scripts/deploy_production_swarmctl.sh`
- Auto deploy workflow: `./../workflows/swarmctl-auto-deploy.yml`
- Deploy workflow: `./../workflows/swarmctl-deploy.yml`
- Image publish workflow: `./../workflows/docker-publish.yml`
- HA Postgres stack: `../../swarm/stack-postgres-ha.yml`
- HA Redis stack: `../../swarm/stack-redis-ha.yml`

## Completion Checklist

A deployment task is complete only when:

- the intended trigger path is verified
- required secrets and networks are present
- image pullability is confirmed for the chosen tag(s)
- the deployment finished or failed with a precise classified cause
- rollout evidence is captured for the affected services
- any remaining operational action items are explicit

## Suggested Invocation Prompts

- `/swarmctl-production-deployment Deploy the latest production-ready SHA image to production and verify rollout.`
- `/swarmctl-production-deployment Make push to master auto-deploy production safely with swarmctl.`
- `/swarmctl-production-deployment Debug why the swarmctl deploy workflow is failing in GitHub Actions.`
- `/swarmctl-production-deployment Bootstrap all required production secrets and HA infra prerequisites.`
- `/swarmctl-production-deployment Audit GHCR pullability, swarm secrets, and swarmctl settings before production deploy.`
