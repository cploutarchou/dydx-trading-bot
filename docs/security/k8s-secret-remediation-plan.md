# k8s secret remediation plan

## Problem summary

The checked-in k8s manifests under `deploy/k8s/` currently contain plaintext secret material in `stringData`, including database passwords, JWT secrets, encryption keys, and bot service tokens. The manifests also embed private key material. That is unsafe for Git history, code review, and accidental copy/paste reuse.

## Recommended remediation approach

Use one of the following open-source secret-management patterns:

1. **SOPS + age**
   - best for encrypted secrets committed to Git
   - good fit when the team wants GitOps-friendly encrypted YAML

2. **Sealed Secrets**
   - good when cluster-scoped sealed objects are preferred
   - useful if the team wants a controller-managed decrypt path

3. **External Secrets Operator**
   - best when the runtime secret source is already outside Git
   - suitable for syncing from a secret backend or external vault

### Recommended default

For this repository, **SOPS + age** is the safest open-source default because it keeps the manifests GitOps-friendly while preventing plaintext secret leakage.

## What should change

### Immediate cleanup

- remove plaintext secret values from `deploy/k8s/*.yaml`
- replace literal `stringData` values with secret references or encrypted secret files
- move private key material out of committed manifests
- keep placeholder Secret names/keys so manifests remain shape-compatible

### Generated local secret files

Local-only secret artifacts should live outside Git or be ignored explicitly, for example:

- `deploy/k8s-next/*.local-secret.yaml`
- `deploy/k8s-next/*.generated-secret.yaml`
- other operator-generated secret manifests that are intended only for local experimentation

## Validation guardrail

Add a repository scan that fails when k8s YAML contains obvious plaintext secret material. The guardrail should catch at least:

- `JWT_SECRET_KEY`
- `SECRET_KEY`
- `ENCRYPTION_KEY`
- `BOT_API_TOKEN`
- `DB_PASSWORD`
- `MARIADB_ROOT_PASSWORD`
- `-----BEGIN PRIVATE KEY-----`

The scanner should be run in CI or through a Makefile validation target.

## Safe rollout sequence

1. Add secret-scan guardrail.
2. Replace plaintext values with placeholders or encrypted manifests.
3. Introduce the chosen secret-management system.
4. Update deployment docs with secret bootstrap steps.
5. Remove legacy plaintext manifest fragments.

## Rollback plan

- If encrypted-secret rollout fails, fall back to the previous deployment version, not to plaintext manifests.
- Keep a local-only bootstrap path for development secrets.
- Never restore plaintext values to Git as a rollback mechanism.

## Acceptance criteria

- no plaintext secrets remain in tracked k8s YAML
- the repository contains a guardrail script for future detection
- deployment manifests only reference secrets by name/key or use encrypted secret workflows
- local development still has a documented way to create ephemeral secrets without committing them
