# Responsive Screenshot Capture Checklist

Use this one-page checklist to capture the exact responsive QA evidence files expected by the project.

## Capture targets

- Base output folder: `docs/screenshots/responsive/`
- Required widths: `375`, `768`, `1024`, `1440`
- Total expected PNG files: `12`

## Exact filenames

### Dashboard

- [x] `docs/screenshots/responsive/dashboard-375.png`
- [x] `docs/screenshots/responsive/dashboard-768.png`
- [x] `docs/screenshots/responsive/dashboard-1024.png`
- [x] `docs/screenshots/responsive/dashboard-1440.png`

### Backtest Details

- [x] `docs/screenshots/responsive/backtest-details-375.png`
- [x] `docs/screenshots/responsive/backtest-details-768.png`
- [x] `docs/screenshots/responsive/backtest-details-1024.png`
- [x] `docs/screenshots/responsive/backtest-details-1440.png`

### Settings

- [x] `docs/screenshots/responsive/settings-375.png`
- [x] `docs/screenshots/responsive/settings-768.png`
- [x] `docs/screenshots/responsive/settings-1024.png`
- [x] `docs/screenshots/responsive/settings-1440.png`

## Recommended route mapping

- `dashboard-*` -> `/dashboard`
- `backtest-details-*` -> `/backtest/mock-run-aabb1122`
- `settings-*` -> `/settings`

## Notes

- Current workspace evidence state: only `docs/screenshots/responsive/.gitkeep` exists.
- Run `npm run qa:screenshots:sync` after adding PNG files to refresh the checkboxes below automatically.
- Do not mark the screenshot QA task complete until all 12 PNG files exist and are referenced in `docs/RESPONSIVE_QA_STATUS.md`.
- Reference guides:
  - `docs/guides/RESPONSIVE_SCREENSHOT_PLAYBOOK.md`
  - `docs/RESPONSIVE_SCREENSHOT_SIGNOFF.md`
  - `docs/RESPONSIVE_QA_STATUS.md`

