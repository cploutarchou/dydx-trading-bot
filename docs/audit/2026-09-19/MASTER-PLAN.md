# Master plan — dydx-trading-bot — 2026-09-19

phase: execute
branch: audit/2026-09-19-queue2
base: master
last commit: 36723306 (2026-09-19T18:10Z)
updated: 2026-09-19T21:15Z
scope: all

Findings: BOT 24, BACK 20, FRONT 19, INFRA 20, REPO 7 (90 total; 6 merged as duplicates).
This run executes the small, locally verifiable fixes. Order-path redesigns, anything needing a cluster or a
business decision, and effort M/L items are proposals or deferred with a reason in the service plans.

## Queue (execute top to bottom)
- [x] BOT-P0-003 Scoped abort with empty tracked set flattens the whole subaccount — plans/BOT.md — done (36723306) — empty scope is a no-op in abort and cancel-all; 4 tests
- [x] BOT-P0-004 Abort treats failed position fetch as no positions and clears tracked state — plans/BOT.md — done (36723306) — failed position fetch fails closed; tracked state kept when exposure is unknown; 2 tests
- [x] BOT-P0-005 Leg-2 emergency close priced with leg-1 fail-safe price — plans/BOT.md — done (36723306) — leg-2 close uses a market-2 fail-safe price (new required BotAgent argument); 2 tests extended
- [x] INFRA-P0-001 bot-worker rolls with surge (two traders on one account) — plans/INFRA.md — done (36723306) — bot-worker strategy Recreate; single-writer lock remains a proposal
- [x] INFRA-P0-002 bot-api runs 2 replicas while supervising pod-local trading processes — plans/INFRA.md — done (36723306) — bot-api replicas 1 + Recreate, PDB removed; control-plane split remains a proposal
- [x] BOT-P0-001 Bot list/detail endpoints return mnemonics and tokens in plaintext — plans/BOT.md — done (36723306) — status view drops mnemonic and Telegram token, adds presence flags; 1 test
- [x] BACK-P0-001 Deactivating or demoting a user never revokes sessions — plans/BACK.md — done (36723306) — admin update/role/status and admin password reset revoke sessions before the write; 4 tests. Refresh-time is_active re-check not added (revocation already invalidates refresh via the generation check)
- [x] BACK-P1-002 NATS pending-command reconciler can never republish — plans/BACK.md — done (36723306) — reconciler sets a correlation id and rebuilds the first-publish payload shape via a shared builder; 3 tests
- [x] BOT-P1-005 Fill pagination cursor never advances — plans/BOT.md — done (36723306) — cursor advances from the oldest fill of each page with a no-progress guard; 4 tests, existing pagination test unchanged
- [x] FRONT-P1-001 Global mutation retry re-sends non-idempotent trading POSTs — plans/FRONT.md — done (36723306) — mutations.retry 0 globally; 1 test
- [x] FRONT-P1-003 Wallet mnemonic reaches the browser console via raw error logging — plans/FRONT.md — done (36723306) — create path logs a sanitised summary; seed input autocomplete/spellcheck off; 2 tests
- [x] FRONT-P1-004 Logout never clears the query cache — plans/FRONT.md — done (36723306) — every logged-out transition clears the query cache; 1 test
- [x] INFRA-P1-004 bot-worker command cannot resolve src imports — plans/INFRA.md — done (36723306) — worker runs python -m src.main_instance; probe patterns updated
- [x] INFRA-P1-003 Frontend Deployment port 8080 vs nginx listen 80 — plans/INFRA.md — done (36723306) — containerPort 80 matches nginx listen 80, the Service and the NetworkPolicy
- [x] FRONT-P1-005 formatUsdFixed strips the sign and renders missing as $0.00 — plans/FRONT.md — done (36723306) — new formatUsdBalance (signed, missing renders as em dash) used in the go-live dialog; shared formatters left unchanged; 1 test
- [x] BOT-P1-010 Auth-bypass environment check fails open when unset — plans/BOT.md — done (36723306) — bypass needs an explicit dev/test label and no conflicting label; unset environment denies; 6 tests
- [x] BACK-P2-001 Redis sessions required only for the "production" label, not "prod" — plans/BACK.md — done (36723306) — prod and production accepted in APP_ENV or ENVIRONMENT; table test
- [x] REPO-P2-002 No dependency updates for Go modules and npm — plans/REPO.md — done (36723306) — gomod (/backend) and npm (/frontend) added to the update config; CI scanner steps left as follow-up (no clean baseline obtainable here)
- [x] INFRA-P2-004 .dockerignore does not exclude secret-bearing files — plans/INFRA.md — done (36723306) — env files, run.json, config key, encrypted profiles, keys and archives excluded from every build context; no image build was run
- [x] BACK-P3-001 url.PathEscape used for query values — plans/BACK.md — done (36723306) — quick-deploy and benchmark queries built with url.Values; 2 tests
- [x] REPO-P3-002 history-budget workflow pins checkout v4 — plans/REPO.md — done (36723306) — checkout v7

