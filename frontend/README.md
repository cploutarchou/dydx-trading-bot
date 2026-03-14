# dYdX Trading Bot Frontend

React/TypeScript frontend for the dYdX pairs trading backtest system.

## 🚀 Quick Start

### Development

```bash
# Open in DevContainer (recommended)
code frontend/
# → Click "Reopen in Container" when prompted

# Start dev server
npm run dev
# → Visit http://localhost:5173
```

### Production

```bash
# Build for production
npm run build

# Preview production build locally
npm run preview

# Run in production container
docker build -t dydx-frontend .
docker run -p 3000:80 dydx-frontend
# → Visit http://localhost:3000
```

## 📋 Prerequisites

- **Development:** Docker + VS Code with Remote Containers extension
- **Production:** Docker

## 🛠️ Available Commands

```bash
# Development
npm run dev         # Start dev server (HMR enabled)
npm run build       # Build for production
npm run lint        # Check code quality
npm run preview     # Preview production build

# Docker
docker-compose up -d    # Start backend services
docker-compose down     # Stop backend services
```

## Documentation

See **[docs/README.md](docs/README.md)** for complete documentation index and quick links.

Quick access:

- **[Setup Guide](docs/SETUP.md)** - Development and production setup
- **[DevContainer Quick Start](docs/devcontainer/QUICKSTART.md)** - 30-second setup
- **[Troubleshooting](docs/guides/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Code Patterns](/.github/copilot-instructions.md)** - Project conventions and patterns

## 🔧 Project Structure

```
src/
├── components/       # Reusable React components
├── pages/           # Route-level components
├── store/           # Zustand state management
├── api.ts           # API client with interceptors
└── hooks/           # Custom React hooks

.devcontainer/       # DevContainer configuration
docs/               # All documentation
├── devcontainer/   # DevContainer guides
├── architecture/   # System design
└── guides/         # Detailed guides
```

## 🌍 Environment Variables

Create `.env.local` for local development:

```bash
VITE_API_URL=http://localhost:8889
```

See [.env.local.example](.env.local.example) for all available variables.

## 🔐 SSH & Git Setup

✅ **Automatic in DevContainer:**

- SSH keys from `~/.ssh` mounted automatically
- Git config from `~/.gitconfig` mounted automatically
- All git operations use your identity

## 🐳 Docker Services

Start backend services locally:

```bash
docker-compose up -d    # PostgreSQL + Redis + Backend API
docker-compose logs -f  # View logs
docker-compose down     # Stop services
```

Services available at:

- **Frontend:** <http://localhost:5173> (dev) or <http://localhost:3000> (prod)
- **Backend API:** <http://localhost:8889>
- **PostgreSQL:** localhost:5432
- **Redis:** localhost:6379

## 📦 Tech Stack

- **React 19** + **TypeScript** + **Vite**
- **Zustand** (state management)
- **TailwindCSS v4** (styling)
- **Recharts** (data visualization)
- **Axios** (HTTP client)
- **React Router** (navigation)

## 🏗️ Architecture

For detailed architecture information, see [docs/architecture/](docs/architecture/)

## 🎓 Code Patterns

See [.github/copilot-instructions.md](.github/copilot-instructions.md) for:

- Project-specific conventions
- State management patterns
- API integration patterns
- Component structure
- Styling guidelines

## 📝 Contributing

1. Create a branch from `master`
2. Make your changes
3. Run: `npm run lint -- --fix`
4. Commit with descriptive messages
5. Push and create a pull request

## ❓ Help

- **Setup issues?** → [docs/guides/TROUBLESHOOTING.md](docs/guides/TROUBLESHOOTING.md)
- **DevContainer help?** → [docs/devcontainer/README.md](docs/devcontainer/README.md)
- **Architecture questions?** → [docs/architecture/](docs/architecture/)
- **Code patterns?** → [.github/copilot-instructions.md](.github/copilot-instructions.md)

## 📄 License

See LICENSE file in root directory

---

**Ready to get started?** Read [docs/SETUP.md](docs/SETUP.md) or [docs/devcontainer/QUICKSTART.md](docs/devcontainer/QUICKSTART.md)
