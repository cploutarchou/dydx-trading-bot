# Responsive Screenshot Playbook

This playbook helps you capture the final responsive QA evidence referenced by:

- `docs/RESPONSIVE_QA_STATUS.md`
- `docs/RESPONSIVE_SCREENSHOT_SIGNOFF.md`
- `docs/RESPONSIVE_SCREENSHOT_CHECKLIST.md`

## What this script does

The Node helper reads `scripts/responsive-screenshot-routes.json` and generates screenshots for these widths:

- `375`
- `768`
- `1024`
- `1440`

It saves files to:

- `docs/screenshots/responsive/`

By default, capture now runs with an isolated temporary browser profile for cleaner signoff evidence (no persisted extensions/widgets from personal browser sessions).
The script also appends `?qa_screenshots=1` automatically so capture-only CSS can hide floating helper overlays.

## Before you run it

1. Start the frontend dev server.
2. Make sure the app is reachable at `http://localhost:5173` (or pass another base URL).
3. For authenticated routes, pass an existing logged-in Chrome/Chromium/Edge profile.
4. Prefer mock/dev-safe routes where available (the manifest already uses `/backtest/mock-run-aabb1122`).

## Dry run (recommended first)

```bash
cd /path/to/dydx-trading-bot/frontend
node ./scripts/capture-responsive-screenshots.mjs --dry-run
```

## Real capture

Example using an existing browser profile so protected routes keep session state:

```bash
cd /path/to/dydx-trading-bot/frontend
node ./scripts/capture-responsive-screenshots.mjs \
  --user-data-dir "$HOME/.config/google-chrome" \
  --profile-directory Default
```

If needed, target a different frontend URL:

```bash
cd /path/to/dydx-trading-bot/frontend
node ./scripts/capture-responsive-screenshots.mjs \
  --base-url "http://127.0.0.1:5173" \
  --user-data-dir "$HOME/.config/google-chrome" \
  --profile-directory Default
```

## NPM shortcut

```bash
cd /path/to/dydx-trading-bot/frontend
npm run qa:screenshots:plan
```

Clean signoff capture (default isolated profile):

```bash
cd /path/to/dydx-trading-bot/frontend
npm run qa:screenshots:capture
```

## Sync the checklist after screenshots are added

```bash
cd /path/to/dydx-trading-bot/frontend
npm run qa:screenshots:sync
```

This updates the checkboxes in `docs/RESPONSIVE_SCREENSHOT_CHECKLIST.md` based on which PNG files actually exist in `docs/screenshots/responsive/`.

## After capture

1. Verify that the expected PNG files exist in `docs/screenshots/responsive/`.
2. Update `docs/RESPONSIVE_QA_STATUS.md` with real evidence paths.
3. Check off reviewer status in `docs/RESPONSIVE_SCREENSHOT_SIGNOFF.md`.
4. Mark the remaining responsive screenshot task complete in `tasks.md`.

## Expected filenames

- `dashboard-375.png`
- `dashboard-768.png`
- `dashboard-1024.png`
- `dashboard-1440.png`
- `backtest-details-375.png`
- `backtest-details-768.png`
- `backtest-details-1024.png`
- `backtest-details-1440.png`
- `settings-375.png`
- `settings-768.png`
- `settings-1024.png`
- `settings-1440.png`
- `login-coming-soon-375.png`
- `login-coming-soon-768.png`
- `login-coming-soon-1024.png`
- `login-coming-soon-1440.png`
- `unauthorized-coming-soon-375.png`
- `unauthorized-coming-soon-768.png`
- `unauthorized-coming-soon-1024.png`
- `unauthorized-coming-soon-1440.png`

