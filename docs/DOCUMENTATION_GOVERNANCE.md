# Documentation Governance

This policy ensures docs stay accurate, linked, and archived correctly as platform behavior changes.

## Documentation Update Checklist

Use this checklist in every PR that changes runtime behavior, contracts, config, or operator flow:

- [ ] Updated the owning service README (`frontend/README.md`, `backend/README.md`, or `bot/README.md`) for behavior changes.
- [ ] Updated at least one root/cross-service doc when cross-service behavior changed (`README.md`, `docs/PLATFORM.md`, `docs/DEVELOPMENT.md`, `docs/OPERATIONS.md`).
- [ ] Updated `IMPROVEMENTS.md` status when a roadmap item changed state.
- [ ] Added/updated verification steps in docs if commands, ports, health probes, or deployment gates changed.
- [ ] Added contract notes if request/response payloads or websocket semantics changed.

## Canonical Documentation Link Validation

Canonical docs are link-validated in CI using `scripts/validate_docs_governance.py`.

Validation scope includes:

- `README.md`
- `IMPROVEMENTS.md`
- `docs/*.md`
- service docs (`frontend/README.md`, `backend/README.md`, `bot/README.md`)
- `config/README.md`

CI checks:

1. Canonical docs exist.
2. Local markdown links resolve.
3. Governance sections exist in this policy file.
4. Temporary docs naming patterns are archived under `docs/archive/`.

## Archival Rules

Temporary/handoff/task notes must not remain in root or service roots once the work is complete.

### Approved archival location

- `docs/archive/`

### What should be archived

- implementation handoff notes
- one-off incident notes
- temporary migration/task planning docs
- time-boxed analysis artifacts no longer part of canonical docs

### Naming convention

Use a date-prefixed filename:

- `docs/archive/YYYY-MM-DD-<topic>.md`

Example:

- `docs/archive/2026-04-10-observability-rollout-handoff.md`

### Do not archive these

- service READMEs
- `docs/PLATFORM.md`, `docs/DEVELOPMENT.md`, `docs/OPERATIONS.md`
- roadmap and governance files (`IMPROVEMENTS.md`, `docs/CI_CD_STRATEGY.md`, this file)

## Local Validation

Run docs governance checks locally before pushing:

- `python3 scripts/validate_docs_governance.py`

If the check fails:

1. Fix broken links.
2. Move temporary notes into `docs/archive/`.
3. Ensure checklist/policy sections remain present.
