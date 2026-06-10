# Consul Security Enablement (ACL + Gossip) — Go/No-Go Runbook

Date: 2026-06-10
Scope: Production cluster `stackforge-production` / node set `nomad-cp-01`, `nomad-node-01`, `nomad-node-02`

## Current Observed State (evidence)

- StackForge CLI: `v0.1.14`
- Consul: `v2.0.0`
- Nomad: `v2.0.2`
- Consul quorum: healthy (3/3 servers)
- Runtime API behavior:
  - `consul acl token list` -> `401 (ACL support disabled)`
  - `consul keyring -list` -> `Keyring is empty (encryption not enabled)`
- Dry-run upgrade path is available (`stackforge upgrade --dry-run`) and returns full step sequence.

## Decision Gate

- **Decision:** `HOLD`
- **Confidence:** `High`

Reason: Current runtime does not expose operational ACL/keyring enablement despite config edits and rolling restarts. Enabling/rotating ACL+gossip must be treated as a controlled **platform migration**, not an in-place hot toggle.

---

## Blocking Findings

1. Consul API reports ACL subsystem disabled after config-level attempts.
2. Keyring API reports no active keyring (encryption not enabled), blocking gossip key rotation.
3. Current live behavior indicates feature-gate/model mismatch in Consul v2 runtime packaging or startup mode.

## Residual Risks

- Misaligned security config can create false confidence without real enforcement.
- Attempting forced in-place toggles may risk control-plane instability during future upgrades.
- Nomad/Consul integration can regress if ACL is partially enabled without policy bootstrap and token wiring.

---

## Required Actions Before APPROVE

1. **Platform validation (mandatory)**
   - Confirm with release notes/packaging docs whether this Consul build supports ACL/keyring enablement in current mode.
   - Confirm exact config schema for v2 security blocks used by this package.

2. **Upgrade-first path (recommended)**
   - Execute StackForge upgrade workflow in maintenance window:
     - `stackforge upgrade --dry-run` reviewed
     - `stackforge backup run` completed
     - live `stackforge upgrade --confirm-production --yes`
   - Re-verify post-upgrade that ACL/keyring APIs are functional.

3. **Security enablement in phased cutover**
   - Phase A: enable ACL mode + bootstrap management token + persist secure env.
   - Phase B: enable gossip encryption keyring + install/use key across servers.
   - Phase C: rotate initial bootstrap token to operator token, revoke bootstrap.

4. **Integration hardening**
   - Wire Consul ACL token where required for system agents/services.
   - Add post-change checks in ops runbook (Consul ACL list/self, keyring list, Nomad/Traefik health).

---

## Operator Execution Sequence (once prerequisites are met)

1. Preflight
   - quorum check (`consul members`, `consul operator raft list-peers`)
   - backup configs on all 3 nodes
   - snapshot service health (`stackforge status`, public readiness checks)

2. Enable ACL (follower-first restart, then leader)
   - apply validated ACL config model
   - restart `nomad-node-01`, `nomad-node-02`, then `nomad-cp-01`
   - bootstrap token and store in `/root/.consul-secure-env` with `0600`
   - verify `consul acl token list` works with token

3. Enable gossip encryption (follower-first restart, then leader)
   - apply validated gossip config model
   - install/use keyring key
   - verify `consul keyring -list` on cluster

4. Rotate credentials
   - create new management token
   - update secure env references
   - revoke prior token

5. Validate
   - Consul quorum/leader stable
   - Nomad node status healthy
   - app endpoints healthy

---

## Rollback Plan Check

If any phase fails:

1. Restore `/etc/consul.d/stackforge.hcl` from latest timestamped backup on each node.
2. Restart followers first, then leader.
3. Recheck quorum and service health.
4. Keep bootstrap/new tokens quarantined; only reintroduce after root-cause is resolved.

Rollback viability: **Confirmed** (tested during this session; cluster remained healthy after restore).

---

## Evidence Summary

- Live commands confirmed cluster health and version inventory.
- Multiple runtime checks confirmed ACL/keyring unavailable in current runtime state.
- Dry-run upgrade path is present and suitable as the migration entrypoint.
