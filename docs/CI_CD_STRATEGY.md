# CI/CD Strategy

## Pipelines

All effective gates live in the **repo-root** `.github/workflows/` (GitHub
Actions ignores service-level workflow directories):

- **Bot Quality** (`bot-quality.yml`) — the merge gate:
  unit tests (coverage floor 82%), isort/Black/flake8, mypy, bandit (reporting),
  pip-audit (reporting), multi-worker broadcast integration (real
  Postgres+Valkey), external-service integration, k8s plaintext-secret scan,
  compose/kustomize validation, backend Go tests (`-race`), and frontend
  lint/typecheck/contract-tests/build.
- **Build Service Images** (`container-images.yml`) — compose validation and
  image build/publish.
- **Local Dev Setup** (`local-dev-setup.yml`) — validates onboarding targets
  and guides.

## Principles

1. Hermetic CI: jobs carry their own runtime config (`.ci-run.json`) and
   never depend on repo-local secrets like `.configkey.bin`.
2. Gates are blocking; reporting-only scans (bandit, pip-audit) are explicitly
   marked `continue-on-error` with a promotion note.
3. Coverage ratchets only tighten (see `bot/tests/test_exception_handling_ratchet.py`
   for the broad-catch ratchet precedent).
4. Deployment is manual and out-of-band (`deploy/`, `make images-*`); CI never
   touches infrastructure.

## Known gaps

- Backend and frontend lint/format gates beyond the root job (golangci-lint,
  eslint --max-warnings) are not yet enforced in CI.
- `make docs-governance` (this docs tree's validator) is developer-run, not a
  CI gate.
