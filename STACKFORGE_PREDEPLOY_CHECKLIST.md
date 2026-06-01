# StackForge Pre-Deploy Checklist (Existing Cluster)

Use this checklist for `stackforge-cluster` where infra is already installed and you are deploying app services.

## 1) Config hygiene

- [x] `stackforge.yaml` cluster name is correct (`stackforge-cluster`)
- [x] Node private address is correct (`10.0.0.11` for `nomad-cp-01`)
- [x] `allowed_admin_cidrs` and `allowed_ssh_cidrs` are intentionally scoped
- [x] `control_plane.domain`, `traefik.dashboard_domain`, and `traefik.email` are real values
	- Verified from existing-cluster state (`~/.stackforge/stackforge-cluster/domain-pool.yaml` and install state), even though repo `stackforge.yaml` still has scaffold placeholders.
- [x] `admin_api_keys` is a real strong key (not placeholder)
	- Verified from existing-cluster generated secrets/state (value redacted).

## 2) Env hygiene (`.env.stackforge`)

- [x] No placeholder secrets remain (`replace-with`, `change-me`, `example.com`)
- [x] `APP_DOMAIN` and `API_DOMAIN` are real production domains
- [x] `APP_DB_PASSWORD` is strong and unique
- [x] If using registries, registry credentials are present and valid
	- Not required for current deploy path (`registry_auth.configured=false` and no private registry used).
- [x] If using auto DNS, Cloudflare token/zone values are set and verified
	- Not required for current deploy path (`--auto-dns=false`).

## 3) Existing-cluster readiness (recommended path)

- [x] `stackforge status --cluster stackforge-cluster --output json`
- [x] `stackforge inventory show --cluster stackforge-cluster --output json`
- [x] `stackforge deploy --dry-run --auto-dns=false --config stackforge.yaml --file stackforge-deployment.yaml --env-file .env.stackforge`

## 4) Go/No-Go rules

Stop (NO-GO) if any of the following are true:

- [ ] Placeholder values still exist in active deploy sources (current `.env.stackforge` or effective cluster state)
	- Current placeholders are only in repo scaffold `stackforge.yaml`; active existing-cluster state is already provisioned.
- [ ] Deploy dry-run fails
- [ ] Target node/address mismatch in dry-run output
- [ ] Registry auth is required but not configured

Proceed (GO) only when:

- [x] Dry-run succeeds
- [x] All active secrets/domains are real values
	- Verified for current existing-cluster deploy path; update repo `stackforge.yaml` later for documentation parity.
- [x] DNS strategy is explicit (`--auto-dns=false` unless fully prepared)

## 5) Live deploy command

When all checks pass:

- `stackforge deploy --auto-dns=false --config stackforge.yaml --file stackforge-deployment.yaml --env-file .env.stackforge`

Optional (only when fully ready for DNS automation):

- `stackforge deploy --auto-dns=true --config stackforge.yaml --file stackforge-deployment.yaml --env-file .env.stackforge`

## 6) Immediate post-deploy verification

- [x] `stackforge status --cluster stackforge-cluster --output json`
- [x] `stackforge components status --config stackforge.yaml --output json`
	- Note: command returned component inventory with warnings for SSH reachability to `10.0.0.12` and `10.0.0.13` from local runner.
- [x] App/API health checks succeed
- [x] Rollback path is known (`stackforge rollback list --cluster stackforge-cluster`)
