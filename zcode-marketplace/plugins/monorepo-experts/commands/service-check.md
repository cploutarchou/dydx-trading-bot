---
description: Validate one service end-to-end (bot | backend | frontend | platform | data | ci) against its reference profile
argument-hint: "<service>"
skills: monorepo-architecture
---

Validate the service named "$1" end-to-end.

Steps:
1. Read the matching profile under
   zcode-marketplace/plugins/monorepo-experts/references/
   (bot-service.md / backend-service.md / frontend-service.md /
   platform-infra.md / data-migrations.md / ci-release.md).
2. Verify the service's stated entry points and boundaries still match the
   code (spot-check; report drift).
3. Run that profile's validation commands and quote exact results.
4. Report: checks run, pass/fail per command, drift found between profile
   and code, and recommended profile updates (do not apply them here —
   that is /refresh-monorepo-experts).

If "$1" is missing or matches no service, list the valid service names from
the routing table and stop.
