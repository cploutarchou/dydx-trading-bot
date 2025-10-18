# DevContainer Complete Guide

Full documentation for the DevContainer setup.

## Quick Links

- **Quick Start:** [QUICKSTART.md](QUICKSTART.md) - 30 seconds to get going!
- **Troubleshooting:** [../guides/TROUBLESHOOTING.md](../guides/TROUBLESHOOTING.md)
- **Setup Guide:** [../SETUP.md](../SETUP.md)

## What is DevContainer?

DevContainer provides a complete, isolated development environment using Docker. This ensures:

- ✅ Consistency - All developers work in identical environment
- ✅ Simplicity - One-click setup in VS Code
- ✅ No system pollution - Everything isolated in Docker
- ✅ Easy onboarding - New team members setup in minutes

## Prerequisites

### Required

- **Docker Desktop** (macOS/Windows) or Docker + Docker Compose (Linux)
  - [Download Docker Desktop](https://www.docker.com/products/docker-desktop)

- **Visual Studio Code**
  - [Download VS Code](https://code.visualstudio.com/)
  - Install: **Remote - Containers** extension (ms-vscode-remote.remote-containers)

### Optional

- SSH keys in `~/.ssh/` (for GitHub/GitLab)
- Git configured on your machine

## Setup

### 1. Open in VS Code

```bash
code frontend/
```

### 2. Reopen in Container

- Click "Reopen in Container" popup, or
- `Ctrl+Shift+P` → "Dev Containers: Reopen in Container"

### 3. Wait for Build

- First build: 2-5 minutes
- Subsequent: <10 seconds
- Extensions and dependencies auto-install

### 4. Start Development

```bash
npm run dev
```

Visit <http://localhost:5173>

## What's Included

### Software

- Node.js 20
- npm, yarn, pnpm
- TypeScript, tsx, ts-node
- Docker CLI & Docker Compose

### VSCode Extensions (15+)

- ESLint + Prettier (formatting)
- TypeScript support
- Tailwind CSS IntelliSense
- React snippets
- Docker integration
- GitLens & GitHub Copilot
- And 8+ more tools

### Pre-configured

- Editor settings & formatters
- ESLint rules
- Prettier configuration
- TypeScript strict mode
- All environment variables

## SSH & Git

✅ **Automatic Setup:**

Your `~/.ssh` and `~/.gitconfig` are automatically mounted (read-only).

```bash
# Git commits use your identity
git add .
git commit -m "feat: description"
git push origin main
```

No additional setup needed!

## Commands

### Development

```bash
npm run dev         # Dev server (HMR enabled)
npm run build       # Production build
npm run lint        # Code quality check
npm run lint -- --fix  # Auto-fix issues
```

### Docker

```bash
docker-compose up -d    # Start backend services
docker-compose logs -f  # View logs
docker-compose down     # Stop services
```

## Troubleshooting

### Container won't build

```bash
Ctrl+Shift+P → "Dev Containers: Rebuild Container"
```

### Port conflicts

```bash
docker-compose down
# Or change port in .devcontainer/devcontainer.json
```

### SSH not working

```bash
# Inside container:
ls -la ~/.ssh
ssh -T git@github.com
```

### Dependencies not installing

```bash
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

For more issues: [../guides/TROUBLESHOOTING.md](../guides/TROUBLESHOOTING.md)

## Performance

| Metric | Time |
|--------|------|
| First build | 2-5 min |
| Container startup | <10 sec |
| Dev server start | <5 sec |
| HMR reload | <1 sec |

## Docker Services

Included in `docker-compose.yml`:

| Service | Port | Purpose |
|---------|------|---------|
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache |
| Backend API | 8000 | REST API |
| Frontend | 5173 | Dev server |

Start them:

```bash
docker-compose up -d
```

## Additional Resources

- [VS Code DevContainers Docs](https://code.visualstudio.com/docs/devcontainers/containers)
- [Docker Docs](https://docs.docker.com/)
- [Quick Start Guide](QUICKSTART.md)
- [Setup Guide](../SETUP.md)
- [Troubleshooting](../guides/TROUBLESHOOTING.md)

---

**Ready?** Start with [QUICKSTART.md](QUICKSTART.md)
