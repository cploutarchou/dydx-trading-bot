# Findings — REPO (monorepo-wide) — 2026-09-19

Scope: CI/CD, toolchain and dependency policy, secrets handling, repository hygiene, cross-service conventions.
IDs are provisional until consolidation.

### REPO-P2-001 — Production images are built with a different toolchain than CI tests
- Priority: P2 | Type: reliability | Area: ci / docker
- Evidence: `docker/Dockerfile.backend:2`, `docker/Dockerfile.backend-migrator:10`, `.github/workflows/bot-quality.yml:729`, `docker/Dockerfile.frontend:6`, `.github/workflows/bot-quality.yml:769`
  ```
  FROM golang:1.27-alpine AS builder            # Dockerfile.backend
  go-version-file: backend/go.mod               # CI -> go 1.25.0
  FROM node:26-alpine AS builder                # Dockerfile.frontend
  node-version: "24"                            # CI
  ```
- Impact: `go test -race` and the frontend lint/typecheck/build gates run on Go 1.25 / Node 24, while the shipped binaries and bundle are produced by Go 1.27 / Node 26. A compiler, runtime or stdlib behaviour change between the two is never exercised by a test before it reaches production.
- Root cause: base images were bumped (dependabot `docker` ecosystem) without moving `go.mod` / CI `node-version`; nothing ties the two together.
- Fix: decide the supported version per language [CONFIRM], then make CI and the Dockerfiles agree (either bump `go.mod` `go` directive + CI Node to match the images, or pin the images back). Add a small CI check that fails when the `golang:` tag minor differs from `go.mod` and the `node:` tag major differs from the CI `node-version`.
- Verification: `grep -n 'FROM golang' docker/Dockerfile.backend*; grep -n '^go ' backend/go.mod`; new CI check green.
- Effort: S | Blast radius: med | Depends on: —

### REPO-P2-002 — No dependency update or vulnerability scanning for Go modules and npm
- Priority: P2 | Type: security | Area: ci / dependencies
- Evidence: `.github/dependabot.yml:10,33,40` (only `pip`, `github-actions`, `docker`); `grep -nE 'govulncheck|npm audit|trivy|grype|gitleaks|codeql' .github/workflows/*.yml` returns nothing
  ```yaml
  - package-ecosystem: pip
  - package-ecosystem: github-actions
  - package-ecosystem: docker
  ```
- Impact: the bot has `pip-audit` in CI, but the internet-facing Go gateway (auth, sessions) and the React bundle get no automated CVE signal and no update PRs.
- Root cause: dependency tooling was set up for `bot/` first and never extended.
- Fix: add `gomod` (`/backend`) and `npm` (`/frontend`) ecosystems to `.github/dependabot.yml` with the same weekly cadence and grouping as `pip`; add a non-blocking-then-blocking `govulncheck ./...` step to `backend-tests` and `npm audit --omit=dev --audit-level=high` to `frontend-quality`.
- Verification: dependabot config validates on push; CI jobs show the new steps' real output.
- Effort: S | Blast radius: low | Depends on: —

### REPO-P2-003 — `quality-gate` is not a required check; `master` accepts direct pushes with red CI
- Priority: P2 | Type: reliability | Area: governance / ci
- Evidence: `gh api repos/cploutarchou/dydx-trading-bot/branches/master/protection` → `404 Branch not protected`; ruleset `Protect` (id 21112202, active, `~DEFAULT_BRANCH`) contains only
  ```json
  {"type":"deletion"},{"type":"non_fast_forward"}
  ```
  while `.github/workflows/bot-quality.yml:872` defines an aggregate `quality-gate` job.
- Impact: every blocking gate (bot tests at 82% coverage, `go test -race`, frontend lint/typecheck/e2e, k8s secret scan) is advisory. A push to `master` with failing tests still triggers `container-images.yml` and publishes images.
- Root cause: the ruleset was created for history protection only.
- Fix: proposal — add a `required_status_checks` rule for `quality-gate` (and `Max 4 commits per day`) to the ruleset, and make `container-images.yml` publish only after `quality-gate` succeeds (`workflow_run` or a `needs` chain). Changes how the owner pushes to `master`, so it needs a human decision.
- Verification: `gh api repos/cploutarchou/dydx-trading-bot/rulesets/21112202` lists `required_status_checks`; a red PR cannot merge.
- Effort: S | Blast radius: med | Depends on: —

