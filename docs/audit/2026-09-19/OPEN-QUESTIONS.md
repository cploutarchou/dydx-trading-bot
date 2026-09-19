# Open questions — 2026-09-19

All twelve questions were answered by the owner on 2026-09-19, or resolved by a read-only look at the k3s cluster. Decisions below unblock the listed tasks; see `MASTER-PLAN.md` for their status.

## Decisions

- [BOT-P0-002] **Disable self-registration on the bot API and require admin/operator on lifecycle routes.** Registration stays off unless an explicit environment flag enables it; create/start/stop/delete need an admin or operator role. The Go gateway remains the only user-management surface. Unblocks: BOT-P0-002.
- [INFRA-P0-001] **Postgres advisory lock.** `main_instance` takes a session-level advisory lock keyed by instance id at start; a second process for the same instance refuses to trade. A lease with fencing token is not required. Unblocks: INFRA-P0-001 (lock part), BOT-P2-002.
- [REPO-P2-001] **Move CI up to the images.** `go.mod` go directive 1.27, CI Node 26, plus a CI check that fails when the image tags and the tested versions drift. Unblocks: REPO-P2-001, REPO-P3-001.
- [REPO-P2-003] **Gate image publishing only.** Direct pushes to `master` stay; `container-images.yml` publishes only after `quality-gate` succeeded for the commit. `quality-gate` does not become a required status check. Unblocks: REPO-P2-003.
- [BACK-P1-003] **Migration 000070 has not been applied anywhere that matters; migrations run through the explicit migrator only.** `DB_AUTO_MIGRATE=false` in deployable manifests and compose, no `Force(version)` recovery at startup, 000070 rehearsed on a copy before it runs. Unblocks: BACK-P1-003, BACK-P1-004.
- [BACK-P1-005] **Traefik ingress in k3s** (observed: Traefik DaemonSet on three nodes behind kube-vip, cert-manager, external-dns; namespace `executionlab-staging`). Add a configurable `TRUSTED_PROXIES` (default loopback) set to the cluster pod CIDR in the deployment, stop trusting raw `X-Forwarded-For`, add a dedicated limiter on auth endpoints. Unblocks: BACK-P1-005.
- [INFRA-P1-005] **The cluster is deployed by Flux from a separate GitOps repository** (observed: Flux kustomizations `apps`, `infra-configs`, `infra-controllers`; live shape differs from `deploy/k8s-next`). **Delete `deploy/k8s` and `deploy/k8s-next`**, their CI validation and dead Makefile targets, and document the GitOps repository as the single source of truth. Closes as not applicable in this repository: INFRA-P1-001, P1-002, P1-005, P1-006, P1-007, P1-009, P2-002, P2-005, P2-007 and the manifest parts of INFRA-P0-001/002, P1-003/004, P2-001, P2-003. Their substance (rollout strategy for the trader, probes, securityContext, NetworkPolicy, TLS) must be checked against the GitOps repository instead. Unblocks: INFRA-P3-001.
- [INFRA-P1-008] **PITR with an RPO of about 5 minutes** (observed: CloudNativePG cluster `postgres` with three instances and the barman-cloud plugin). Continuous WAL archiving, daily base backup, 14 to 30 days retention, periodic restore test. To be verified in the GitOps repository, not implemented here. Unblocks: INFRA-P1-008 (moves to the GitOps repository).
- [INFRA-P1-009] Resolved by observation: cert-manager runs in the cluster; TLS is configured with the ingresses in the GitOps repository. Nothing to do in this repository once `deploy/k8s-next` is removed.
- [BOT-P1-009] **Realised P&L is net of fees, computed from fills.** Per leg: (exit VWAP − entry VWAP) × size × side from indexer fills, minus trading fees on all four fills; funding payments are stored in a separate field; `Decimal` arithmetic, rounded to 6 dp at storage. Unblocks: BOT-P1-009.
- [FRONT-P1-006] **Testnet default and confirmed stop.** The manual runtime form defaults to testnet, `is_testnet` is derived from `chain_id`, numeric inputs are validated, mainnet is an explicit choice. Stopping a runtime shows a confirmation naming the runtime and the bare `s` shortcut is removed. Unblocks: FRONT-P1-006, FRONT-P1-002.
- [BOT-P1-011] **Verify first, then upgrade.** Check the advisory's affected range and the installed SDK's integrity, upgrade `dydx-v4-client` in a dedicated change with the full bot suite, make `pip-audit` blocking with a dated ignore for `ecdsa` until a fix exists. Unblocks: BOT-P1-011.

## Observed during the cluster check (not part of the audit scope)

- The `dns-guard` CronJob in `executionlab-staging` is failing: the last three runs each left three `Failed` pods. Needs triage in the GitOps repository.

## Raised during queue 2

- [BOT-P1-007] On dYdX v4, when a short-term reduce-only order is re-submitted with the same client id (same OrderId) and a later goodTilBlock after the first attempt's outcome is unknown, does the chain count fills already made against that OrderId (so the retry cannot over-close), or does it reject the replacement? Needs a testnet check. Blocks: reusing one client id per logical close.
- [BOT-P1-003] May the write-ahead entry intent add a table to the bot database (expand-only migration), and is there a testnet account on which a killed entry can be rehearsed? Blocks: BOT-P1-003.
- [GitOps] Which settings does the cluster's backend and bot configuration carry today for `DB_AUTO_MIGRATE`, `BOT_API_TOKEN`, `BOT_CREDENTIALS_ENCRYPTION_KEY`, the environment labels, and the pods' termination grace period? Blocks: deploying queue 2 safely.
- [INFRA] Does anything sit between the bot and PostgreSQL that pools connections per transaction? The single-writer lock needs a direct session. Blocks: relying on INFRA-P0-001L in the cluster.
