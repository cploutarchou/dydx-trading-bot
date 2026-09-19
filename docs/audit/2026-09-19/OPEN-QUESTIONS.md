# Open questions — 2026-09-19

- [BOT-P0-002] Is self-registration on the bot API (`/auth/register`) intended to exist at all, given the Go gateway owns user management? Which role may create/start/stop/delete bot instances? Blocks: the authorization fix in plans/BOT.md.
- [INFRA-P0-001] For the single-writer guarantee per trading instance, is a Postgres advisory lock acceptable, or is a lease row with a fencing token required (multi-node failover)? Blocks: the lock proposal.
- [REPO-P2-001] Which Go and Node versions are the supported ones: what CI tests (Go 1.25 / Node 24) or what the images build with (Go 1.27 / Node 26)? Blocks: REPO-P2-001, REPO-P3-001.
- [REPO-P2-003] May `quality-gate` become a required status check on `master`, and may image publishing wait for it? Blocks: REPO-P2-003.
- [BACK-P1-003] Has migration 000070 already been applied to any real database? Which environments run with `DB_AUTO_MIGRATE=true`? Blocks: BACK-P1-003, BACK-P1-004.
- [BACK-P1-005] What sits in front of the backend in production (ingress controller, proxy CIDRs)? Blocks: trusted-proxy and rate-limit fix.
- [INFRA-P1-005] Is `deploy/k8s-next` deployed anywhere today, and with which tool (kubectl, Flux, Argo)? Is `deploy/k8s` (MariaDB) retired? Blocks: INFRA-P1-005, INFRA-P1-006, INFRA-P3-001.
- [INFRA-P1-008] What RPO/RTO is required for the Postgres databases? Blocks: backup design.
- [INFRA-P1-009] Which hostnames and certificate issuer should the ingresses use? Blocks: TLS fix.
- [BOT-P1-009] How is realised P&L defined for a pair trade (fees, funding payments, rounding)? Blocks: BOT-P1-009.
- [FRONT-P1-006] Should the manual runtime form default to testnet? Blocks: FRONT-P1-006.
- [BOT-P1-011] Is the pinned signing SDK version affected by the reported advisory, and is an upgrade acceptable? Blocks: BOT-P1-011.
