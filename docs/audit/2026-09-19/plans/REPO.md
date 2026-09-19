# Plan — REPO (monorepo-wide) — 2026-09-19

Evidence, impact and root cause for every ID: `../findings/REPO.md`.

## P2

### REPO-P2-002 — No dependency update or vulnerability scanning for Go modules and npm
- Absorbs: FRONT-P2-016, BACK-P3-003 (scanner part).
- Fix: add `gomod` (`/backend`) and `npm` (`/frontend`) to `.github/dependabot.yml`, mirroring the existing `pip` entry (weekly, grouped). CI scanner steps (`govulncheck`, `npm audit`) are left as a follow-up because neither tool could be run here to establish a clean baseline (`govulncheck` not installed; the npm advisory endpoint returned HTTP 503 during this audit).
- Verification: YAML parses (`python3 -c "import yaml; yaml.safe_load(open('.github/dependabot.yml'))"`); structure matches the existing entries.
- Effort: S | Blast radius: low | Status: done (36723306) — gomod (/backend) and npm (/frontend) added to the update config; CI scanner steps left as follow-up (no clean baseline obtainable here)

### Proposal-only
- REPO-P2-001 production images built with a different toolchain than CI tests (Go 1.27 / Node 26 images vs Go 1.25 / Node 24 in CI) — proposal (needs the supported version per language; absorbs the version parts of BACK-P3-002 and FRONT-P3-017).
- REPO-P2-003 `quality-gate` is not a required check; images publish without it — proposal (changes how the owner pushes to `master`; exact ruleset change in the finding).

## P3

### REPO-P3-002 — `history-budget.yml` pins `actions/checkout@v4`; every other workflow uses `@v7`
- Fix: bump to `@v7`.
- Verification: YAML parses; the workflow runs on the next push to `master` (not observable from this branch; stated as such).
- Effort: S | Blast radius: low | Status: done (36723306) — checkout v7

### Deferred / proposal
- REPO-P3-001 docs and devcontainer state Go versions that match nothing — deferred (depends on REPO-P2-001).
- REPO-P3-003 third-party actions pinned by tag in the image-publishing workflow — deferred (SHA pins must be resolved against the upstream repos and verified; do with a dedicated change).
- REPO-P3-004 no `CODEOWNERS` — proposal (needs the owner list).

## Queue 2 — unblocked by the owner's decisions (2026-09-19)

### REPO-P2-003 — Publish images only after `quality-gate`
- Decision: direct pushes to `master` stay; `container-images.yml` publishes only when `quality-gate` succeeded for the same commit. Not a required status check.
- Verification: workflow YAML parses; PR builds still run without pushing; first push to `master` shows publish waiting on the gate.
- Effort: S | Blast radius: med | Status: todo

### REPO-P2-001 — One toolchain for tests and images
- Decision: move CI up to the images: `go.mod` go 1.27, CI Node 26, plus a CI check that fails when image tags and tested versions drift.
- Verification: `go build ./... && go vet ./... && go test -race ./...` on 1.27; frontend gates on Node 26; drift check red when a tag is changed on purpose.
- Effort: S | Blast radius: med | Status: todo

### REPO-P3-001 — Correct Go version statements
- Verification: `grep -rn 'Go 1\.' zcode-marketplace/plugins/monorepo-experts/references backend/.devcontainer/Dockerfile` agrees with `go.mod`.
- Effort: S | Blast radius: low | Depends on: REPO-P2-001 | Status: todo

### REPO-P3-004 — Add `CODEOWNERS` (moved from proposal at the owner's request)
- Fix: `.github/CODEOWNERS` with the repository owner (`@cploutarchou`) as default owner and explicit entries for the order path (`bot/src/trading/`), auth (`backend/internal/auth/`, `backend/internal/middleware/`, `bot/src/middleware/`), migrations and workflows, so ownership is recorded and review requests route automatically when collaborators are added.
- Verification: GitHub reports no CODEOWNERS errors for the branch (`gh api repos/cploutarchou/dydx-trading-bot/codeowners/errors`).
- Effort: S | Blast radius: low | Status: todo
