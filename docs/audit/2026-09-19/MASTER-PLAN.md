# Master plan — dydx-trading-bot — 2026-09-19

phase: report
branch: audit/2026-09-19-all
base: master
last commit: none
updated: 2026-09-19T18:07Z
scope: all

Findings: BOT 24, BACK 20, FRONT 19, INFRA 20, REPO 7 (90 total; 6 merged as duplicates).
This run executes the small, locally verifiable fixes. Order-path redesigns, anything needing a cluster or a
business decision, and effort M/L items are proposals or deferred with a reason in the service plans.

## Queue (execute top to bottom)
- [x] BOT-P0-003 Scoped abort with empty tracked set flattens the whole subaccount — plans/BOT.md — done (pending commit) — empty scope is a no-op in abort and cancel-all; 4 tests
- [x] BOT-P0-004 Abort treats failed position fetch as no positions and clears tracked state — plans/BOT.md — done (pending commit) — failed position fetch fails closed; tracked state kept when exposure is unknown; 2 tests
- [x] BOT-P0-005 Leg-2 emergency close priced with leg-1 fail-safe price — plans/BOT.md — done (pending commit) — leg-2 close uses a market-2 fail-safe price (new required BotAgent argument); 2 tests extended
- [x] INFRA-P0-001 bot-worker rolls with surge (two traders on one account) — plans/INFRA.md — done (pending commit) — bot-worker strategy Recreate; single-writer lock remains a proposal
- [x] INFRA-P0-002 bot-api runs 2 replicas while supervising pod-local trading processes — plans/INFRA.md — done (pending commit) — bot-api replicas 1 + Recreate, PDB removed; control-plane split remains a proposal
- [x] BOT-P0-001 Bot list/detail endpoints return mnemonics and tokens in plaintext — plans/BOT.md — done (pending commit) — status view drops mnemonic and Telegram token, adds presence flags; 1 test
- [x] BACK-P0-001 Deactivating or demoting a user never revokes sessions — plans/BACK.md — done (pending commit) — admin update/role/status and admin password reset revoke sessions before the write; 4 tests. Refresh-time is_active re-check not added (revocation already invalidates refresh via the generation check)
- [x] BACK-P1-002 NATS pending-command reconciler can never republish — plans/BACK.md — done (pending commit) — reconciler sets a correlation id and rebuilds the first-publish payload shape via a shared builder; 3 tests
- [x] BOT-P1-005 Fill pagination cursor never advances — plans/BOT.md — done (pending commit) — cursor advances from the oldest fill of each page with a no-progress guard; 4 tests, existing pagination test unchanged
- [x] FRONT-P1-001 Global mutation retry re-sends non-idempotent trading POSTs — plans/FRONT.md — done (pending commit) — mutations.retry 0 globally; 1 test
- [x] FRONT-P1-003 Wallet mnemonic reaches the browser console via raw error logging — plans/FRONT.md — done (pending commit) — create path logs a sanitised summary; seed input autocomplete/spellcheck off; 2 tests
- [x] FRONT-P1-004 Logout never clears the query cache — plans/FRONT.md — done (pending commit) — every logged-out transition clears the query cache; 1 test
- [x] INFRA-P1-004 bot-worker command cannot resolve src imports — plans/INFRA.md — done (pending commit) — worker runs python -m src.main_instance; probe patterns updated
- [x] INFRA-P1-003 Frontend Deployment port 8080 vs nginx listen 80 — plans/INFRA.md — done (pending commit) — containerPort 80 matches nginx listen 80, the Service and the NetworkPolicy
- [x] FRONT-P1-005 formatUsdFixed strips the sign and renders missing as $0.00 — plans/FRONT.md — done (pending commit) — new formatUsdBalance (signed, missing renders as em dash) used in the go-live dialog; shared formatters left unchanged; 1 test
- [x] BOT-P1-010 Auth-bypass environment check fails open when unset — plans/BOT.md — done (pending commit) — bypass needs an explicit dev/test label and no conflicting label; unset environment denies; 6 tests
- [x] BACK-P2-001 Redis sessions required only for the "production" label, not "prod" — plans/BACK.md — done (pending commit) — prod and production accepted in APP_ENV or ENVIRONMENT; table test
- [x] REPO-P2-002 No dependency updates for Go modules and npm — plans/REPO.md — done (pending commit) — gomod (/backend) and npm (/frontend) added to the update config; CI scanner steps left as follow-up (no clean baseline obtainable here)
- [x] INFRA-P2-004 .dockerignore does not exclude secret-bearing files — plans/INFRA.md — done (pending commit) — env files, run.json, config key, encrypted profiles, keys and archives excluded from every build context; no image build was run
- [x] BACK-P3-001 url.PathEscape used for query values — plans/BACK.md — done (pending commit) — quick-deploy and benchmark queries built with url.Values; 2 tests
- [x] REPO-P3-002 history-budget workflow pins checkout v4 — plans/REPO.md — done (pending commit) — checkout v7

## Proposal-only (needs a human decision; not executed)
- [ ] BOT-P0-002 Open self-registration; lifecycle routes need only any active user — see OPEN-QUESTIONS.md
- [ ] INFRA-P0-001 (lock part) single-writer lock per instance in main_instance — plans/INFRA.md
- [ ] BOT-P1-001, BOT-P1-002, BOT-P1-003, BOT-P1-004, BOT-P1-006, BOT-P1-007, BOT-P1-008, BOT-P1-009, BOT-P1-012 — order path / design-level — plans/BOT.md
- [ ] BACK-P1-001, BACK-P1-003, BACK-P1-004 — plans/BACK.md
- [ ] FRONT-P1-002, FRONT-P1-006 — plans/FRONT.md
- [ ] INFRA-P1-002, INFRA-P1-005, INFRA-P1-006, INFRA-P1-008, INFRA-P1-009, INFRA-P1-010, INFRA-P3-001 — plans/INFRA.md
- [ ] REPO-P2-001, REPO-P2-003, REPO-P3-004 — plans/REPO.md

## Deferred / invalid
- Deferred with reasons in the service plans: BOT-P1-011, BOT-P2-001..003, BOT-P2-005, BOT-P2-006, BOT-P3-001; BACK-P1-005, BACK-P2-002..011; FRONT-P2-007..015, FRONT-P3-018, FRONT-P3-019; INFRA-P1-001, INFRA-P1-007, INFRA-P2-001..003, INFRA-P2-005..007; REPO-P3-001, REPO-P3-003.
- Merged duplicates: BOT-P2-002 → INFRA-P0-001; BOT-P2-004 → INFRA-P2-001/006; BACK-P3-002 → INFRA-P2-001/006 + REPO-P2-001; BACK-P3-003 → REPO-P2-002; FRONT-P2-016 → REPO-P2-002; FRONT-P3-017 → REPO-P2-001 + INFRA-P2-001/006.
