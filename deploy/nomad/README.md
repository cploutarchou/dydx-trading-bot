# Nomad-native deployment (jobs visible in Nomad UI)

This directory provides a Nomad job path for this stack so workloads show up in `nomad ... /ui/jobs`.

## Important behavior difference

- The live StackForge deploy path in this repo is Nomad-backed.
- Nomad UI shows jobs submitted with `nomad job run ...`.

If those ports are already in use on the target host, stop the existing services before starting the Nomad job to avoid port collisions.

## Files

- `dydx-trading-bot.nomad.hcl` — Nomad job definition (`frontend`, `backend`, `bot`, backend MariaDB, bot MariaDB, `redis`)
- `production.nomad.vars.hcl.example` — variables template (copy and fill with real values)

## 1) Prepare vars file

Create a local vars file that is **not committed**:

- copy `production.nomad.vars.hcl.example` to `production.nomad.vars.hcl`
- fill secret values and image tags

For StackForge-based deploys, also start from `.env.stackforge.example`, copy it to `.env.stackforge`, and fill the live values before running `make deploy`.

Use images that are already pushed and pullable by the Nomad client node.

## 2) Validate and run the Nomad job

From a machine with Nomad CLI access to the cluster:

- `nomad job validate deploy/nomad/dydx-trading-bot.nomad.hcl`
- `nomad job plan -var-file=deploy/nomad/production.nomad.vars.hcl deploy/nomad/dydx-trading-bot.nomad.hcl`
- `nomad job run  -var-file=deploy/nomad/production.nomad.vars.hcl deploy/nomad/dydx-trading-bot.nomad.hcl`

## 3) Verify

- `nomad job status dydx-trading-bot`
- `nomad alloc status <alloc-id>`
- Nomad UI: `/ui/jobs` should show `dydx-trading-bot`

Runtime checks (from deploy node):

- `curl -I http://127.0.0.1:8888/ready`
- `curl -I http://127.0.0.1:5173/`

## Notes

- The job is constrained to `nomad-cp-01` by default (`nomad_node_name`) so it matches the existing single-host exposure model.
- Traefik tags are included on `frontend` and `backend` services for catalog-driven routing setups.
- Frontend runtime depends on build-time `VITE_*` values baked into the image; publish correct images before running the job.
