# StackForge Feature Gaps — GitHub Issues

Created: 2026-06-10
Related work: Attempted Consul ACL + gossip encryption enablement on production cluster

## Issue 1: Consul ACL enablement and token management support

**Title:** `stackforge consul acl` commands for token creation, rotation, and bootstrap

**Description:**

StackForge currently has no CLI support for Consul ACL token operations:

- No command to bootstrap ACL (force-create management token after config enable).
- No command to create new Consul ACL tokens.
- No command to rotate/revoke Consul ACL tokens.
- No token persistence/secure-env wiring helpers.

**Expected behavior:**

- `stackforge consul acl bootstrap --cluster <name> --format json` -> outputs bootstrap token.
- `stackforge consul acl token create --cluster <name> --name <name> --type management --format json`.
- `stackforge consul acl token delete --cluster <name> --accessor <id>`.
- Optional: auto-persist bootstrap token to `/root/.consul-secure-env` with `chmod 600`.

**Impact:** Operators must manually `ssh root@<node> consul acl bootstrap` to enable ACL after config, blocking safe, reproducible security hardening via StackForge automation.

---

## Issue 2: Consul gossip keyring management support

**Title:** `stackforge consul keyring` commands for encryption key rotation

**Description:**

StackForge currently has no CLI support for Consul gossip keyring operations:

- No command to install/activate gossip encryption key.
- No command to list active keys.
- No command to rotate keys (install new, use new, revoke old).
- No helper to generate base64 keys and apply across cluster.

**Expected behavior:**

- `stackforge consul keyring generate --cluster <name>` -> outputs new key.
- `stackforge consul keyring install --cluster <name> --key <base64key>`.
- `stackforge consul keyring use --cluster <name> --key <base64key>`.
- `stackforge consul keyring list --cluster <name>`.
- `stackforge consul keyring delete --cluster <name> --key <base64key>`.

**Impact:** Operators cannot safely rotate gossip encryption keys via StackForge; manual Consul CLI commands on each node are required, introducing drift and human error risk.

---

## Issue 3: Component-level upgrade granularity

**Title:** `stackforge upgrade --component <name>` for selective component upgrades

**Description:**

`stackforge upgrade` currently performs a full coordinated upgrade of all components (control-plane, traefik, consul, nomad).

For security hardening (e.g., if Consul needs a patch to enable ACL/keyring), operators should be able to:

- Upgrade just Consul without touching Nomad/Traefik.
- Pin specific component versions while upgrading others.
- Dry-run component upgrades independently.

**Expected behavior:**

- `stackforge upgrade --component consul --cluster <name> --dry-run`.
- `stackforge upgrade --component consul --cluster <name> --version <version> --confirm-production`.

**Impact:** Reduces blast radius of security feature enablement; avoids unnecessary service restarts; improves operational velocity for isolated fixes.

---

## Issue 4: Consul security config validation and runtime checking

**Title:** `stackforge consul validate` subcommand for ACL/keyring config and runtime state

**Description:**

Currently no StackForge validation ensures that Consul config changes (e.g., `acl { enabled = true }`) actually take effect at runtime:

- No check that `acl.enabled = true` is reflected in API responses (not returning `401 (ACL support disabled)`).
- No check that keyring is active after config deploy.
- No diff between declared config and observed runtime state.

**Expected behavior:**

- `stackforge consul validate --cluster <name> --acl` -> checks `consul acl token list` works (or explains why not).
- `stackforge consul validate --cluster <name> --gossip` -> checks `consul keyring -list` returns keys.
- `stackforge consul validate --config <file>` -> static validation of ACL/keyring config model.

**Impact:** Operators cannot confidently know whether security features are truly enabled after deployment; silent failures are hard to diagnose.

---

## Issue 5: Automated health check for security features

**Title:** Post-deploy health probes for Consul ACL and gossip encryption

**Description:**

`stackforge deploy` and `stackforge upgrade` include health checks for basic service availability but do not validate that optional security features remain functional:

- No check that ACL API is responding (not disabled).
- No check that gossip keyring is intact.
- No validation that Nomad/Traefik can still communicate with Consul after ACL enablement.

**Expected behavior:**

- Post-deploy, include in health checks:
  - `consul acl token list` (if ACL enabled in config).
  - `consul keyring -list` (if encryption enabled in config).
  - `nomad node status` to confirm Nomad can still reach Consul.

**Impact:** Regressions in security feature availability go undetected; operators discover issues only when services fail to connect.

---

## Issue 6: Config model clarity for Consul v2.0 security blocks

**Title:** Document/validate Consul v2.0 ACL and encryption config schema in StackForge

**Description:**

Current StackForge docs and validation do not specify the exact HCL config format for Consul v2.0 security features.

Our attempts to enable ACL and gossip encryption via standard HCL blocks:

```hcl
acl {
  enabled = true
  default_policy = "allow"
  enable_token_persistence = true
}
encrypt = "<base64key>"
```

resulted in runtime reporting `ACL support disabled` and `Keyring is empty` despite config being syntactically valid.

Root cause unknown — possibly:

- Config model changed in v2.0; docs are stale.
- Security features require a different config stanza.
- Feature gates need explicit enablement beyond config.

**Expected behavior:**

- StackForge docs clarify exact v2.0 syntax for ACL and gossip.
- `stackforge validate --config <file>` catches ACL/gossip config errors early.
- Upgrade/install workflows include migration guide for v1→v2 security config.

**Impact:** Trial-and-error security hardening; no confidence that config changes take effect; blocking adoption of Consul security features in production.

---

## Summary table for triage

| Issue                              | Priority | Effort | Blocking                                                                                                   |
| ---------------------------------- | -------- | ------ | ---------------------------------------------------------------------------------------------------------- |
| ACL token management               | High     | Medium | Yes (manual ops only)                                                                                      |
| Keyring management                 | High     | Medium | Yes (manual ops only)                                                                                      |
| Component upgrade granularity      | Medium   | Medium | No (workaround: full upgrade)                                                                              |
| Security config validation         | High     | Small  | Yes (no confidence in state)                                                                               |
| Post-deploy security health checks | High     | Small  | Yes (silent failures possible)                                                                             |
| Consul v2.0 config model docs      | High     | Small  | Yes (unclear what works) changes take effect; blocking adoption of Consul security features in production. |

---

## Summary table for triage

| Issue                              | Priority | Effort | Blocking                       |
| ---------------------------------- | -------- | ------ | ------------------------------ |
| ACL token management               | High     | Medium | Yes (manual ops only)          |
| Keyring management                 | High     | Medium | Yes (manual ops only)          |
| Component upgrade granularity      | Medium   | Medium | No (workaround: full upgrade)  |
| Security config validation         | High     | Small  | Yes (no confidence in state)   |
| Post-deploy security health checks | High     | Small  | Yes (silent failures possible) |
| Consul v2.0 config model docs      | High     | Small  | Yes (unclear what works)       |

---

## Suggested order for implementation

1. **First:** Consul v2.0 config model clarification (smallest, unblocks others).
2. **Second:** Security config validation + health checks (immediate confidence gain).
3. **Third:** ACL token management (core functionality).
4. **Fourth:** Keyring management (core functionality).
5. **Fifth:** Component-level upgrade granularity (nice-to-have, improves operational safety).
