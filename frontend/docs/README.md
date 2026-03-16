# Documentation Index

All project documentation organized in one place.

## Quick Links

| Purpose                        | Link                                                             | Time   |
| ------------------------------ | ---------------------------------------------------------------- | ------ |
| **Backend API Integration**    | [BACKEND_API_INTEGRATION.md](./BACKEND_API_INTEGRATION.md)       | 10 min |
| **Frontend Development Guide** | [FRONTEND_DEVELOPMENT_GUIDE.md](./FRONTEND_DEVELOPMENT_GUIDE.md) | 15 min |
| **API Coverage Checklist**     | [API_COVERAGE_CHECKLIST.md](./API_COVERAGE_CHECKLIST.md)         | 5 min  |
| **Integration Summary**        | [INTEGRATION_SUMMARY.md](./INTEGRATION_SUMMARY.md)               | 5 min  |
| **React Component Examples**   | [REACT_COMPONENT_EXAMPLES.tsx](./REACT_COMPONENT_EXAMPLES.tsx)   | 20 min |
| **Setup**                      | [SETUP.md](SETUP.md)                                             | 5 min  |
| **DevContainer quick start**   | [devcontainer/QUICKSTART.md](devcontainer/QUICKSTART.md)         | 2 min  |
| **Troubleshooting**            | [guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md)           | varies |

## Directory Structure

```
docs/
├── SETUP.md                 # Setup guide for dev & prod
├── README.md               # This file
├── devcontainer/           # DevContainer documentation
│   ├── QUICKSTART.md      # 30-second setup
│   └── README.md          # Full guide
├── architecture/           # Architecture & design
│   └── (coming)
└── guides/                 # Detailed guides
    ├── TROUBLESHOOTING.md # Common issues
    └── (coming)
```

## Getting Started

### First Time?

1. **Quick start:** [SETUP.md](SETUP.md) - Choose your path
2. **DevContainer user?** → [devcontainer/QUICKSTART.md](devcontainer/QUICKSTART.md)
3. **Having issues?** → [guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md)

### Development

- **Start dev server:** `npm run dev`
- **Build for production:** `npm run build`
- **Start backend services:** `docker-compose up -d`

### Common Tasks

| Task                           | Link                                                                     |
| ------------------------------ | ------------------------------------------------------------------------ |
| Set up development environment | [SETUP.md](SETUP.md)                                                     |
| Use DevContainer               | [devcontainer/QUICKSTART.md](devcontainer/QUICKSTART.md)                 |
| Deploy to production           | [SETUP.md](SETUP.md#-production-build)                                   |
| Start backend services         | [SETUP.md](SETUP.md#-docker-services)                                    |
| Fix a problem                  | [guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md)                   |
| Understand architecture        | [architecture/](architecture/)                                           |
| Learn code patterns            | [../.github/copilot-instructions.md](../.github/copilot-instructions.md) |

## Documentation Files

### SETUP.md

**What:** Complete setup guide for development and production

**Read when:**

- You're setting up for the first time
- You want to deploy to production
- You need to configure environment variables

**Contents:**

- Quick start (DevContainer)
- Local development setup
- Production build & deployment
- Docker services configuration
- Troubleshooting links

### devcontainer/QUICKSTART.md

**What:** 30-second DevContainer setup

**Read when:**

- You want the fastest possible setup
- Using DevContainer for development
- You're in a hurry

**Contents:**

- 3 steps to get running
- Command reference
- SSH/Git setup (automatic!)

### devcontainer/README.md

**What:** Complete DevContainer guide

**Read when:**

- You want to understand DevContainer
- You need detailed configuration info
- You want to customize the setup

**Contents:**

- Prerequisites
- Setup process
- What's included
- Commands reference
- Troubleshooting
- Pro tips

### guides/TROUBLESHOOTING.md

**What:** Solutions to common problems

**Read when:**

- Something isn't working
- You get an error message
- You need to debug an issue

**Contents:**

- DevContainer issues
- npm & dependencies
- Docker & services
- Development server
- Build & production
- Environment configuration
- Other issues

### architecture/

**What:** System design and architecture (coming soon)

**Read when:**

- You want to understand the overall design
- You're making large structural changes
- You want to learn about the project structure

### .github/copilot-instructions.md

**What:** Code patterns and conventions for this project

**Read when:**

- You're writing code
- You want to follow project conventions
- You want to understand design patterns

---

## Quick Reference

### Commands

**Development:**

```bash
npm run dev         # Start dev server
npm run build       # Production build
npm run lint        # Check code quality
npm run lint -- --fix  # Auto-fix issues
```

**Docker:**

```bash
docker-compose up -d        # Start services
docker-compose logs -f      # View logs
docker-compose down         # Stop services
```

### Environment Variables

Create `.env.local`:

```bash
VITE_API_URL=http://localhost:8889
```

### Ports

| Port | Service                 |
| ---- | ----------------------- |
| 5173 | Dev server              |
| 3000 | Production server       |
| 8889 | Bot API (default)       |
| 8888 | Go Backend API (legacy) |
| 5432 | PostgreSQL              |
| 6379 | Redis                   |

## Need Help?

1. **Check documentation** - Most answers are in the docs
2. **Search troubleshooting** - Common issues are documented
3. **Check code patterns** - See `.github/copilot-instructions.md`
4. **Ask the team** - We're happy to help!

---

**Start with:** [SETUP.md](SETUP.md) or [devcontainer/QUICKSTART.md](devcontainer/QUICKSTART.md)