### REPO-P3-001 — Docs and devcontainer state Go versions that match neither `go.mod` nor the image
- Priority: P3 | Type: docs | Area: docs / devcontainer
- Evidence: `zcode-marketplace/plugins/monorepo-experts/references/monorepo-map.md:17`, `.../backend-service.md:14`, `backend/.devcontainer/Dockerfile:2-3`
  ```
  -> backend/ (Go 1.26 / Gin API gateway, :8888)
  # Base image ships Go 1.25 (matches backend/go.mod `go 1.25.0` and
  # docker/Dockerfile.backend `golang:1.25-alpine`), git, and a non-root
  ```
- Impact: three sources name three versions (1.25, 1.26, 1.27); the devcontainer comment is factually wrong about the Dockerfile.
- Root cause: version bumps did not update prose.
- Fix: after REPO-P2-001 settles the version, correct the two profiles and the devcontainer comment.
- Verification: `grep -rn 'Go 1\.' zcode-marketplace/plugins/monorepo-experts/references backend/.devcontainer/Dockerfile`
- Effort: S | Blast radius: low | Depends on: REPO-P2-001

### REPO-P3-002 — `history-budget.yml` pins `actions/checkout@v4` while every other workflow uses `@v7`
- Priority: P3 | Type: tech-debt | Area: ci
- Evidence: `.github/workflows/history-budget.yml:26` vs 20 uses of `actions/checkout@v7` elsewhere
  ```yaml
  uses: actions/checkout@v4
  ```
- Impact: inconsistent action major; an open dependabot branch (`dependabot/github_actions/actions/checkout-7`) already proposes the bump.
- Fix: bump to `@v7` (or merge the dependabot PR).
- Verification: workflow run green on next push to master.
- Effort: S | Blast radius: low | Depends on: —

### REPO-P3-003 — Third-party actions in the image-publishing workflow are pinned by tag, not commit SHA
- Priority: P3 | Type: security | Area: ci / supply chain
- Evidence: `.github/workflows/container-images.yml:30-32` and its `uses:` lines
  ```yaml
  permissions:
      contents: read
      packages: write
  ```
  with `docker/login-action@v4`, `docker/build-push-action@v7`, `docker/metadata-action@v6`, `docker/setup-buildx-action@v4`.
- Impact: a moved tag on a third-party action would run with `packages: write` and could publish a tampered image that the cluster then pulls.
- Fix: pin the four `docker/*` actions to full commit SHAs with the version in a trailing comment; dependabot's `github-actions` ecosystem keeps SHA pins updated.
- Verification: `grep -n 'uses: docker/' .github/workflows/container-images.yml` shows 40-hex refs; workflow green.
- Effort: S | Blast radius: low | Depends on: —

### REPO-P3-004 — No `CODEOWNERS`
- Priority: P3 | Type: docs | Area: governance
- Evidence: neither `CODEOWNERS` nor `.github/CODEOWNERS` exists (`test -f` on both).
- Impact: no recorded owner per service; review routing for order-path changes is by convention only.
- Fix: proposal only — needs the owner list from a human.
- Effort: S | Blast radius: low | Depends on: —

## Secret scan

`gitleaks` is not installed. Pattern grep over tracked files (AWS keys, private-key headers, GitHub/Slack/Stripe/Resend token shapes, quoted `password|secret|token|api_key|mnemonic` assignments): no real credential found. Hits reviewed:
- `deploy/k8s/dydx-trading-bot-{staging,production}.yaml:19-27` — `REPLACE…` placeholders.
- `bot/src/api/auth_utils.py:503` — literal test password inside an `if __name__ == "__main__":` self-test block (dead demo code in `src`; covered under BOT if the service investigation raises it).
- `scripts/check_no_plaintext_k8s_secrets.py:18` — the detector's own marker string.
`.configkey.bin` and `run.json` are git-ignored (`.gitignore:220-221`). `.ci-run.json` is tracked and contains only non-secret Redis/env settings (keys inspected, values not printed).

## Needs verification

- `bot/openapi.json` may be stale relative to the FastAPI app. Check: regenerate with the repo's documented command and `git diff --stat bot/openapi.json`.
- Whether branch protection on `master` requires the `quality-gate` job. Check: `gh api repos/cploutarchou/dydx-trading-bot/branches/master/protection`.

## Checks run

- `gh run list --limit 12` → all `success` (latest 2026-09-13, dependabot branches and master).
- Secret pattern grep (commands in LOG.md) → no credential found.
- `git check-ignore -v .configkey.bin run.json` → both ignored.
