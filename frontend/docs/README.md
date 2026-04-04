# Documentation Index

Frontend documentation organized around the current local workflow.

## Quick Links

| Purpose                        | Link                                                                                 | Time   |
| ------------------------------ | ------------------------------------------------------------------------------------ | ------ |
| Setup                          | [SETUP.md](SETUP.md)                                                                 | 5 min  |
| Troubleshooting                | [guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md)                               | varies |
| Architecture overview          | [architecture/README.md](architecture/README.md)                                     | 10 min |
| Responsive screenshot playbook | [guides/RESPONSIVE_SCREENSHOT_PLAYBOOK.md](guides/RESPONSIVE_SCREENSHOT_PLAYBOOK.md) | 5 min  |
| Screenshot checklist           | [RESPONSIVE_SCREENSHOT_CHECKLIST.md](RESPONSIVE_SCREENSHOT_CHECKLIST.md)             | 3 min  |
| Responsive QA status           | [RESPONSIVE_QA_STATUS.md](RESPONSIVE_QA_STATUS.md)                                   | 5 min  |

## Directory Structure

```text
docs/
├── README.md                         # This file
├── SETUP.md                          # Local dev + production setup
├── RESPONSIVE_QA_STATUS.md           # Breakpoint QA matrix
├── RESPONSIVE_SCREENSHOT_CHECKLIST.md # Expected evidence filenames
├── RESPONSIVE_SCREENSHOT_SIGNOFF.md  # Reviewer sign-off checklist
├── architecture/                     # Architecture & design docs
└── guides/                           # Troubleshooting and workflows
```

## Getting Started

1. Read [SETUP.md](SETUP.md) for the supported local setup.
2. Start frontend dev with `npm install` then `npm run dev`.
3. For integration services, use the repo-root commands: `make stack-env` and `make infra-up`.
4. If something breaks, use [guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md).

## Common Tasks

| Task                           | Link                                                                                 |
| ------------------------------ | ------------------------------------------------------------------------------------ |
| Set up development environment | [SETUP.md](SETUP.md)                                                                 |
| Fix a problem                  | [guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md)                               |
| Understand architecture        | [architecture/README.md](architecture/README.md)                                     |
| Learn project patterns         | [../.github/copilot-instructions.md](../.github/copilot-instructions.md)             |
| Capture responsive screenshots | [guides/RESPONSIVE_SCREENSHOT_PLAYBOOK.md](guides/RESPONSIVE_SCREENSHOT_PLAYBOOK.md) |
| Verify screenshot filenames    | [RESPONSIVE_SCREENSHOT_CHECKLIST.md](RESPONSIVE_SCREENSHOT_CHECKLIST.md)             |

## Quick Reference

### Commands

```bash
npm run dev
npm run build
npm run lint
npm run qa:screenshots:plan
npm run qa:screenshots:capture
npm run qa:screenshots:sync
```

Integration services from the repo root:

```bash
make stack-env
make infra-up
make stack-up-dev
make infra-down
make stack-down
```

### Environment Variables

Use the repo-root `.env`:

```bash
VITE_API_URL=http://localhost:8888
```

### Ports

| Port | Service              |
| ---- | -------------------- |
| 5173 | Frontend dev server  |
| 3000 | Production container |
| 8888 | Go backend           |
| 8889 | Bot API              |
| 5432 | PostgreSQL           |
| 6379 | Redis                |

## Need Help?

Start with [SETUP.md](SETUP.md), then fall back to [guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md) if needed.
