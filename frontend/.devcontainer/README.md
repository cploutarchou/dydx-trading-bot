# dYdX Trading Bot Frontend - DevContainer Setup Guide

This project is configured with a complete development environment using Docker DevContainers. This ensures consistency across all development machines and simplifies onboarding.

## 📋 Prerequisites

### Required

- **Docker Desktop** (or Docker + Docker Compose on Linux)
  - [Download Docker Desktop](https://www.docker.com/products/docker-desktop)
  - Ensure Docker daemon is running

- **Visual Studio Code**
  - [Download VS Code](https://code.visualstudio.com/)
  - Install extension: **Remote - Containers** (ms-vscode-remote.remote-containers)

### Optional

- **SSH keys** for GitHub/GitLab
  - Located at `~/.ssh/` - will be automatically mounted
  - Ensures you can commit with your identity

## 🚀 Quick Start

### Step 1: Open in DevContainer

1. Clone the repository
2. Open the folder in VS Code: `code frontend/`
3. VS Code will detect the `.devcontainer` folder
4. Click the notification popup: **"Reopen in Container"** or use command palette:
   - Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
   - Type: "Dev Containers: Reopen in Container"
   - Press Enter

### Step 2: Wait for Container to Build

- First build takes 2-5 minutes
- VS Code shows progress in the bottom left
- You'll see terminal output with setup steps

### Step 3: Start Development

```bash
npm run dev
```

- Dev server starts on `http://localhost:5173`
- Backend API available at `http://localhost:8000` (if running locally)
- HMR (Hot Module Reload) enabled - changes auto-refresh

## 🐳 Docker Services (Optional Local Development)

To run backend services locally inside Docker:

```bash
# Start all services (backend, PostgreSQL, Redis)
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop services
docker-compose down
```

### Available Services

| Service | Port | URL |
|---------|------|-----|
| Frontend (Vite) | 5173 | <http://localhost:5173> |
| Backend API | 8000 | <http://localhost:8000> |
| PostgreSQL | 5432 | postgresql://postgres:postgres@localhost:5432/dydx_trading |
| Redis | 6379 | redis://localhost:6379 |

## 🔧 Available Commands Inside Container

```bash
# Development
npm run dev           # Start development server with HMR
npm run build         # Build for production
npm run preview       # Preview production build

# Code Quality
npm run lint          # Run ESLint

# Utilities
docker ps             # View running containers
docker logs <container> # View container logs
docker-compose ps     # View docker-compose services
```

## 🔐 SSH Keys & Git Configuration

### SSH Keys

- Your `~/.ssh` directory is **automatically mounted** as read-only
- SSH keys work for GitHub/GitLab operations
- Permissions are preserved inside container

### Git Configuration

- Your `~/.gitconfig` is **automatically mounted** as read-only
- Git commits use your identity
- GPG signing configured if you have GPG keys

## 📁 Project Structure

```
.devcontainer/
├── devcontainer.json    # Main DevContainer config
├── Dockerfile           # Container image definition
├── setup.sh            # Setup script (auto-runs on container creation)
└── README.md           # This file

docker-compose.yml      # Multi-service orchestration
src/                    # React source code
  ├── components/       # Reusable UI components
  ├── pages/           # Route-level components
  ├── store/           # Zustand state management
  └── api.ts           # API client
package.json           # Dependencies & scripts
tailwind.config.js     # Tailwind CSS config
vite.config.ts         # Vite bundler config
```

## 🎯 VSCode Extensions Inside Container

The following extensions are automatically installed:

| Extension | Purpose |
|-----------|---------|
| **ESLint** | Code quality and error detection |
| **Prettier** | Code formatting |
| **TypeScript Vue Plugin** | TypeScript support |
| **Tailwind CSS IntelliSense** | Tailwind class autocomplete |
| **ES7+ React/Redux Snippets** | React code snippets |
| **SQLTools** | Database client (for PostgreSQL/Redis) |
| **GitHub Copilot** | AI-powered code assistance |
| **GitLens** | Git history and blame |
| **Vscode Icons** | File icons |
| **Docker** | Docker integration |
| **Git Graph** | Visual git history |

## 🌍 Environment Variables

### Inside DevContainer

```bash
# Automatically set
VITE_API_URL=http://localhost:8000
```

### Create `.env.local` for additional variables

```bash
# The setup script creates this automatically
cp .env.local.example .env.local
```

## 🐛 Troubleshooting

### DevContainer fails to start

```bash
# Rebuild container from scratch
# In VS Code: Ctrl+Shift+P > "Dev Containers: Rebuild Container"
# Or delete and restart
```

### Port already in use

- Change port in `devcontainer.json` `forwardPorts` array
- Or stop other containers: `docker-compose down`

### Git operations fail inside container

- Verify SSH keys mounted: `ls -la ~/.ssh` inside container
- Check permissions: `ssh -T git@github.com`

### npm packages not installing

```bash
# Clear npm cache inside container
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

### Docker can't access backend services

- Ensure `docker-compose up` was run
- Check network: `docker network ls | grep dydx`
- Verify services: `docker-compose ps`

## 📚 Additional Resources

- [VS Code DevContainers Documentation](https://code.visualstudio.com/docs/devcontainers/containers)
- [Docker Documentation](https://docs.docker.com/)
- [React Documentation](https://react.dev)
- [TypeScript Documentation](https://www.typescriptlang.org/docs/)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)

## 💡 Pro Tips

1. **Use `.gitignore` for sensitive files** - DevContainer has no access to files listed there

2. **Port forwarding automatic** - VS Code handles it, just use localhost URLs

3. **Hot Reload** - Changes to source files auto-refresh browser

4. **Debug mode** - Add `debugger;` to code and use DevTools

5. **Terminal inside VS Code** - Open integrated terminal with `` Ctrl+` ``

## 🤝 Contributing

When contributing to this project:

1. Always develop inside the DevContainer
2. Run linter before committing: `npm run lint`
3. Follow the established code patterns in `src/`
4. Update `.github/copilot-instructions.md` if adding major features

## 📝 Notes

- DevContainer uses the same SSH keys as your host machine
- All Docker operations work normally inside the container
- Network access to external services works seamlessly
- Volume mounts ensure hot reload on file changes
