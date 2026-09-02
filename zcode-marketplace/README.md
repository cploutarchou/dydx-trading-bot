# zcode-marketplace — local ZCode marketplace

Repository-local marketplace providing the `monorepo-experts` plugin:
service reference profiles, 10 skills, 9 specialist subagents, and 8 slash
commands for this monorepo. Structure follows the current ZCode plugin spec
(`.zcode-plugin/plugin.json` + `commands/` + `skills/` + `agents/`;
`references/` holds plain profile documents that agents read from this
repository-relative path).

## Install (one time)

1. Open ZCode **Settings → Plugins**.
2. Click **Create → Add marketplace** (top right).
3. Enter this directory's absolute path on your machine
   (`<repo-root>/zcode-marketplace`) — the path must exist; drag-and-drop or
   "Choose directory" also work.
4. Find `dydx-monorepo-local` under the **Personal** segment, select the
   `monorepo-experts` plugin, click **Install**, and keep it enabled
   (newly installed plugins are enabled by default).
5. **Start a new ZCode session** — subagents and commands load per session.

After editing plugin files, refresh the marketplace from the
**Marketplace sources** panel (gear icon above the search box), and bump the
version in `plugins/monorepo-experts/.zcode-plugin/plugin.json` and in
`marketplace.json` (updates are only offered when the version increases).

## Quick use

- `/monorepo-check` — run every canonical validation gate.
- `/service-check bot` — validate one service against its profile.
- `/security-review backend` — threat-focused review of a scope.

See the root `AGENTS.md` routing table for the full service→skill→agent map.
