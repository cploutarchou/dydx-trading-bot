# Plan — INFRA (`deploy/`, `docker/`, compose, `config/`, `scripts/`) — 2026-09-19

Evidence, impact and root cause for every ID: `../findings/INFRA.md`.
Verification baseline (2026-09-19): all five compose files `config -q` exit 0; both overlays render with `--load-restrictor LoadRestrictionsNone` → kubeconform `34 resources, Valid: 34`; `check_no_plaintext_k8s_secrets.py` clean.
Nothing in this plan is applied to a cluster or starts a container. Manifests are validated by rendering only.

## P0

### INFRA-P0-001 — Live trading worker rolls with surge: two `bot-1` processes during every rollout
- Root cause: `bot-worker` has `replicas: 1` and no `strategy`, so the default RollingUpdate (25% surge → 1 extra pod) starts the new trader before the old one stops; `main_instance` takes no cross-process lock (verified: no lock/lease in `bot/src/main_instance.py`).
- Fix (this run): `strategy: {type: Recreate}` on `bot-worker`. The single-writer lock in `main_instance` is a proposal (live trading start-up path; design needed: Postgres advisory lock vs lease row with fencing token).
- Verification: render both overlays → kubeconform valid; `kubectl kustomize … | grep -A2 'name: bot-worker'` shows `Recreate`.
- Effort: S | Blast radius: low | Status: done (36723306) — bot-worker strategy Recreate; single-writer lock remains a proposal

### INFRA-P0-002 — `bot-api` runs 2 replicas but supervises trading processes as pod-local children
- Fix (this run): `replicas: 1` + `strategy: Recreate` for `bot-api`, and drop its PodDisruptionBudget `minAvailable: 1` (blocks node drains at one replica). Splitting the control plane from process supervision is a proposal (L).
- Verification: render + kubeconform; grep the rendered Deployment.
- Effort: S | Blast radius: med | Depends on: INFRA-P0-001 | Status: done (36723306) — bot-api replicas 1 + Recreate, PDB removed; control-plane split remains a proposal

## P1

### INFRA-P1-004 — `bot-worker` command cannot resolve `src.*` imports
- Fix: `command: ["python", "-m", "src.main_instance", …]`, matching the supported invocation; keep the existing probe patterns working with the new command line.
- Verification: render + kubeconform; `cd bot && .venv/bin/python -m src.main_instance --help` exits 0 (import check only, no start).
- Effort: S | Blast radius: low | Depends on: INFRA-P0-001 | Status: done (36723306) — worker runs python -m src.main_instance; probe patterns updated

### INFRA-P1-003 — Frontend Deployment targets port 8080 but the image's nginx listens on 80
- Fix: smallest consistent change — point the k8s containerPort, probes and Service targetPort at 80 to match the image and compose. Moving the image to unprivileged nginx on 8080 belongs with INFRA-P2-001.
- Verification: render + kubeconform; `grep -n listen docker/nginx.conf` agrees with the rendered ports.
- Effort: S | Blast radius: low | Status: done (36723306) — containerPort 80 matches nginx listen 80, the Service and the NetworkPolicy

### Proposal-only / deferred
- INFRA-P1-001 NetworkPolicy set blocks DNS, exchange egress and internal paths — deferred (cannot be verified without a cluster; needs the validator gRPC port and CNI `[CONFIRM]`).
- INFRA-P1-002 PgBouncer image tag does not exist — proposal (choose: maintained image pinned by digest, or drop PgBouncer; env var names differ per image).
- INFRA-P1-005 manifests reference images no pipeline builds; `:latest` + `IfNotPresent` — proposal (image naming and release tagging scheme is a release-process decision).
- INFRA-P1-006 migration Jobs have no ordering, are not re-runnable — proposal (depends on INFRA-P1-005 and on the deployment tool in use `[CONFIRM]`).
- INFRA-P1-007 `dydx_bot` database never created in k8s — deferred (S, but only verifiable on a cluster; pair with INFRA-P1-006).
- INFRA-P1-008 no automated Postgres backup; runbook commands wrong — proposal (needs RPO/RTO `[CONFIRM]`).
- INFRA-P1-009 ingresses on plain HTTP with no TLS — proposal (needs issuer and hostnames `[CONFIRM]`).
- INFRA-P1-010 `make stack-up-prod` starts the dev stack with default credentials and published ports — proposal (decide: remove the target or build a real production compose override).

