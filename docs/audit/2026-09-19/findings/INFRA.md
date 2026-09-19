# Findings — INFRA (deploy/, docker/, compose, config/, scripts/, .devcontainer/, .dockerignore)

Audit date: 2026-09-19. Read-only investigation. Provisional IDs. No container was started, stopped, pulled or built; nothing was applied to any cluster; no secret file contents were read or printed (example/secret files were inspected with values redacted or reduced to a placeholder/non-placeholder classification).

Scope note: `deploy/k8s-next/README.md:20` calls the manifests "a skeleton". They are nevertheless what CI validates as `overlays/production`, and what the runbook tells operators to deploy, so they are audited as the production path.

---

## P0

### INFRA-P0-001 — Live trading worker rolls with surge: two `bot-1` processes trade the same account during every rollout
- Priority: P0 | Type: reliability | Area: deploy/k8s-next/applications
- Evidence: deploy/k8s-next/applications.yaml:285-309 (no `strategy:` anywhere in deploy/k8s-next — `grep -rn "strategy:" deploy/k8s-next` returns nothing)
  ```yaml
  kind: Deployment
  metadata:
    name: bot-worker
  spec:
    replicas: 1
  ...
            - src/main_instance.py
            - --instance-id
            - bot-1
  ```
  bot/src/main_instance.py has no cross-process guard: `grep -n -i "lock\|lease\|advisory" bot/src/main_instance.py` returns nothing; the only instance locks are in-process `asyncio.Lock` objects (bot/src/bot_instance_manager.py:232-237).
- Impact: a Deployment without `strategy` defaults to RollingUpdate (maxSurge 25% -> 1 pod, maxUnavailable -> 0). On every image/config change the new `bot-1` pod is started and must pass readiness (>= 20 s) before the old one receives SIGTERM, and the old one then has up to 30 s grace. For that whole window two processes evaluate the same signals and place orders on the same dYdX subaccount: duplicate entries, doubled position size, conflicting exits. Same effect on node drain/eviction races.
- Root cause: a singleton stateful trader is modelled as a stateless Deployment; no fencing (DB advisory lock / lease) in the process either.
- Fix: set `strategy: {type: Recreate}` on `bot-worker` (or convert to a 1-replica StatefulSet, which gives at-most-one semantics per ordinal); add an explicit `terminationGracePeriodSeconds` sized to the shutdown path; add a Postgres advisory lock (or lease row with fencing token) keyed by instance id taken at start of `main_instance` so a second process refuses to trade. The manifest fix is S; the lock belongs to the BOT plan.
- Verification: `kubectl kustomize --load-restrictor LoadRestrictionsNone deploy/k8s-next/overlays/production | grep -A3 "name: bot-worker" | grep -A2 strategy` shows `Recreate`; new bot test starting two `main_instance` processes with the same id asserts the second exits non-zero.
- Effort: S (manifest) + M (lock) | Blast radius: med | Depends on: —

### INFRA-P0-002 — `bot-api` runs 2 replicas but supervises trading processes as pod-local subprocesses tracked by PID
- Priority: P0 | Type: reliability | Area: deploy/k8s-next/applications + bot runtime supervisor
- Evidence: deploy/k8s-next/applications.yaml:188-193
  ```yaml
  kind: Deployment
  metadata:
    name: bot-api
  spec:
    replicas: 2
  ```
  bot/src/bot_instance_manager.py:1276-1285 (`cmd = [bot_python, "-m", "src.main_instance", "--instance-id", instance_id]` ... `subprocess.Popen(`) and :1012-1018
  ```python
            process = psutil.Process(normalized_pid)
        except (TypeError, ValueError):
            return None, f"Stored runtime PID for {instance_id} is invalid"
        except psutil.NoSuchProcess:
            return None, f"Runtime process for {instance_id} is no longer running"
  ```
- Impact: the trading process lives inside whichever bot-api pod handled "start". The other replica shares the persisted state but not the PID namespace: its PID probe reports "no longer running", the instance is marked ERROR (bot_instance_manager.py:1112-1120 pops the pid), and a subsequent start request load-balanced to that replica launches a second live trader for the same instance. In addition, every bot-api rollout kills the child trading processes with the pod, and the separate `bot-worker` Deployment hard-codes `--instance-id bot-1`, so the same id can be started by two different supervisors. What is proven here: replicas=2, Popen-based supervision, pod-local PID probe. The exact reconcile path that flips the state on the second replica should be confirmed in the BOT audit.
- Root cause: a single-host process supervisor deployed as a horizontally scaled, load-balanced service.
- Fix: run `bot-api` with `replicas: 1` + `strategy: Recreate` and remove its PDB `minAvailable: 1` (which blocks drains at 1 replica) until the supervisor is replaced; decide on one owner for live instances (either bot-api-spawned or the `bot-worker` Deployment, not both); longer term make bot-api a pure control plane that writes desired state and let one worker per instance (StatefulSet) reconcile it under the P0-001 lock.
- Verification: rendered manifest shows `replicas: 1`/`Recreate` for bot-api; integration test: two manager objects sharing one DB, start on A, status/start on B must not spawn.
- Effort: S (manifest) / L (control-plane split) | Blast radius: high | Depends on: INFRA-P0-001

---

## P1

### INFRA-P1-001 — NetworkPolicy set blocks DNS, exchange egress, bot-api ingress, pgbouncer->postgres and the migration Jobs; namespace selector is wrong in both overlays
- Priority: P1 | Type: bug | Area: deploy/k8s-next/networkpolicies
- Evidence: deploy/k8s-next/networkpolicies.yaml:6-9 and :26-39
  ```yaml
    podSelector: {}
    policyTypes:
      - Ingress
      - Egress
  ```
  ```yaml
          - namespaceSelector:
              matchLabels:
                kubernetes.io/metadata.name: dydx-next
  ...
          - protocol: TCP
            port: 80
  ```
  Rendered production overlay still contains `kubernetes.io/metadata.name: dydx-next` (line 1251 of the render) while every resource is in `namespace: dydx-next-production`.
