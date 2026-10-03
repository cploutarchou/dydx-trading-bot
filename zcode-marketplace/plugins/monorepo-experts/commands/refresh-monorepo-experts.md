---
description: Re-inspect the repository and update the monorepo-experts profiles, routing, skills, and agents after structural changes
skills: monorepo-architecture
---

Refresh the monorepo-experts system after the repository's structure,
commands, services, or boundaries changed.

Procedure:
1. Re-run repository discovery: workspace configs, entry points, services,
   validation commands (Makefiles, pyproject/go.mod/package.json, CI
   workflows), and the security-sensitive boundaries listed in
   monorepo-map.md.
2. Diff the findings against each profile under
   zcode-marketplace/plugins/monorepo-experts/references/ and update ONLY
   the drifted, evidence-backed facts (paths, commands, ports, owners).
3. Update the routing table in monorepo-map.md (and root AGENTS.md's
   service-routing table) if services were added/removed/renamed. New
   services must get a profile, a routing entry, skill coverage, and an
   assigned specialist agent.
4. Keep human-maintained rules intact: never delete or rewrite prose rules,
   safety sections, or conventions — merge facts, preserve intent. Report
   any conflict instead of silently overwriting.
5. Do not modify application source, dependencies, lockfiles, or CI config.
6. Bump the plugin version in
   zcode-marketplace/plugins/monorepo-experts/.zcode-plugin/plugin.json and
   the marketplace entry version in zcode-marketplace/marketplace.json
   (updates are only offered when the version bumps).

Finish with: what changed in each file, discovery evidence for each update,
conflicts found, and a reminder that a new ZCode session is needed for
agent/command changes to load.
