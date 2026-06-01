# StackForge Release-Ready Follow-ups (Existing Cluster)

This checklist tracks only **post-success cleanup** items after deployment is already healthy.

## Today’s top 3 (15-minute execution plan)

1. **✅ DONE — StackForge v0.1.13 new commands verified (2026-05-31)**
   - `stackforge validate --config stackforge.yaml --production` → `safe: true`
     - One warning: SSH root user — pre-existing pattern, cosmetic only
   - `stackforge verify --config stackforge.yaml` → **ALL OK** across all 3 nodes
     - Consul active + 3-member quorum on all nodes
     - Nomad active + leader elected (`10.0.0.12:4647`) on all nodes
     - Traefik active on control-plane node
     - Firewall (UFW) active on all nodes
     - StackForge control-plane: `{"status":"ok"}`
   - `scripts/post_deploy_verify.sh` → PASS
   - `stackforge deploy --dry-run` → PASS

2. **Config parity update in `stackforge.yaml`** ← still pending
   - Replace scaffold placeholders for:
     - `traefik.email`
     - `traefik.dashboard_domain`
     - `control_plane.domain`
     - `control_plane.admin_api_keys`

3. **Capture release evidence snapshot**
   - Save current outputs for status, inventory, dry-run, and health checks in your deployment notes/ticket.

## v0.1.13 new commands — status notes

| Command | Status | Notes |
|---|---|---|
| `stackforge validate --live/--production` | ✅ Live | Full preflight safety gate |
| `stackforge verify` | ✅ Live | Live 3-node full cluster verification |
| `stackforge nodes onboard` | ✅ Available | Higher-level onboarding — not needed for existing cluster |
| `stackforge deploy init` | ✅ Available | Scaffold generator with `--random-secrets` support |
| `stackforge consul status/members` | ⏳ Needs client config | Requires Consul token wired into CLI context |
| `stackforge nomad status/jobs` | ⏳ Needs client config | Requires Nomad token wired into CLI context |
| `stackforge traefik status/routes` | ⏳ Needs client config | Refusing live behavior until client wired |
| `stackforge traefik consul-catalog check` | ⏳ Not registered | Not in installed binary yet |
| `stackforge domains pool apply-dns/verify-dns` | ✅ Available | Cloudflare DNS automation pool operations |

## Current deployment state

- ✅ Dry-run succeeds (`stackforge deploy --dry-run ...`)
- ✅ API health endpoint responds successfully
- ✅ Frontend endpoint responds successfully
- ✅ Rollback entries are available
- ✅ Existing cluster state under `~/.stackforge/stackforge-cluster/` is valid for day-2 ops

## Non-blocking follow-ups

### 1) Config parity cleanup (repo scaffold vs live state)

- [ ] Replace scaffold placeholders in `stackforge.yaml` with your canonical production values:
  - `traefik.email`
  - `traefik.dashboard_domain`
  - `control_plane.domain`
  - `control_plane.admin_api_keys`
- [ ] Keep values aligned with effective cluster state and runbook docs.

### 2) Operator access hardening

- [ ] Confirm `allowed_admin_cidrs` and `allowed_ssh_cidrs` still match active operator/VPN egress ranges.
- [ ] Remove any obsolete IP ranges from firewall policy and SSH allowlists.

### 3) Observability and diagnostics quality

- [ ] Resolve local-runner SSH reachability warnings for `10.0.0.12` and `10.0.0.13` (routing/VPN/bastion path).
- [ ] Re-run `stackforge components status --config stackforge.yaml --output json` and confirm clean diagnostics from operator workstation.

### 4) Optional DNS automation readiness

- [ ] If planning `--auto-dns=true`, validate Cloudflare zone/token inputs and domain ownership ahead of time.
- [ ] Keep `--auto-dns=false` as default until DNS automation is fully validated.

### 5) Final release check

- [ ] Re-run post-deploy verifier:
  - `scripts/post_deploy_verify.sh --host 159.195.82.201 --cluster stackforge-cluster`
- [ ] Save final evidence artifacts (status, inventory, dry-run, health checks) for audit trail.

## Go/No-Go quick gate (today)

You are **GO** for current existing-cluster operations.

Only pause for a fresh production cutover if any of these become true:

- Dry-run starts failing
- API or frontend health checks fail
- Target node/address mismatch appears
- Effective cluster secrets/domains drift from intended production values