- Impact (each item read directly from the file): (1) default-deny egress with no rule for UDP/TCP 53 -> no pod can resolve `pgbouncer`, `valkey`, `nats`; (2) the only egress rule (`allow-app-to-data`, :41-88) targets in-namespace data pods, so `bot-worker` cannot reach the dYdX indexer/validator and cannot trade, and `backend` cannot call `bot-api:8889`; (3) `allow-app-ingress` selects components `ui` and `api` only — `bot-api` is `component: runtime` (applications.yaml:201) so nothing may connect to it; (4) the selector names namespace `dydx-next`, which matches neither overlay namespace; (5) the frontend pod port is 8080 in the manifest but the policy allows 80 (NetworkPolicy ports are pod ports); (6) `pgbouncer` (`database-proxy`) has no egress rule to `postgresql`; (7) migration Job pods carry no `component` label (migrations.yaml:8-10) so they get deny-all and cannot reach the database. On an enforcing CNI the stack cannot start; the predictable operator reaction is deleting the policies wholesale, leaving the data tier open.
- Root cause: policies were written without being exercised on an enforcing cluster; namespace hard-coded in base.
- Fix: add a DNS egress policy (kube-system/kube-dns, UDP+TCP 53) for all pods; add explicit egress for `bot-worker`/`bot-api` to 0.0.0.0/0:443 (+ the validator gRPC port) excluding RFC1918; allow `api -> runtime:8889`; allow `database-proxy -> postgresql:5432`; label migration Jobs `component: migration` and allow them to 5432/6432; replace the hard-coded namespace selector with `podSelector: {}` (same namespace) plus the ingress-controller namespace; align the frontend port (see INFRA-P1-003).
- Verification: apply the staging overlay to a throwaway k3s/kind cluster with an enforcing CNI and run `kubectl -n dydx-next-staging exec deploy/backend -- nslookup pgbouncer` and `wget -qO- http://bot-api:8889/health`; both must succeed, and `wget` from an unlabelled debug pod to `postgresql:5432` must time out.
- Effort: M | Blast radius: med | Depends on: —

### INFRA-P1-002 — PgBouncer image tag does not exist on the registry; every app DB connection goes through it
- Priority: P1 | Type: reliability | Area: deploy/k8s-next/pgbouncer
- Evidence: deploy/k8s-next/pgbouncer.yaml:30
  ```yaml
          image: bitnami/pgbouncer:1.24.0
  ```
  Real output of `docker manifest inspect bitnami/pgbouncer:1.24.0` (registry query only, nothing pulled): `no such manifest: docker.io/bitnami/pgbouncer:1.24.0`. platform-config.yaml:14, :17, :43 point `DB_HOST`, `BOT_DB_HOST`, `TASK_DB_HOST` at `pgbouncer`.
- Impact: a fresh node cannot pull the image -> pgbouncer stays in ImagePullBackOff -> backend, bot-api, workers and both migration Jobs have no database. Nodes with a cached copy hide the problem until they are replaced.
- Root cause: dependency on a third-party image catalogue whose versioned tags were withdrawn; no digest pin, no mirror.
- Fix: switch to a maintained PgBouncer image pinned by digest and mirrored into the project registry (ghcr), or drop PgBouncer until connection counts justify it (apps -> `postgresql:5432` directly). Re-check env var names when changing image.
- Verification: `docker manifest inspect <new-image>@sha256:...` returns a manifest; staging rollout shows `kubectl get pods -l app.kubernetes.io/name=pgbouncer` Running/Ready.
- Effort: S | Blast radius: med | Depends on: —

### INFRA-P1-003 — Frontend Deployment targets port 8080 but the image's nginx listens on 80
- Priority: P1 | Type: bug | Area: deploy/k8s-next/applications, docker/nginx.conf
- Evidence: deploy/k8s-next/applications.yaml:20-29
  ```yaml
            ports:
              - name: http
                containerPort: 8080
  ...
              httpGet:
                path: /
                port: http
  ```
  docker/nginx.conf:12-13 `server {` / `listen 80;` and docker/Dockerfile.frontend:49 `EXPOSE 80`.
- Impact: readiness and liveness probes hit 8080 where nothing listens: pods never become Ready, are restarted in a loop, and the Service (`targetPort: http`) has no endpoints. The UI is down in k8s.
- Root cause: manifest anticipates an unprivileged nginx on 8080; the Dockerfile still ships root nginx on 80.
- Fix: move the image to the unprivileged model (nginx unprivileged base or `listen 8080;` + non-root user, `EXPOSE 8080`) and update the compose mapping to `5173:8080`. This also resolves the frontend part of INFRA-P2-001.
- Verification: `docker build -f docker/Dockerfile.frontend .` then `docker run --rm -p 18080:8080 <img>` + `curl -fsS localhost:18080/`; staging pods Ready.
- Effort: S | Blast radius: low | Depends on: —

### INFRA-P1-004 — `bot-worker` command runs `python src/main_instance.py`; the module's absolute `src.*` imports cannot resolve that way
- Priority: P1 | Type: bug | Area: deploy/k8s-next/applications
- Evidence: deploy/k8s-next/applications.yaml:304-309
  ```yaml
            command:
              - python
            args:
              - src/main_instance.py
              - --instance-id
              - bot-1
  ```
  bot/src/main_instance.py:4 `from src.shared.env_loader import load_repo_env`; the supported launch form is `-m src.main_instance` (bot/src/bot_instance_manager.py:1276-1281). docker/Dockerfile.worker sets no `PYTHONPATH`, and platform-config.yaml does not either.
