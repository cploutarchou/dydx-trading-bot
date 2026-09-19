# Service Profile — CI/CD and release conventions

Read before touching `.github/workflows/**` or release tooling.

## Workflows (repo-root `.github/workflows/` only — GitHub ignores service-level dirs)

### bot-quality.yml (the merge gate)
Jobs (all blocking unless noted): bot unit tests (coverage floor 82,
hermetic `.ci-run.json`), bot lint (isort/Black/flake8 E9,F63,F7,F82),
bot mypy (0-error baseline), bandit (reporting), pip-audit (reporting),
multi-worker broadcast (real Postgres+Valkey), external-service
integration, compose validation and toolchain drift check,
backend Go tests (`-race`, `POSTGRES_TEST_DSN` harness), frontend quality
(lint `--max-warnings 0`, typecheck, contracts, build), docs governance,
backend lint golangci v2 (reporting-only, phase 1), quality-gate
(needs all blocking jobs).

### container-images.yml
Compose validation + service image build/publish (`IMAGE_TAG`).

### local-dev-setup.yml
Onboarding target/setup-guide/infra-config validation.

## Conventions

- Hermetic CI: jobs carry `APP_RUN_CONFIG_FILE` + `.ci-run.json`; no
  repo-local secrets (`.configkey.bin`) on runners.
- Ratchets only tighten (coverage floor, broad-catch baseline in
  `bot/tests/test_exception_handling_ratchet.py` with documented
  justification for any increase).
- Reporting-only scans are explicitly `continue-on-error` with a promotion
  note (bandit, pip-audit, golangci phase 1).
- CI never deploys. Images are published to ghcr only after the Quality gate
  passed for the commit; Flux deploys them from the separate GitOps repository.

## Release path

No automated release workflow detected (unknown/unset beyond image
publishing): images tagged via `make images-build/push IMAGE_TAG=...`;
deployment through the GitOps repository (Flux). Maintainers should document a
versioning scheme here if one is adopted.

## Workflow-change rules

Follow `.github/instructions/workflow-yaml.instructions.md`: explicit
triggers, deterministic ordering, safe secret handling. Trigger paths must
include every scope a job validates (bot/**, frontend/**, backend/**,
docs/**, README.md).

## Evidence sources

`.github/workflows/*.yml`, `.github/instructions/workflow-yaml.instructions.md`,
root `Makefile` image targets, `docs/CI_CD_STRATEGY.md`.
