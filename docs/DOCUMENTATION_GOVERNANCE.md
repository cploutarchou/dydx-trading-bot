# Documentation Governance

This file defines the rules for the canonical docs tree. Validation:
`make docs-governance` (runs `scripts/validate_docs_governance.py`).

## Documentation Update Checklist

When changing behavior, update in the same change:

- [ ] The touched service's README (bot/backend/frontend).
- [ ] `bot/openapi.json` when API contracts change.
- [ ] The canonical doc here (PLATFORM/DEVELOPMENT/OPERATIONS/CI_CD_STRATEGY)
      when the change affects what those documents describe.
- [ ] Linked customization files (`.github/CUSTOMIZATION_INDEX.md` and
      service indexes) when skills/agents/prompts move.

Never document intent that the code does not implement. Removed features must
have their links removed, not left dangling.

## Canonical Documentation Link Validation

- Every local markdown link in the canonical docs and service READMEs must
  resolve to a file in the repository.
- Prefer repo-relative links (`../bot/README.md`); never absolute local
  filesystem paths (they break on other machines).
- External links (http/https) are allowed but should reference stable URLs.

## Archival Rules

- Temporary/handoff-style notes (filenames containing handoff, temp, tmp,
  task-note, working-notes) must live under `docs/archive/` or be deleted.
- Superseded planning documents move to `docs/archive/` rather than being
  edited in place; historical state should stay readable.
- The `improvements-*.md` files at the repo root and `bot/IMPROVEMENTS.md`
  are tracked working documents and are exempt from archival renaming.
