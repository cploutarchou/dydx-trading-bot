# Responsive Screenshot Sign-off Helper

Use this checklist to capture visual evidence for final responsive sign-off.

Reference playbook: `docs/guides/RESPONSIVE_SCREENSHOT_PLAYBOOK.md`
Exact filename checklist: `docs/RESPONSIVE_SCREENSHOT_CHECKLIST.md`

Current evidence state: `docs/screenshots/responsive/` contains only `.gitkeep`, so all reviewer sign-off rows remain pending until PNG captures are added.

Known blocker from the latest automated attempt: Edge headless capture against the authenticated local profile failed before writing screenshots because of profile-lock / OS crypto decryption errors.

## Capture rules

- Use consistent theme/state (dark mode, authenticated user, same seed data where possible).
- Capture these widths: `375`, `768`, `1024`, `1440`.
- Save files under `docs/screenshots/responsive/`.
- Naming format: `<route-key>-<width>.png` (example: `dashboard-375.png`).

## Required routes

- `/dashboard` -> `dashboard-<width>.png`
- `/backtest/:runId` -> `backtest-details-<width>.png`
- `/settings` -> `settings-<width>.png`

## Reviewer completion template

| Route | 375 | 768 | 1024 | 1440 | Reviewer | Date | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/dashboard` | [ ] Missing | [ ] Missing | [ ] Missing | [ ] Missing |  |  | Pending capture |
| `/backtest/:runId` | [ ] Missing | [ ] Missing | [ ] Missing | [ ] Missing |  |  | Pending capture |
| `/settings` | [ ] Missing | [ ] Missing | [ ] Missing | [ ] Missing |  |  | Pending capture |