- Impact: when a file path is executed, Python puts the script's directory (`/app/src`) on `sys.path`, not `/app`; `import src...` raises ModuleNotFoundError and the pod crash-loops. The production trading worker as declared cannot start. (It currently masks INFRA-P0-001.)
- Root cause: manifest written against a different invocation than the one the code supports.
- Fix: `command: ["python", "-m", "src.main_instance", "--instance-id", "$(BOT_INSTANCE_ID)"]` with the id from an env var rather than a literal; update the pgrep patterns or, better, replace them (INFRA-P2-003).
- Verification: `cd bot && python -m src.main_instance --help` exits 0, whereas `python src/main_instance.py --help` fails at import (run in a disposable venv/container, not in the tracked tree).
- Effort: S | Blast radius: low | Depends on: INFRA-P0-001 (fix the rollout strategy in the same change, since this fix makes the worker actually run)

### INFRA-P1-005 — Manifests reference images that no pipeline builds, under names the pipeline does not publish, all on `:latest` with `IfNotPresent`
- Priority: P1 | Type: reliability | Area: deploy/k8s-next, scripts/build_all_service_images.sh, container-images workflow
- Evidence: deploy/k8s-next/applications.yaml:205-206, :302, :378; migrations.yaml:15, :47
  ```yaml
            image: ghcr.io/cploutarchou/dydx-trading-bot/bot-api:latest
            imagePullPolicy: IfNotPresent
  ```
  ```yaml
            image: ghcr.io/cploutarchou/dydx-trading-bot/bot-migrator:latest
  ```
  scripts/build_all_service_images.sh:17 `SERVICES=(api worker backend frontend)`; .github/workflows/container-images.yml:66-73 builds the same four. Nothing builds `docker/Dockerfile.backend-migrator`; there is no Dockerfile for `bot-migrator` or `backtest-worker`. The rendered production overlay contains 8 `:latest` image references (`grep -c "image: .*:latest"` -> `8`); neither overlay has an `images:` transformer.
- Impact: `bot-api`, `bot-worker`, `backtest-worker`, `backend-migrator`, `bot-migrator` do not exist in the registry -> ImagePullBackOff. For the two that do exist, `:latest` + `IfNotPresent` means nodes run whatever they cached: a rollout may silently not update, replicas on different nodes can run different code, and rollback to a known build is impossible. For a system placing orders, "which code is running" must be answerable.
- Root cause: image naming diverged between the build tooling and the manifests; release tagging was never wired into kustomize.
- Fix: one naming scheme (rename matrix entries to `bot-api`/`bot-worker`, add `backend-migrator` and a `bot-migrator` target — the worker image with an alembic entrypoint is enough; `backtest-worker` can reuse the `bot-worker` image); add `images:` blocks in both overlays pinned to the short-SHA tag (ideally digest) and have the release step run `kustomize edit set image`; add a CI check that fails on `:latest` in rendered overlays.
- Verification: `kubectl kustomize --load-restrictor LoadRestrictionsNone deploy/k8s-next/overlays/production | grep -c ":latest"` -> `0`; `docker manifest inspect` succeeds for every rendered image.
- Effort: M | Blast radius: med | Depends on: —

### INFRA-P1-006 — Migration Jobs are plain resources in the same kustomization as the apps: no ordering, not re-runnable, never cleaned up
- Priority: P1 | Type: migration | Area: deploy/k8s-next/migrations
- Evidence: deploy/k8s-next/kustomization.yaml:17-18 (`- applications.yaml` / `- migrations.yaml`) and migrations.yaml:1-6, :20-22
  ```yaml
  kind: Job
  metadata:
    name: backend-postgres-migrate
  spec:
    backoffLimit: 1
  ...
                echo "Run backend PostgreSQL migrations explicitly before rolling out app workloads."
  ```
- Impact: `apply -k` creates Deployments and Jobs simultaneously, so new application code starts against the old schema (the echo states the intent but nothing enforces it; the runbook has no migration step at all). A Job's pod template is immutable: the second release with a new image tag fails with "field is immutable", and with an unchanged `:latest` tag the apply is a no-op and the migration silently does not run. No `ttlSecondsAfterFinished`, no resources, no `activeDeadlineSeconds`. `backoffLimit: 1` retries a half-applied migration once with no human in the loop.
- Root cause: Jobs treated as declarative steady-state resources.
- Fix: take the Jobs out of the base bundle into `deploy/k8s-next/jobs/` applied as an explicit, gated release step (`kubectl create -f` with `generateName`, then `kubectl wait --for=condition=complete`), or use the GitOps tool's pre-sync/dependsOn mechanism; set `ttlSecondsAfterFinished`, `activeDeadlineSeconds`, `backoffLimit: 0`; document expand -> deploy -> contract in the runbook. Optionally add an init container on backend/bot-api that blocks until `migrate version` matches the expected version.
- Verification: staging dry run: release N+1 with a schema change shows Job Complete before the Deployment's new ReplicaSet is created; re-running the release step twice creates two distinct Jobs without an immutability error.
- Effort: M | Blast radius: med | Depends on: INFRA-P1-005

### INFRA-P1-007 — The bot database `dydx_bot` is never created in Kubernetes
- Priority: P1 | Type: bug | Area: deploy/k8s-next/postgresql, platform-config
- Evidence: deploy/k8s-next/postgresql.yaml:38-42 and platform-config.yaml:22-23
  ```yaml
              - name: POSTGRES_DB
                valueFrom:
                  configMapKeyRef:
                    name: platform-config
                    key: DATABASE_NAME
  ```
  ```yaml
    DATABASE_NAME: dydx_platform
    BOT_DATABASE_NAME: dydx_bot
  ```
  The compose stacks have a dedicated `postgresql-bot-db-init` service (docker-compose.stack.yml:43-57); `grep -rn -i "createdb\|CREATE DATABASE" deploy/k8s-next/*.yaml` returns nothing.
