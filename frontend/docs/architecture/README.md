# Frontend Architecture Notes

This page is the compact architectural companion to the canonical [frontend README](/home/chris/workspace/dydx-trading-bot/frontend/README.md).

## Core Rule

The frontend communicates with the Go backend only.

All HTTP and websocket origin helpers must resolve to the backend origin, not the bot origin.

## Current Architecture

```text
React app
  -> API client / websocket helpers
  -> backend HTTP + websocket routes
  -> backend delegates to bot and persistence layers
```

## Main Building Blocks

- `src/pages` for product routes
- `src/components` for reusable product UI
- `src/api` for HTTP, origin, websocket, and hook integration
- `src/store` for local state
- `src/navigation` for workspace shell navigation

## Live Data Pattern

The preferred live pattern is:

1. bootstrap with HTTP
2. stream updates over websocket
3. recover with silent HTTP resync only when needed

That pattern now powers backtests, runtime views, and live operator surfaces.

## Design Direction

The UI bar is production DeFi:

- responsive on mobile, tablet, and desktop
- dense where operators need signal
- marketing surfaces without oversized boxed layouts
- websocket-first live views
- modern charting and terminal-style data grids

## Additional References

- [Fintech UI Standards](FINTECH_UI_STANDARDS.md)
- [Troubleshooting](/home/chris/workspace/dydx-trading-bot/frontend/docs/guides/TROUBLESHOOTING.md)
- [Platform Wiki Home](/home/chris/workspace/dydx-trading-bot/docs/README.md)
