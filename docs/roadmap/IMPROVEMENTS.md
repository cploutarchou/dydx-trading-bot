# Roadmap / Improvements

Tracked improvement work for the platform. This file is the cross-service
index; detailed working lists live in the services.

## Open workstreams (2026-08)

- **Trading-core hardening** — the 2026-08 audit follow-ups: cancel
  verification, wallet-derivation fail-closed, per-instance DB runtime-config
  parity for credentials, exit-slippage budget tuning. Status and evidence in
  `bot/tasks.md` and `bot/IMPROVEMENTS.md`.
- **Backtest validity** — calibration/trade split landed (no full-sample
  look-ahead, out-of-sample pair ranking). Remaining: walk-forward hedge
  estimation (rolling refits), realistic fee defaults anchored to dYdX taker
  fees, fill-at-next-bar-open option.
- **Backend security** — password-change gate, settings secret masking, TOTP
  replay guard and usable backup codes landed. Remaining: TOTP attempt
  bounding on `/auth/2fa/verify`, unsalted SHA-256 secret hashes → Argon2/bcrypt.
- **CI** — promote golangci-lint and stricter eslint gates; consider making
  `make docs-governance` a CI job.

## Completed milestones

- 2026-08: order-lifecycle fail-closed hardening (emergency cleanup on any
  post-fill failure, partial-fill recovery, abort-all redesign); shared-
  subaccount attribution; live/backtest decision parity; suite hermeticity.
- Earlier service-level histories: [root improvements log](../../improvements-0.1.md),
  [bot improvements](../../bot/IMPROVEMENTS.md),
  [implementation progress summary](../IMPLEMENTATION_PROGRESS_SUMMARY.md).
