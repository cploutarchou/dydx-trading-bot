# Responsive Screenshot Checklist

Regenerated from `scripts/responsive-screenshot-routes.json` x capture widths
(390/768/1440/1920) so the checklist reflects what the capture tool actually
produces. `npm run qa:screenshots:sync` keeps these checkboxes in sync with
the files on disk.

Screenshot PNGs are intentionally not committed (root .gitignore policy); this checklist reflects captures on the QA machine that ran them. Re-run `npm run qa:screenshots:capture` to reproduce locally.

Auth-gated routes require a logged-in browser profile via `--user-data-dir`
per `docs/guides/RESPONSIVE_SCREENSHOT_PLAYBOOK.md`; without one they capture
the auth redirect and are listed unchecked.

- [x] `docs/screenshots/responsive/public-launch-390.png`
- [x] `docs/screenshots/responsive/public-launch-768.png`
- [x] `docs/screenshots/responsive/public-launch-1440.png`
- [x] `docs/screenshots/responsive/public-launch-1920.png`
- [x] `docs/screenshots/responsive/ico-briefing-390.png`
- [x] `docs/screenshots/responsive/ico-briefing-768.png`
- [x] `docs/screenshots/responsive/ico-briefing-1440.png`
- [x] `docs/screenshots/responsive/ico-briefing-1920.png`
- [x] `docs/screenshots/responsive/ico-whitepaper-390.png`
- [x] `docs/screenshots/responsive/ico-whitepaper-768.png`
- [x] `docs/screenshots/responsive/ico-whitepaper-1440.png`
- [x] `docs/screenshots/responsive/ico-whitepaper-1920.png`
- [x] `docs/screenshots/responsive/ico-tokenomics-390.png`
- [x] `docs/screenshots/responsive/ico-tokenomics-768.png`
- [x] `docs/screenshots/responsive/ico-tokenomics-1440.png`
- [x] `docs/screenshots/responsive/ico-tokenomics-1920.png`
- [x] `docs/screenshots/responsive/ico-privacy-notice-390.png`
- [x] `docs/screenshots/responsive/ico-privacy-notice-768.png`
- [x] `docs/screenshots/responsive/ico-privacy-notice-1440.png`
- [x] `docs/screenshots/responsive/ico-privacy-notice-1920.png`
- [x] `docs/screenshots/responsive/ico-participation-terms-390.png`
- [x] `docs/screenshots/responsive/ico-participation-terms-768.png`
- [x] `docs/screenshots/responsive/ico-participation-terms-1440.png`
- [x] `docs/screenshots/responsive/ico-participation-terms-1920.png`
- [ ] `docs/screenshots/responsive/login-390.png`
- [ ] `docs/screenshots/responsive/login-768.png`
- [ ] `docs/screenshots/responsive/login-1440.png`
- [ ] `docs/screenshots/responsive/login-1920.png`
- [ ] `docs/screenshots/responsive/dashboard-390.png` (auth-gated)
- [ ] `docs/screenshots/responsive/dashboard-768.png` (auth-gated)
- [ ] `docs/screenshots/responsive/dashboard-1440.png` (auth-gated)
- [ ] `docs/screenshots/responsive/dashboard-1920.png` (auth-gated)
- [ ] `docs/screenshots/responsive/backtest-details-390.png` (auth-gated)
- [ ] `docs/screenshots/responsive/backtest-details-768.png` (auth-gated)
- [ ] `docs/screenshots/responsive/backtest-details-1440.png` (auth-gated)
- [ ] `docs/screenshots/responsive/backtest-details-1920.png` (auth-gated)
- [ ] `docs/screenshots/responsive/settings-390.png` (auth-gated)
- [ ] `docs/screenshots/responsive/settings-768.png` (auth-gated)
- [ ] `docs/screenshots/responsive/settings-1440.png` (auth-gated)
- [ ] `docs/screenshots/responsive/settings-1920.png` (auth-gated)
- [ ] `docs/screenshots/responsive/login-coming-soon-390.png`
- [ ] `docs/screenshots/responsive/login-coming-soon-768.png`
- [ ] `docs/screenshots/responsive/login-coming-soon-1440.png`
- [ ] `docs/screenshots/responsive/login-coming-soon-1920.png`
- [ ] `docs/screenshots/responsive/unauthorized-coming-soon-390.png`
- [ ] `docs/screenshots/responsive/unauthorized-coming-soon-768.png`
- [ ] `docs/screenshots/responsive/unauthorized-coming-soon-1440.png`
- [ ] `docs/screenshots/responsive/unauthorized-coming-soon-1920.png`

**Status: 24 files present** (public routes captured 2026-09-05; capture of timer-driven ICO surfaces stalls under Chrome virtual-time budget — rerun `npm run qa:screenshots:capture` to extend coverage).
