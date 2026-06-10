# Consul Security Enablement — Maintenance Window Run Sheet

Date template: `YYYY-MM-DD`
Target cluster: `stackforge-production`
Window length: `90 minutes`
Primary operator: `_____`
Secondary operator (observer/rollback owner): `_____`

> Use this only after reviewing `docs/consul-security-enablement-go-no-go.md`.

## Success criteria

- Consul quorum remains healthy (3/3 servers) throughout.
- ACL API functional (`consul acl token list` works with management token).
- Gossip keyring functional (`consul keyring -list` returns keys, not empty).
- Nomad and app health remain green.

## Hard stop / abort criteria

Abort immediately and execute rollback if any of these occur:

- Consul quorum drops below 2/3 for more than 60 seconds.
- Leader election flaps repeatedly (3+ elections in 5 min).
- `consul operator raft list-peers` cannot return stable peers.
- `https://api.executionlab.io/ready` fails for > 2 consecutive checks.

---

## T-30 to T-10 (Preflight)

- [ ] Confirm maintenance window and rollback owner on call.
- [ ] Confirm recent backups exist.
- [ ] Confirm current health baseline:
  - [ ] `consul members`
  - [ ] `consul operator raft list-peers`
  - [ ] `nomad node status`
  - [ ] `bash scripts/deploy_status.sh`

Go/No-Go gate:

- **GO** only if all baseline checks are healthy.

---

## T-10 to T-0 (Safety prep)

- [ ] Backup Consul config on all 3 nodes.
- [ ] Snapshot current secure env files (`/root/.nomad-secure-env`, `/root/.consul-secure-env` if present).
- [ ] Open two terminals:
  - Terminal A: control-plane operations
  - Terminal B: continuous health checks

---

## T+0 to T+20 (Platform migration pre-step)

- [ ] Run upgrade readiness dry-run (must be clean):
  - `stackforge upgrade --cluster stackforge-production --config stackforge.yaml --dry-run --output json`
- [ ] If dry-run is clean, execute production upgrade in-window per approved change control.
- [ ] Wait for component health checks to settle.

Go/No-Go gate:

- **GO** only if Consul/Nomad/control-plane health all green post-upgrade.
- **HOLD/ROLLBACK** if upgrade introduces control-plane regressions.

---

## T+20 to T+40 (Enable ACL in rolling sequence)

Order:

1. `nomad-node-01`
2. `nomad-node-02`
3. `nomad-cp-01` (leader last)

For each node:

- [ ] Apply validated ACL config stanza.
- [ ] Restart Consul service.
- [ ] Confirm node rejoins cluster.

After all nodes:

- [ ] Bootstrap ACL management token.
- [ ] Store token in `/root/.consul-secure-env` (`chmod 600`).
- [ ] Verify:
  - [ ] `consul acl token list` works using management token.

Go/No-Go gate:

- **GO** only if ACL list/self commands are successful.
- **ROLLBACK** if API still reports ACL disabled.

---

## T+40 to T+60 (Enable gossip encryption)

- [ ] Generate new gossip key.
- [ ] Apply validated gossip encryption config model on all servers.
- [ ] Perform rolling restart (followers first, leader last).
- [ ] Activate keyring if required by runtime mode.
- [ ] Verify:
  - [ ] `consul keyring -list` returns active keys.

Go/No-Go gate:

- **GO** only if keyring shows active key and no “empty/not enabled” errors.
- **ROLLBACK** if keyring remains unavailable.

---

## T+60 to T+75 (Token/key rotation hardening)

- [ ] Create fresh Consul management token.
- [ ] Update secure env references atomically.
- [ ] Revoke previous token/accessor.
- [ ] Verify new token works (`consul acl token self/list`).

---

## T+75 to T+90 (Final verification + closeout)

- [ ] Consul:
  - [ ] `consul members`
  - [ ] `consul operator raft list-peers`
  - [ ] `consul acl token list`
  - [ ] `consul keyring -list`
- [ ] Nomad:
  - [ ] `nomad node status`
- [ ] App:
  - [ ] `bash scripts/deploy_status.sh`
  - [ ] `https://api.executionlab.io/ready` == healthy

Close criteria:

- [ ] All checks green for 10 continuous minutes.
- [ ] Incident log notes updated with token/key rotation IDs (no secret values).
- [ ] Backups retained and labeled with timestamp.

---

## Fast rollback procedure

If abort criteria triggered:

1. Restore latest known-good `stackforge.hcl` backup on all nodes.
2. Restart Consul followers first, then leader.
3. Re-validate quorum and leadership.
4. Re-validate Nomad and app health.
5. Freeze further security changes until root cause identified.

---

## Post-window checklist (next business day)

- [ ] Remove stale temporary backup files not needed for rollback retention policy.
- [ ] Confirm runbook deltas discovered during window and update docs.
- [ ] Schedule periodic rotation cadence (Nomad done, Consul pending feature support verification).
