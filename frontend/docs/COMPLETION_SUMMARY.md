# Documentation Cleanup Summary

This file records the current documentation shape after cleanup and reordering.

## Primary entry points

Use these docs in this order:

1. [`docs/README.md`](./README.md)
2. [`docs/SETUP.md`](./SETUP.md)
3. [`docs/guides/TROUBLESHOOTING.md`](./guides/TROUBLESHOOTING.md)
4. [`docs/architecture/README.md`](./architecture/README.md)

## Current structure

```text
docs/
├── README.md
├── INDEX.md
├── SETUP.md
├── COMPLETION_SUMMARY.md
├── RESPONSIVE_QA_STATUS.md
├── RESPONSIVE_SCREENSHOT_SIGNOFF.md
├── RESPONSIVE_SCREENSHOT_CHECKLIST.md
├── architecture/
└── guides/
```

## Cleanup decisions

- kept `docs/README.md` as the canonical entry point
- kept `docs/INDEX.md` as a lightweight quick index
- kept `docs/SETUP.md` focused on supported local setup
- kept troubleshooting and architecture docs as the main references after setup
- removed older container-oriented guidance and overlapping navigation noise

## Status

✅ Current and aligned with the repository’s local macOS/Linux workflow.