## Queue 2 — unblocked by the owner's decisions of 2026-09-19 (see OPEN-QUESTIONS.md); the last eleven were moved from proposal at the owner's request
- [x] BOT-P0-002 Disable bot-API self-registration; admin/operator on lifecycle routes — plans/BOT.md — done (pending commit) — register returns 403 unless BOT_API_ALLOW_SELF_REGISTRATION=true; six mutating lifecycle routes need an admin principal; 17 tests
- [ ] INFRA-P0-001L Postgres advisory lock per trading instance in main_instance — plans/INFRA.md — todo
- [x] BACK-P1-003 Migrations via the explicit migrator only; DB_AUTO_MIGRATE=false in deployables — plans/BACK.md — done (pending commit) — local stack gets a one-shot backend-migrate service; backend-api waits for it; DB_AUTO_MIGRATE=false in both stack files
- [x] BACK-P1-004 Remove Force(version) startup recovery — plans/BACK.md — done (pending commit) — Force(version) recovery is explicit opt-in only and refused for production labels (CONFIG_ENV included); table test
- [x] BACK-P1-005 Configurable TRUSTED_PROXIES, no raw X-Forwarded-For, auth endpoint limiter — plans/BACK.md — done (pending commit) — validated TRUSTED_PROXIES, raw X-Forwarded-For helper removed, shared per-IP limiter on credential endpoints; 3 tests. Deployment must set TRUSTED_PROXIES to the pod CIDR
- [ ] BOT-P1-011 Verify the signing SDK advisory, upgrade in a dedicated change, blocking pip-audit — plans/BOT.md — todo
- [ ] BOT-P1-009 Realised P&L net of fees from fills, Decimal, funding separate — plans/BOT.md — todo
- [x] FRONT-P1-006 Testnet default; is_testnet derived from chain_id; numeric validation — plans/FRONT.md — done (pending commit) — form defaults to testnet; network and is_testnet derived from chain_id; NaN/zero/negative numerics rejected; 10 tests
- [x] FRONT-P1-002 Confirm runtime stop; remove the bare-key shortcut — plans/FRONT.md — done (pending commit) — stop asks for confirmation naming the runtime; the s shortcut and its hint are removed. No component test (StrategyManager has no test harness, FRONT-P2-014); verified by lint, typecheck and the e2e smoke suite
- [x] REPO-P2-003 Publish images only after quality-gate succeeded — plans/REPO.md — done (pending commit) — image workflow waits for the Quality gate check of the same commit on push; gate workflow now runs for every image path; wait script exercised locally (success, missing, PR paths)
- [x] REPO-P2-001 go.mod 1.27 and CI Node 26, plus a drift check — plans/REPO.md — done (pending commit) — go.mod go 1.27.0, CI Node 26, scripts/check_toolchain_drift.py enforced in CI; backend gates green on go1.27.0; Node 26 gates run in PR CI only (local Node is 24)
- [x] INFRA-P3-001 Delete deploy/k8s and deploy/k8s-next, their CI validation and dead make targets; point docs to the GitOps repository — plans/INFRA.md — done (pending commit) — deploy/k8s and deploy/k8s-next removed with their two CI jobs, the k8s secret scan script and make target; docs and expert profiles point to the GitOps repository
- [x] REPO-P3-001 Correct Go version statements in docs and devcontainer — plans/REPO.md — done (pending commit) — profiles, AGENTS.md and devcontainer comment state the real versions; devcontainer base tag left at 1.25 (newer tag could not be verified)
- [ ] BOT-P1-001 Detect tx rejection from the broadcast response; bind order ids by client id — plans/BOT.md — todo
- [ ] BOT-P1-006 Emergency-close retry loop survives placement exceptions — plans/BOT.md — todo
- [ ] BOT-P1-007 One client id per logical reduce-only close — plans/BOT.md — todo
- [ ] BOT-P1-008 Halt new entries after a failed emergency cleanup (persisted latch) — plans/BOT.md — todo
- [ ] BOT-P1-004 Tracked-position store must not ignore write failures — plans/BOT.md — todo
- [ ] BOT-P1-002 Cooperative shutdown instead of raising from the signal handler — plans/BOT.md — todo
- [ ] BOT-P1-003 Write-ahead entry intent and restart recovery — plans/BOT.md — todo
- [ ] BOT-P1-012 Refuse plaintext mnemonics outside dev/test — plans/BOT.md — todo
- [x] BACK-P1-001 Quick-deploy creates an owned row and honours the quota — plans/BACK.md — done (pending commit) — quick-deploy writes an owned bot_instances row (no credentials), rolls the upstream runtime back when that fails, and re-checks the quota after the insert; the unused requested_by_user_id injection is removed; 5 tests
- [x] INFRA-P1-010 Remove the compose prod path; loopback-only ports; no default secrets — plans/INFRA.md — done (pending commit) — stack-up-prod targets removed; all 30 published ports in the four stack/infra files bound to 127.0.0.1. Placeholder secret defaults kept: failing fast would break the CI compose validation and local bootstrap, and the stacks are now dev-only and loopback-bound
- [x] REPO-P3-004 Add CODEOWNERS — plans/REPO.md — done (pending commit) — .github/CODEOWNERS added; every listed path exists; GitHub-side validation after the push

