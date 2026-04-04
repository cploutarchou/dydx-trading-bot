# Frontend Documentation

This is the main entry point for frontend docs. Use it to find the right guide quickly and follow the docs in a clear order.

## Start here

1. [SETUP.md](SETUP.md) — local setup, build, preview, and shared service commands
2. [guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md) — common local environment and runtime issues
3. [architecture/README.md](architecture/README.md) — architecture map and deeper technical references
4. [../.github/copilot-instructions.md](../.github/copilot-instructions.md) — project conventions and implementation patterns

## Recommended reading order

| If you want to...                     | Read this                                                                            |
| ------------------------------------- | ------------------------------------------------------------------------------------ |
| run the frontend locally              | [SETUP.md](SETUP.md)                                                                 |
| connect to backend and infra services | [SETUP.md](SETUP.md)                                                                 |
| debug a broken local setup            | [guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md)                               |
| understand data flow and UI structure | [architecture/README.md](architecture/README.md)                                     |
| capture responsive screenshots        | [guides/RESPONSIVE_SCREENSHOT_PLAYBOOK.md](guides/RESPONSIVE_SCREENSHOT_PLAYBOOK.md) |

## Docs map

### Core docs

| Document                                               | Purpose                                                     |
| ------------------------------------------------------ | ----------------------------------------------------------- |
| [SETUP.md](SETUP.md)                                   | Supported local workflow on macOS/Linux                     |
| [guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md) | Fix common environment, dependency, and service issues      |
| [architecture/README.md](architecture/README.md)       | Architecture index for flows, patterns, and API integration |

### QA and operational docs

| Document                                                                             | Purpose                      |
| ------------------------------------------------------------------------------------ | ---------------------------- |
| [guides/RESPONSIVE_SCREENSHOT_PLAYBOOK.md](guides/RESPONSIVE_SCREENSHOT_PLAYBOOK.md) | Screenshot capture workflow  |
| [RESPONSIVE_SCREENSHOT_CHECKLIST.md](RESPONSIVE_SCREENSHOT_CHECKLIST.md)             | Expected screenshot outputs  |
| [RESPONSIVE_SCREENSHOT_SIGNOFF.md](RESPONSIVE_SCREENSHOT_SIGNOFF.md)                 | Review sign-off checklist    |
| [RESPONSIVE_QA_STATUS.md](RESPONSIVE_QA_STATUS.md)                                   | Current responsive QA status |

### Summary docs

| Document                                       | Purpose                                       |
| ---------------------------------------------- | --------------------------------------------- |
| [INDEX.md](INDEX.md)                           | Short navigation summary                      |
| [COMPLETION_SUMMARY.md](COMPLETION_SUMMARY.md) | Maintenance note about the current docs shape |

## Quick reference

### Frontend commands

```bash
npm run dev
npm run build
npm run lint
npm run qa:screenshots:plan
npm run qa:screenshots:capture
npm run qa:screenshots:sync
```

### Repo-root integration commands

```bash
make stack-env
make infra-up
make stack-up-dev
make infra-down
make stack-down
```

### Shared ports

| Port | Service                               |
| ---- | ------------------------------------- |
| 5173 | Frontend dev server                   |
| 3000 | Frontend production preview/container |
| 8888 | Go backend                            |
| 8889 | Bot API                               |
| 5432 | PostgreSQL                            |
| 6379 | Redis                                 |

## Directory layout

```text
docs/
├── README.md
├── INDEX.md
├── SETUP.md
├── COMPLETION_SUMMARY.md
├── RESPONSIVE_QA_STATUS.md
├── RESPONSIVE_SCREENSHOT_CHECKLIST.md
├── RESPONSIVE_SCREENSHOT_SIGNOFF.md
├── architecture/
└── guides/
```

## Need help?

If you are not sure where to start, read [SETUP.md](SETUP.md) first and then use [guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md) when something misbehaves.