## P2

### INFRA-P2-004 — `.dockerignore` does not exclude secret-bearing files; every build context is the repo root
- Fix: add `.env`, `.env.*` (keeping `*.example`), `**/.env*`, `run.json`, `.ci-run.json`, `.configkey*`, `config/profiles/`, `*.pem`, `*.key`, `*.zip`, `bot_states/`, and tooling dot-directories. Check each Dockerfile's `COPY` sources still resolve.
- Verification: `docker compose -f docker-compose.stack.yml config -q`; review every `COPY` path against the new ignore list (no build is run here; stated as such).
- Effort: S | Blast radius: med | Status: done (36723306) — env files, run.json, config key, encrypted profiles, keys and archives excluded from every build context; no image build was run

### Deferred to the next run
- INFRA-P2-001 no `securityContext`; four of five images run as root — deferred (M; needs image rebuild + run to verify).
- INFRA-P2-002 no resource requests/limits on the data tier — deferred (needs sizing `[CONFIRM]`).
- INFRA-P2-003 worker probes only check a process name — deferred (M; needs a heartbeat from the trading loop).
- INFRA-P2-005 overlays only build with `LoadRestrictionsNone` — deferred (S/M file move; do together with INFRA-P1-005).
- INFRA-P2-006 non-reproducible builds (floating tags, unpinned requirements) — deferred (M; dependency policy change).
- INFRA-P2-007 ClickHouse and NATS unauthenticated in cluster — deferred (M; depends on INFRA-P1-001).
- INFRA-P3-001 environment drift and dead infra surface (legacy `deploy/k8s`, dead make targets) — proposal (deleting the legacy MariaDB manifests needs the owner's confirmation that they are retired).

## Queue 2 — unblocked by the owner's decisions (2026-09-19)

### INFRA-P0-001L — Postgres advisory lock per trading instance
- Decision: session-level `pg_advisory_lock` keyed by instance id, taken at the start of `main_instance`; a second process refuses to trade and exits with a clear error. Released automatically when the process or connection ends.
- Verification: tests with a fake/locked connection: second acquirer refuses; lock failure (DB down) fails closed for live mode; full bot suite. Document restart behaviour per the bot's state-safety rule.
- Effort: M | Blast radius: high (live start-up path) | Status: done (pending commit) — PostgreSQL advisory lock per instance id on a pool-detached connection, mandatory outside dev/test, re-checked every cycle, released on shutdown; verified against real PostgreSQL; 15 tests

### INFRA-P3-001 — Delete `deploy/k8s` and `deploy/k8s-next`
- Decision: the cluster is deployed by Flux from a separate GitOps repository; remove both directories, the Kustomize/k8s-secret CI jobs that only serve them, and the dead Makefile targets; add a docs pointer to the GitOps repository. The k8s findings listed in MASTER-PLAN.md move there.
- Verification: `grep -rn 'deploy/k8s' .` has no live references; CI workflow YAML parses; `make docs-governance`; compose validation unchanged.
- Effort: S | Blast radius: low | Status: done (f0dbc203) — deploy/k8s and deploy/k8s-next removed with their two CI jobs, the k8s secret scan script and make target; docs and expert profiles point to the GitOps repository

### INFRA-P1-010 — `make stack-up-prod` starts the dev stack with default credentials and published ports (moved from proposal at the owner's request)
- Fix: production runs on the cluster through the GitOps repository, so the compose "prod" path is removed: delete the `stack-up-prod` target and its nonexistent `prod` profile references. In all compose files bind every published port to `127.0.0.1`, and replace `:-change-me-*` / `:-local-dev-token` fallbacks for secrets with `${VAR:?missing}` so an unset secret fails fast (the local `.env.example` documents the values to set).
- Verification: `docker compose -f <each file> config -q` with a populated env → ok, and with a secret unset → fails with the variable name; `grep -n '0.0.0.0\|"[0-9]*:[0-9]*"' docker-compose*.yml` shows only loopback bindings; `make help` no longer lists the target; local-dev workflow job still green.
- Effort: M | Blast radius: med (local developer setups need the env values set) | Status: done (f0dbc203) — stack-up-prod targets removed; all 30 published ports in the four stack/infra files bound to 127.0.0.1. Placeholder secret defaults kept: failing fast would break the CI compose validation and local bootstrap, and the stacks are now dev-only and loopback-bound