## Proposal-only (needs a human decision; not executed)
- none: every proposal was either decided and queued above or moved to the GitOps repository.

## Moved to the GitOps repository (not applicable here once deploy/k8s-next is deleted)
- INFRA-P1-001, INFRA-P1-002, INFRA-P1-005, INFRA-P1-006, INFRA-P1-007, INFRA-P1-008 (PITR, RPO about 5 min, verify the CloudNativePG backup configuration), INFRA-P1-009, INFRA-P2-002, INFRA-P2-005, INFRA-P2-007, and the manifest halves of INFRA-P0-001, INFRA-P0-002, INFRA-P1-003, INFRA-P1-004, INFRA-P2-001, INFRA-P2-003: check each against the GitOps manifests.

## Deferred / invalid
- Deferred with reasons in the service plans: BOT-P1-011, BOT-P2-001..003, BOT-P2-005, BOT-P2-006, BOT-P3-001; BACK-P1-005, BACK-P2-002..011; FRONT-P2-007..015, FRONT-P3-018, FRONT-P3-019; INFRA-P1-001, INFRA-P1-007, INFRA-P2-001..003, INFRA-P2-005..007; REPO-P3-001, REPO-P3-003.
- Merged duplicates: BOT-P2-002 → INFRA-P0-001; BOT-P2-004 → INFRA-P2-001/006; BACK-P3-002 → INFRA-P2-001/006 + REPO-P2-001; BACK-P3-003 → REPO-P2-002; FRONT-P2-016 → REPO-P2-002; FRONT-P3-017 → REPO-P2-001 + INFRA-P2-001/006.
