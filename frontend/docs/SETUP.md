# Setup Guide - Development & Production

Choose your setup path below:

## 🚀 Quick Start (Recommended: DevContainer)

**For development using DevContainer (one-click setup):**

1. Open in VS Code:

   ```bash
   code frontend/
   ```

2. Click the "Reopen in Container" popup
   (Or: `Ctrl+Shift+P` → "Dev Containers: Reopen in Container")

3. Start development:

   ```bash
   npm run dev
   ```

4. Visit <http://localhost:5173>

**That's it!** SSH keys and Git config are automatically mounted.

For more details: [docs/devcontainer/QUICKSTART.md](devcontainer/QUICKSTART.md)

---

## 💻 Local Development (Without DevContainer)

### Prerequisites

- Node.js 20+
- npm or yarn
- Docker (optional, for backend services)

### Setup

```bash
# Install dependencies
npm install

# Create environment file
cp .env.local.example .env.local

# Start development server
npm run dev
```

Visit <http://localhost:5173>

### Optional: Start Backend Services

```bash
docker-compose up -d    # Start PostgreSQL + Redis + Backend
docker-compose logs -f  # View logs
```

---

## 🐳 Production Build

### Build

```bash
npm run build
```

Output in `dist/` directory (ready for deployment)

### Test Production Build Locally

```bash
npm run preview
```

Visit <http://localhost:4173>

### Run in Docker

```bash
# Build image
docker build -t dydx-frontend .

# Run container
docker run -p 3000:3000 dydx-frontend
```

Visit <http://localhost:3000>

### Environment Variables for Production

Create `.env.production` or set environment variables:

```bash
VITE_API_URL=https://api.example.com
```

---

## 🔧 Available Commands

### Development

```bash
npm run dev         # Start dev server (HMR enabled)
npm run build       # Build for production
npm run lint        # Check code quality
npm run preview     # Preview production build
```

### Docker Compose (Backend Services)

```bash
docker-compose up -d        # Start all services
docker-compose up -d db redis  # Start only database services
docker-compose logs -f backend  # View backend logs
docker-compose down         # Stop all services
docker-compose ps           # List running services
```

---

## 📦 Environment Variables

### Development (.env.local)

```bash
VITE_API_URL=http://localhost:8888
NODE_ENV=development
```

### Production (.env.production)

```bash
VITE_API_URL=https://api.example.com
NODE_ENV=production
```

See [../.env.local.example](.env.local.example) for all available options.

---

## 🔐 SSH & Git Setup

### In DevContainer (Automatic ✅)

- SSH keys from `~/.ssh` automatically mounted
- Git config from `~/.gitconfig` automatically mounted
- All git operations use your identity
- **No setup needed!**

### Local Development (Manual Setup)

1. Ensure SSH keys are in `~/.ssh/`
2. Configure git locally:

   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "your.email@example.com"
   ```

---

## 🐳 Docker Services

### Starting Services

```bash
docker-compose up -d
```

### Available Services

| Service | Port | URL |
|---------|------|-----|
| Frontend (Vite) | 5173 | <http://localhost:5173> |
| Backend API | 8888 | <http://localhost:8888> |
| PostgreSQL | 5432 | postgresql://postgres:postgres@localhost:5432/dydx_trading |
| Redis | 6379 | redis://localhost:6379 |

### View Logs

```bash
docker-compose logs -f              # All services
docker-compose logs -f backend      # Specific service
docker-compose logs -f --tail=100   # Last 100 lines
```

### Stop Services

```bash
docker-compose down
```

---

## 🆘 Troubleshooting

### Port Already in Use

```bash
# Option 1: Stop conflicting service
docker-compose down

# Option 2: Use different port in devcontainer.json
"forwardPorts": [5174, 3000, 8888, 5432, 6379]
```

### npm Dependencies Not Installing

```bash
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

### DevContainer Build Issues

```bash
# Rebuild container from scratch
Ctrl+Shift+P → "Dev Containers: Rebuild Container"

# Or remove and restart
Ctrl+Shift+P → "Dev Containers: Remove Container"
```

### SSH Keys Not Working in DevContainer

```bash
# Check SSH keys are mounted
ls -la ~/.ssh

# Test connection
ssh -T git@github.com
```

For more troubleshooting: [../guides/TROUBLESHOOTING.md](../guides/TROUBLESHOOTING.md)

---

## 🎯 Next Steps

- **New to DevContainer?** → [devcontainer/QUICKSTART.md](devcontainer/QUICKSTART.md)
- **Want to understand the setup?** → [devcontainer/README.md](devcontainer/README.md)
- **Need architecture info?** → [../architecture/](../architecture/)
- **Having issues?** → [../guides/TROUBLESHOOTING.md](../guides/TROUBLESHOOTING.md)

---

## 📚 Additional Resources

- [DevContainer Setup](devcontainer/README.md)
- [Architecture Guide](../architecture/)
- [Troubleshooting Guide](../guides/TROUBLESHOOTING.md)
- [Codebase Instructions](../../.github/copilot-instructions.md)
