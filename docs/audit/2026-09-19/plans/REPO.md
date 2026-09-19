# Plan — REPO (monorepo-wide) — 2026-09-19

Evidence, impact and root cause for every ID: `../findings/REPO.md`.

## P2

### REPO-P2-002 — No dependency update or vulnerability scanning for Go modules and npm
- Absorbs: FRONT-P2-016, BACK-P3-003 (scanner part).
- Fix: add `gomod` (`/backend`) and `npm` (`/frontend`) to `.github/dependabot.yml`, mirroring the existing `pip` entry (weekly, grouped). CI scanner steps (`govulncheck`, `npm audit`) are left as a follow-up because neither tool could be run here to establish a clean baseline (`govulncheck` not installed; the npm advisory endpoint returned HTTP 503 during this audit).
- Verification: YAML parses (`python3 -c "import yaml; yaml.safe_load(open('.github/dependabot.yml'))"`); structure matches the existing entries.
- Effort: S | Blast radius: low | Status: done (pending commit) — gomod (/backend) and npm (/frontend) added to the update config; CI scanner steps left as follow-up (no clean baseline obtainable here)

### Proposal-only
- REPO-P2-001 production images built with a different toolchain than CI tests (Go 1.27 / Node 26 images vs Go 1.25 / Node 24 in CI) — proposal (needs the supported version per language; absorbs the version parts of BACK-P3-002 and FRONT-P3-017).
- REPO-P2-003 `quality-gate` is not a required check; images publish without it — proposal (changes how the owner pushes to `master`; exact ruleset change in the finding).

## P3

### REPO-P3-002 — `history-budget.yml` pins `actions/checkout@v4`; every other workflow uses `@v7`
- Fix: bump to `@v7`.
- Verification: YAML parses; the workflow runs on the next push to `master` (not observable from this branch; stated as such).
- Effort: S | Blast radius: low | Status: done (pending commit) — checkout v7

### Deferred / proposal
- REPO-P3-001 docs and devcontainer state Go versions that match nothing — deferred (depends on REPO-P2-001).
- REPO-P3-003 third-party actions pinned by tag in the image-publishing workflow — deferred (SHA pins must be resolved against the upstream repos and verified; do with a dedicated change).
- REPO-P3-004 no `CODEOWNERS` — proposal (needs the owner list).
