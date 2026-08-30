---
description: Implement a change in one service (bot | backend | frontend | platform | data | ci) following its profile, safety rules, and verification gates
argument-hint: "<service> <request>"
skills: monorepo-architecture
---

Implement the following request in the service "$1": $2

Procedure:
1. Read the service's profile under
   zcode-marketplace/plugins/monorepo-experts/references/ and follow its
   rules (safety boundaries, generated files, conventions).
2. If the request crosses a service boundary (contract change, config flow,
   shared schema), stop and use the monorepo-architecture routing instead —
   contract changes need lockstep updates across bot openapi, backend
   routes, and the frontend client.
3. Dispatch the implementation to the matching specialist agent if available
   (bot-trading-expert / backend-go-expert / frontend-react-expert).
4. Smallest complete change; focused tests including failure paths; no
   unrelated refactoring; never weaken tests or gates.
5. Verify with the profile's canonical commands and quote exact results.

Finish with: files changed, behavior delta, verification evidence, and any
remaining uncertainty.