- Impact: the postgres entrypoint creates only `dydx_platform`. `bot-postgres-migrate` (`alembic upgrade head`) and every bot workload fail with "database dydx_bot does not exist" on a fresh environment; the manual workaround is undocumented, which invites running the bot against the platform database.
- Root cause: compose bootstrap step not ported to k8s.
- Fix: mount an init script ConfigMap at `/docker-entrypoint-initdb.d/` creating `dydx_bot` (first boot) plus an idempotent bootstrap Job equivalent to the compose init service for existing volumes; give the bot its own role with rights on `dydx_bot` only instead of sharing the superuser.
- Verification: fresh staging namespace: `kubectl exec postgresql-0 -- psql -U "$POSTGRES_USER" -d postgres -tAc "select datname from pg_database"` lists both databases; bot migrate Job completes.
- Effort: S | Blast radius: low | Depends on: —

### INFRA-P1-008 — No automated PostgreSQL backup; the runbook's backup/rollback commands cannot work as written
- Priority: P1 | Type: data | Area: deploy/k8s-next (postgresql.yaml, DEPLOYMENT_RUNBOOK.md)
- Evidence: `grep -rn "CronJob" deploy/k8s-next` returns nothing; postgresql.yaml:20 `replicas: 1` on a single RWO PVC. DEPLOYMENT_RUNBOOK.md:152, :164, :168
  ```
     - Or apply down migrations: `kubectl exec <backend-pod> -- alembic downgrade -1`
  kubectl exec postgresql-0 -- pg_dump -U postgres dydx_platform > dydx_platform_$(date +%Y%m%d_%H%M%S).sql
  kubectl exec pgbouncer-xxxx -- pg_dump -h postgresql -U postgres dydx_platform > backup.sql
  ```
- Impact: orders, fills, positions, audit and encrypted runtime configs live on one volume with no scheduled dump, no WAL archiving, no off-cluster copy and no restore drill. PVC loss or a bad migration is unrecoverable. The documented commands assume a `postgres` role (the superuser is whatever `postgres-credentials/username` holds, so `postgres` normally does not exist), run `alembic` inside the Go backend image (docker/Dockerfile.backend ships only `./server`), and run `pg_dump` inside the PgBouncer image. The restore section drops the production database as step one with no verification of the dump.
- Root cause: backup treated as documentation rather than a deployed, tested component.
- Fix: CronJob running `pg_dump -Fc` for both databases to the existing MinIO (separate bucket, versioning/retention, credentials from a Secret) plus an off-cluster copy; or move to an operator with WAL archiving/PITR if RPO < 24 h is required `[CONFIRM RPO/RTO]`. Rewrite the runbook with real role/image names, restore-into-scratch-database-first, and a quarterly restore test. Take a backup as a mandatory pre-step of the migration release step (INFRA-P1-006).
- Verification: `kubectl create job --from=cronjob/postgres-backup manual-1`; object appears in the bucket; `pg_restore --list` succeeds; restore into a scratch DB and compare row counts on orders/fills tables.
- Effort: M | Blast radius: low | Depends on: —

### INFRA-P1-009 — Ingresses expose the API and UI on the plain-HTTP entrypoint with no TLS section
- Priority: P1 | Type: security | Area: deploy/k8s-next/applications, overlays
- Evidence: deploy/k8s-next/applications.yaml:161-167 (same at :63-68)
  ```yaml
    annotations:
      traefik.ingress.kubernetes.io/router.entrypoints: web,websecure
  spec:
    ingressClassName: traefik
    rules:
      - host: api.example.com
  ```
  `grep -rn "tls:" deploy/k8s-next` returns nothing, including both overlay ingress patches.
- Impact: the backend API (login, JWTs, bot control) is routed on port 80 in clear text, and on 443 with the controller's default self-signed certificate. Credentials and session tokens for a system that controls live trading are interceptable; `FRONTEND_PUBLIC_ORIGIN: https://...` in the ConfigMap implies TLS that the manifests do not provide.
- Root cause: TLS left to be added later; `web` entrypoint included for convenience.
- Fix: `entrypoints: websecure` only; add `spec.tls` with a cert-manager `Certificate`/issuer annotation per overlay; add an HTTP->HTTPS redirect middleware; set HSTS at the edge.
- Verification: rendered overlay has `tls:` on both Ingresses; `curl -sI http://<host>/` returns 301/308 to https; `curl -sI https://<host>/health` presents a valid chain.
- Effort: S | Blast radius: low | Depends on: —

### INFRA-P1-010 — `make stack-up-prod` validates the production profile, then starts the dev stack with default credentials and wide-open ports
- Priority: P1 | Type: security | Area: docker-compose.stack*.yml, Makefile
- Evidence: Makefile:742-744
  ```make
  		python3 scripts/validate_stack_env.py --environment production --strict-prod; \
  		APP_CONFIG_ENV=production docker compose -f $(STACK_COMPOSE_FILE) --profile prod up -d --remove-orphans; \
  		echo "[OK] Prod-like stack started (proxy:8080, api internal, frontend internal)"; \
  ```
  docker-compose.stack.yml:97-99, :119-121, :144-146, :222, :226-228, :327-328
  ```yaml
      ports:
        - "4222:4222"
        - "8222:8222"
  ...
        BOT_API_TOKEN: ${BOT_API_TOKEN:-local-dev-token}
  ```
- Impact: the compose file has no `profiles:` and no proxy service (`grep -n "profiles:\|proxy" docker-compose.stack.yml` -> nothing), so "prod" is the dev stack: `APP_CONFIG_ENV: development` and `DB_AUTO_MIGRATE: "true"` are literals; nothing exports the validated profile into compose interpolation, so `change-me-db-password`, `change-me-clickhouse`, `change-me-minio-*` and `local-dev-token` are what actually run. Postgres and Valkey are bound to 127.0.0.1, but NATS 4222/8222 (no auth), ClickHouse 8123/9000, MinIO 9010/9011, backend 8888 and bot-api 8889 are published on 0.0.0.0. On a self-hosted box with a public interface, anyone can call the bot control API with a token that is in the repository, publish to the command bus, and read object storage with the default root key. The success message describes a topology that does not exist. Same in the arm64 file and in docker-compose.infra*.yml (:93-95, :115-117, :140-142).
- Root cause: prod profile/proxy were removed or never added, the Makefile was not updated; host binding was tightened for two of five data services only.
- Fix: bind every published port to `127.0.0.1` in all four compose files; remove `:-default` fallbacks for secrets in the stack files and use `${VAR:?missing}` so an unset secret fails fast; either delete `stack-up-prod` or make it real (separate override file with no published data ports, `DB_AUTO_MIGRATE=false`, env rendered from the production profile into a 0600 env file passed via `--env-file`); fix the echo.
- Verification: `docker compose -f docker-compose.stack.yml config | grep -B1 -A4 "published"` shows `host_ip: 127.0.0.1` for every entry; `env -i PATH=$PATH docker compose -f docker-compose.stack.yml config -q` fails with the "missing" message until secrets are supplied.
- Effort: M | Blast radius: med | Depends on: —

---

## P2

### INFRA-P2-001 — No `securityContext` anywhere; four of five images run as root
- Priority: P2 | Type: security | Area: docker/, deploy/k8s-next
- Evidence: `grep -rn "securityContext\|runAsNonRoot\|automountServiceAccountToken" deploy/k8s-next` returns nothing. docker/Dockerfile.api:26-28 (no `USER`; compare docker/Dockerfile.worker:30 `USER app`)
  ```dockerfile
  EXPOSE 8889

  CMD ["python", "-m", "uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8889"]
  ```
  Same absence of `USER` in Dockerfile.backend, Dockerfile.backend-migrator, Dockerfile.frontend.
- Impact: bot-api — the process that decrypts exchange credentials and spawns traders — runs as uid 0 with a writable root filesystem, default capabilities and a mounted service-account token. Any RCE in an API dependency becomes root in the container with the easiest path to node escape. The namespace cannot be put under the `restricted` Pod Security Standard.
- Root cause: hardening done for the worker image only.
- Fix: add a non-root user to the api/backend/migrator images (copy the worker pattern; static Go binary can use a distroless/nonroot or scratch base); frontend per INFRA-P1-003. In manifests: pod `securityContext: {runAsNonRoot: true, seccompProfile: {type: RuntimeDefault}}`, container `allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: {drop: [ALL]}` with `emptyDir` for /tmp and state dirs, `automountServiceAccountToken: false`; label namespaces `pod-security.kubernetes.io/enforce: restricted`.
- Verification: `docker run --rm <img> id -u` != 0 for each image; `kubectl label --dry-run=server ns dydx-next-staging pod-security.kubernetes.io/enforce=restricted` reports no violations.
- Effort: M | Blast radius: med | Depends on: INFRA-P1-003

### INFRA-P2-002 — Data-tier StatefulSets and migration Jobs have no resource requests or limits
- Priority: P2 | Type: reliability | Area: deploy/k8s-next
- Evidence: deploy/k8s-next/postgresql.yaml:63-71 — the container spec goes from probes straight to `volumeMounts`:
  ```yaml
              initialDelaySeconds: 30
              periodSeconds: 20
            volumeMounts:
              - name: data
                mountPath: /var/lib/postgresql/data
  ```
  `grep -c "resources:" postgresql.yaml valkey.yaml nats.yaml clickhouse.yaml minio.yaml migrations.yaml` finds only the PVC `resources:` stanza in each (none under `containers`). The app Deployments and pgbouncer do set them.
- Impact: Postgres, Valkey, NATS, ClickHouse and MinIO are BestEffort pods: first to be evicted/OOM-killed under node pressure, while the Burstable app pods survive. ClickHouse in particular will take all node memory on a large backtest query and take Postgres down with it on a small k3s node. Eviction of Valkey/NATS mid-session interrupts the command bus and Celery.
- Root cause: omitted in the skeleton.
- Fix: set requests = limits for memory (Guaranteed for Postgres at least), CPU requests for all; cap ClickHouse (`max_server_memory_usage`) to match; add a namespace `LimitRange` so future pods cannot be BestEffort.
- Verification: `kubectl kustomize ... | kubectl apply --dry-run=client -f - -o json | jq '.items[]|select(.kind=="StatefulSet")|.spec.template.spec.containers[].resources'` shows non-empty values; `kubectl get pod postgresql-0 -o jsonpath='{.status.qosClass}'` -> `Guaranteed`.
- Effort: S | Blast radius: low | Depends on: —

### INFRA-P2-003 — Worker probes only check that a process name exists; the stack compose worker has no healthcheck at all
- Priority: P2 | Type: observability | Area: deploy/k8s-next/applications, docker-compose.stack*.yml
- Evidence: deploy/k8s-next/applications.yaml:345-352
  ```yaml
            livenessProbe:
              exec:
                command:
                  - sh
                  - -ec
                  - pgrep -f 'src/main_instance.py' >/dev/null
  ```
  docker-compose.stack.yml:350-446 (`bot-worker`) has no `healthcheck:` key, while docker-compose.bot-worker.yml:89-96 uses `celery ... inspect ping`.
- Impact: a trading loop that is deadlocked, stuck on a dead websocket, or spinning on exceptions is "live" and "ready" forever: no restart, no alert, open positions unmanaged. `pgrep -f` also matches any process whose command line contains the pattern (the probe's own `sh -ec "... src/main_instance.py ..."` wrapper includes it), so the probe can pass with the worker dead. See also Needs verification NV-1 (whether `pgrep` exists in the image at all).
- Root cause: process-existence used as a proxy for health.
- Fix: have the trading loop touch a heartbeat file / update `worker_heartbeats` each cycle and make liveness check its age (`test $(( $(date +%s) - $(stat -c %Y /tmp/heartbeat) )) -lt 120`); use the `celery inspect ping` check from docker-compose.bot-worker.yml for the Celery Deployment and for the stack compose; export heartbeat age as a metric with an alert.
- Verification: `kill -STOP` the worker process in staging -> pod restarted within the liveness window; `docker compose -f docker-compose.stack.yml config | grep -A3 "bot-worker" ` shows a healthcheck.
- Effort: M | Blast radius: low | Depends on: —

### INFRA-P2-004 — `.dockerignore` does not exclude secret-bearing files although every build uses the repo root as context
- Priority: P2 | Type: security | Area: .dockerignore, docker/
- Evidence: .dockerignore:1-17 (complete file is 17 lines: `.git`, caches, `node_modules`, `dist`, `bot_states`, `pair_history`, `*.log` ...) — no entry for `.env*`, `run.json`, `.configkey.bin`, `config/`, `*.pem`, `monorepo.zip`. docker-compose.stack.yml:163 `context: .`; docker/Dockerfile.api:16 and Dockerfile.worker:21
  ```dockerfile
  COPY bot/ .
  ```
  Both `/.configkey.bin` and `/run.json` exist in the working tree (names/sizes only were listed).
- Impact: the config key and the decrypted runtime config are shipped to the Docker daemon on every build (and to any remote/CI builder or build cache export); the untracked `monorepo.zip` at the repo root goes along. They are not in image layers today only because the Dockerfiles copy sub-directories — but `COPY bot/ .` and `COPY backend/ .` will bake in any `bot/.env`, `bot/run.json`, `backend/.env` a developer creates, and one future `COPY . .` publishes the key to ghcr.
- Root cause: ignore file written for size, not for secrets.
- Fix: add `.env`, `.env.*`, `!.env.example`, `**/.env`, `**/.env.*`, `run.json`, `**/run.json`, `.ci-run.json`, `.configkey*`, `config/profiles/`, `*.pem`, `*.key`, `*.zip`, `docs/`, `deploy/`, `.github/`, editor/tooling dot-directories, `.devcontainer/`; add a CI step that fails if a built image contains those names.
- Verification: `docker build --no-cache -f docker/Dockerfile.worker -t t . && docker run --rm --entrypoint sh t -c 'find / -xdev \( -name ".env*" -o -name ".configkey*" \) 2>/dev/null'` prints nothing; build-context size in the build log drops.
- Effort: S | Blast radius: low | Depends on: —

### INFRA-P2-005 — Overlays only build with `--load-restrictor=LoadRestrictionsNone`; `kubectl apply -k` and GitOps controllers reject them
- Priority: P2 | Type: bug | Area: deploy/k8s-next/base
- Evidence: deploy/k8s-next/base/kustomization.yaml:9-11
  ```yaml
  resources:
    - ../namespace.yaml
    - ../platform-config.yaml
  ```
  Real output of `kubectl kustomize deploy/k8s-next/overlays/production`: `error: ... security; file '.../deploy/k8s-next/namespace.yaml' is not in or below '.../deploy/k8s-next/base'` (exit 1). CI passes only because .github/workflows/bot-quality.yml:677-689 adds the flag.
- Impact: the documented deploy path (`apply -k`) fails; Flux's kustomize-controller does not allow disabling the restriction, so the tree cannot be reconciled by GitOps as is. The root `kustomization.yaml` duplicates the base list, so there are two sources of truth. A piped kubeconform on the failed build reports `0 resource found ... exit 0`, i.e. a false green for anyone validating without `pipefail`.
- Root cause: resource files live above `base/`.
- Fix: `git mv` the eleven resource YAMLs into `base/`, delete the duplicate root kustomization (or make it `resources: [base]`), drop the flag from CI, add `kubeconform -strict` to the CI job.
- Verification: `kubectl kustomize deploy/k8s-next/overlays/production | kubeconform -strict -summary -ignore-missing-schemas -` -> `34 resources ... Invalid: 0, Errors: 0` without the flag.
- Effort: S | Blast radius: low | Depends on: —

### INFRA-P2-006 — Builds are not reproducible: floating base tags, no digests, 14 unpinned Python requirements, no hashes
- Priority: P2 | Type: tech-debt | Area: docker/, bot/requirements.txt, deploy/k8s-next
- Evidence: docker/Dockerfile.frontend:44 `FROM nginx:alpine`; docker/Dockerfile.api:1 `FROM python:3.12-slim`; docker/Dockerfile.backend:2 `FROM golang:1.27-alpine AS builder`; deploy/k8s-next/postgresql.yaml:32 `image: postgres:16-alpine`. bot/requirements.txt: 41 lines with `==`, 14 without, e.g.
  ```
  pyyaml
  pandas>=2.3.0
  scipy>=1.18.1
  ```
  `grep -c "hash=" bot/requirements.txt` -> `0`.
- Impact: two builds of the same commit can differ in nginx major version, Python patch level, pandas/scipy/statsmodels versions — the numeric libraries that compute cointegration and z-scores. A rebuild for an unrelated hotfix can change trading signals without a code diff; no supply-chain integrity check on wheels. `postgres:16-alpine` can take a minor upgrade on pod reschedule.
- Root cause: pins applied per dependency ad hoc; no lock file for the bot image.
- Fix: pin every `FROM` and every third-party k8s/compose image to `tag@sha256:digest` and let a bot (Renovate/Dependabot docker ecosystem) bump them; generate `requirements.lock` with `pip-compile --generate-hashes` and install with `--require-hashes`; `go build -trimpath` with `-ldflags "-buildid="`; record the git SHA as an image label.
- Verification: `grep -rhn "^FROM" docker/ | grep -vc "@sha256:"` -> `0`; `pip install --require-hashes -r requirements.lock` succeeds in the image build.
- Effort: M | Blast radius: med | Depends on: —

### INFRA-P2-007 — ClickHouse and NATS in the cluster run with no authentication configured
- Priority: P2 | Type: security | Area: deploy/k8s-next/clickhouse.yaml, nats.yaml
- Evidence: deploy/k8s-next/clickhouse.yaml:34-37 — the container has `image`, `ports`, probes, `volumeMounts` and no `env`:
  ```yaml
          - name: clickhouse
            image: clickhouse/clickhouse-server:24.8
            imagePullPolicy: IfNotPresent
            ports:
  ```
  `grep -n "CLICKHOUSE_PASSWORD\|CLICKHOUSE_USER" deploy/k8s-next/clickhouse.yaml` -> nothing; nats.yaml:42-47 args are `-js -m 8222 -sd /data` only. The apps do receive an (optional) `BACKTEST_CLICKHOUSE_PASSWORD` that the server never gets.
- Impact: once INFRA-P1-001 is fixed or relaxed, NetworkPolicy is the only control: any pod that carries one of the allowed `component` labels can read/alter analytics and publish bot commands onto JetStream (`BOT_COMMAND_BUS_ENABLED: "true"`). A command bus that can start/stop trading should authenticate publishers.
- Root cause: credentials wired on the client side only.
- Fix: set `CLICKHOUSE_USER/PASSWORD` from the existing `backtest-clickhouse` Secret and disable the passwordless default user; NATS config file with per-service users/NKeys and publish/subscribe permissions per subject prefix, mounted from a Secret; then TLS inside the namespace if nodes are not trusted.
- Verification: `kubectl exec clickhouse-0 -- clickhouse-client -q "select 1"` without a password fails; `nats pub bot.commands.x test` with no creds is rejected.
- Effort: M | Blast radius: med | Depends on: INFRA-P1-001

---

## P3

### INFRA-P3-001 — Environment drift and dead infra surface (arm64 vs amd64, compose vs k8s versions, legacy MariaDB manifests, Makefile targets for files that do not exist)
- Priority: P3 | Type: tech-debt | Area: compose files, deploy/k8s, Makefile, scripts
- Evidence: `diff docker-compose.stack.yml docker-compose.stack.arm64.yml` shows the arm64 file lacks, for bot-api and bot-worker:
  ```
  <       BACKTEST_CLICKHOUSE_BATCH_SIZE: "1000"
  <       BACKTEST_CLICKHOUSE_FLUSH_INTERVAL_SECONDS: "5"
  ```
  `diff` of the infra files: amd64 network is `external: true` (must be pre-created, Makefile:447), arm64 is a managed `bridge`. Versions: compose `postgres:15.18-bookworm` / `clickhouse-server:24.1-alpine` vs k8s `postgres:16-alpine` / `clickhouse-server:24.8`. deploy/k8s/dydx-trading-bot-production.yaml:158 `image: mariadb:11.4` and :466 `.../api:latest` — a MariaDB-era stack still tracked although `scripts/check_no_legacy_database.py` exists to forbid it elsewhere. Makefile:243, :264, :274, :282 reference `Dockerfile`, `Dockerfile.dev`, `docker-compose.yml`, `docker-compose.full-stack.yml`; `ls` reports all four missing. scripts/manage_bot.sh:1-5 has no `set -euo pipefail` and its stop path goes TERM -> 2 s -> `kill -KILL` on a trading process (:22-27).
- Impact: four hand-maintained copies of ~450 lines guarantee drift (already present); integration tests run on a different Postgres major than production; the legacy manifests are the first thing a newcomer finds under `deploy/k8s`; broken make targets waste time; a 2-second SIGKILL on the live bot skips graceful shutdown.
- Root cause: copy-paste variants instead of overrides; incomplete cleanup after the MariaDB -> Postgres migration.
- Fix: keep one compose file per stack and make arm64 a 10-line override (`platform:` only) or drop `platform` entirely (all listed images are multi-arch); align image versions across compose and k8s from one variables file; delete `deploy/k8s/` and the dead make targets (or extend the legacy-database check to `deploy/`); give `manage_bot.sh` strict mode and a grace period matching the bot's shutdown path, or delete it if `bot/main.py` is no longer the entrypoint.
- Verification: `diff <(docker compose -f docker-compose.stack.yml config) <(docker compose -f docker-compose.stack.yml -f docker-compose.arm64.override.yml config)` differs only in `platform`; `python3 scripts/check_no_legacy_database.py` covers `deploy/`; `make -n docker-build` no longer exists.
- Effort: M | Blast radius: low | Depends on: —

---

## Needs verification

- NV-1 — `pgrep` may not exist in the worker image, making every worker probe fail. docker/Dockerfile.worker:6-8 installs only `gcc` on `python:3.12-slim`; applications.yaml:342/350/402/410/485/493 call `pgrep`. Slim Debian images normally do not ship `procps`, but this was not proven (no container was run). Check: `docker run --rm --entrypoint sh <worker-image> -c 'command -v pgrep || echo MISSING'`. If missing, this is P1 (workers never Ready and are liveness-killed every ~90 s).
- NV-2 — PgBouncer exposes only one database. pgbouncer.yaml:40-44 sets `POSTGRESQL_DATABASE` to `dydx_platform` only, while bot workloads connect to `dydx_bot` via `pgbouncer:6432`. Check on the replacement image (INFRA-P1-002): `psql "host=pgbouncer port=6432 dbname=dydx_bot ..." -c "select 1"`; also confirm pool mode is compatible with Alembic/SQLAlchemy session features and Go prepared statements (`SHOW CONFIG;` -> `pool_mode`).
- NV-3 — Whether the target cluster's CNI enforces NetworkPolicy (k3s ships an enforcing controller by default). If it does, INFRA-P1-001 is a hard outage on first deploy; if not, the policies give no protection at all. Check: `kubectl -n kube-system get pods | grep -i -E "kube-router|calico|cilium"` and the connectivity test in INFRA-P1-001.
- NV-4 — Graceful shutdown vs. the default 30 s `terminationGracePeriodSeconds`. main_instance.py:564-572 raises `GracefulShutdownException` on SIGTERM; whether the shutdown path (cancel orders / leave positions, persist state) completes within 30 s, and what state is left if it is SIGKILLed, was not traced. Check: time `kill -TERM` to exit on a testnet instance with open orders; inspect exchange open orders afterwards.
- NV-5 — `BACKTEST_ARTIFACTS_DIR: /var/lib/dydx/backtest-artifacts` (platform-config.yaml:72) with no volume mounted in any Deployment (`grep -n "volumeMounts" deploy/k8s-next/applications.yaml` -> nothing) and a non-root worker user. The "local fallback" for artifacts is probably unwritable and in any case ephemeral. Check: `kubectl exec deploy/backtest-worker -- sh -c 'mkdir -p $BACKTEST_ARTIFACTS_DIR && touch $BACKTEST_ARTIFACTS_DIR/x'`.
- NV-6 — Compose healthchecks rely on tools that may be absent from the images: `curl` in the MinIO image (docker-compose.stack.yml:150) and in `nginx:alpine` (:176). If absent the service is permanently `unhealthy` and every `depends_on: service_healthy` consumer never starts. Check: `docker compose -f docker-compose.stack.yml ps` on a running dev stack, or `docker run --rm --entrypoint sh <image> -c 'command -v curl'`.
- NV-7 — Postgres data directory on a PVC root. postgresql.yaml mounts the volume at `/var/lib/postgresql/data` without `PGDATA` sub-directory (the compose files set `PGDATA: .../pgdata`, stack.yml:30). On provisioners that create `lost+found`, `initdb` refuses a non-empty directory. Check: fresh staging deploy on the target storage class; `kubectl logs postgresql-0 | grep -i "exists but is not empty"`.
- NV-8 — `executionlab-config.js` is described as "injected by Kubernetes ConfigMap" (docker/nginx.conf:60-62) but no ConfigMap volume is mounted into the frontend Deployment; the runtime config endpoint likely returns 404 in k8s and the SPA silently falls back to build-time `VITE_*` values (default `https://api.executionlab.io`, Dockerfile.frontend:24). Check: `curl -s -o /dev/null -w '%{http_code}' https://<frontend-host>/executionlab-config.js` and confirm which API origin the deployed bundle calls.

---

## Checks run

| # | Command | Result |
|---|---|---|
| 1 | `docker compose -f docker-compose.infra.yml config -q` | exit 0, no output |
| 2 | `docker compose -f docker-compose.infra.arm64.yml config -q` | exit 0, no output |
| 3 | `docker compose -f docker-compose.stack.yml config -q` | exit 0, no output |
| 4 | `docker compose -f docker-compose.stack.arm64.yml config -q` | exit 0, no output |
| 5 | `docker compose -f docker-compose.bot-worker.yml config -q` | exit 0, no output |
| 6 | `kubectl kustomize deploy/k8s-next/overlays/staging` (as specified, default load restrictor) | exit 1: `error: accumulating resources: ... security; file '.../deploy/k8s-next/namespace.yaml' is not in or below '.../deploy/k8s-next/base'`. kubeconform on the empty result: `Summary: 0 resource found in 1 file - Valid: 0, Invalid: 0, Errors: 0, Skipped: 0` (false green, see INFRA-P2-005) |
| 7 | `kubectl kustomize deploy/k8s-next/overlays/production` (default load restrictor) | exit 1, same error; kubeconform `0 resource found` |
| 8 | `kubectl kustomize --load-restrictor LoadRestrictionsNone deploy/k8s-next/overlays/staging` -> `/home/chris/go/bin/kubeconform -summary -ignore-missing-schemas` | kustomize exit 0; `Summary: 34 resources found in 1 file - Valid: 34, Invalid: 0, Errors: 0, Skipped: 0` |
| 9 | same for `overlays/production` | kustomize exit 0; `Summary: 34 resources found in 1 file - Valid: 34, Invalid: 0, Errors: 0, Skipped: 0` |
| 10 | `grep -c "image: .*:latest"` on the rendered production overlay | `8` |
| 11 | `grep -n "kubernetes.io/metadata.name"` on the rendered production overlay | `dydx-next` and `kube-system` (resources are in `dydx-next-production`) |
| 12 | `python3 scripts/check_no_plaintext_k8s_secrets.py` | `No plaintext k8s secrets detected.` exit 0 |
| 13 | `bash -n` on scripts/build_all_service_images.sh, scripts/install_security_tools.sh, scripts/celery-flower.sh, scripts/manage_bot.sh, the one shell script under .devcontainer/ | all `syntax ok`; `set -euo pipefail` present in all except scripts/manage_bot.sh |
| 14 | `python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" <file>` for all 14 scripts/*.py | all `ast ok` (no bytecode written) |
| 15 | `grep -rn -E "curl.*\|.*sh|wget.*\|.*sh|rm -rf|sudo |chmod 777|--insecure|verify=False" scripts .devcontainer docker` | only `rm -rf /var/lib/apt/lists/*` in three Dockerfiles; no `curl | bash` in the audited area |
| 16 | `docker manifest inspect bitnami/pgbouncer:1.24.0` (registry metadata query; nothing pulled) | `no such manifest: docker.io/bitnami/pgbouncer:1.24.0` |
| 17 | Placeholder classification of `deploy/k8s-next/secrets.local-secret.yaml.example`, legacy `deploy/k8s/*.yaml` `stringData`, `.env.example`, `frontend/.env.example`, `.ci-run.json` (values never printed) | all secret-bearing keys hold placeholder-style values; no real-looking credential found in tracked files |
| 18 | `git ls-files \| grep -E '\.env\|run\.json\|configkey\|\.pem$\|\.key$'` | tracked: `.ci-run.json`, `.env.example`, two tool example env files, `frontend/.env.example`; `run.json` and `.configkey.bin` exist locally and are untracked |

Tools: `kubectl` (with built-in kustomize) present at /usr/bin/kubectl; standalone `kustomize` not installed; `kubeconform` present at /home/chris/go/bin/kubeconform; `docker compose` present. hadolint, trivy, checkov, kube-linter were not run (not checked for / not required by the brief).
