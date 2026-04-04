# Setup Guide - Development & Production

This frontend is now documented for direct local development on macOS/Linux.

## 🚀 Quick Start

### Prerequisites

- Node.js 20+
- npm
- Docker + `make` if you want shared integration services

### Local frontend setup

```bash
# From frontend/
npm install
npm run dev
```

Visit <http://localhost:5173>

### Start shared integration services

From the repo root:

```bash
make stack-env
make infra-up
```

For full-stack verification:

```bash
make stack-up-dev
```

## 🐳 Production Build

```bash
npm run build
npm run preview
```

### Docker image

```bash
docker build -t dydx-frontend .
docker run -p 3000:80 dydx-frontend
```

Visit <http://localhost:3000>

## 🔧 Available Commands

```bash
npm run dev
npm run build
npm run lint
npm run preview
npm run qa:screenshots:plan
npm run qa:screenshots:capture
npm run qa:screenshots:sync
```

Repo-root integration commands:

```bash
make infra-up
make infra-down
make stack-up-dev
make stack-down
make stack-logs
```

## 📦 Environment Variables

Keep shared values in the repo-root `.env`:

```bash
VITE_API_URL=http://localhost:8888
NODE_ENV=development
```

For production builds:

```bash
VITE_API_URL=https://api.example.com
NODE_ENV=production
```

## 🔐 Git & SSH Setup

Use your normal local configuration:

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
ssh -T git@github.com
```

## 🐳 Available Services

| Service         | Port | URL                                                          |
| --------------- | ---- | ------------------------------------------------------------ |
| Frontend (Vite) | 5173 | <http://localhost:5173>                                      |
| Go Backend API  | 8888 | <http://localhost:8888>                                      |
| Bot API         | 8889 | <http://localhost:8889>                                      |
| PostgreSQL      | 5432 | `postgresql://postgres:postgres@localhost:5432/dydx_trading` |
| Redis           | 6379 | `redis://localhost:6379`                                     |

## 🆘 Troubleshooting

If you hit port conflicts, dependency problems, or backend connectivity issues, use [guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md).

## 🎯 Next Steps

- Need architecture info? → [architecture/README.md](architecture/README.md)
- Need troubleshooting? → [guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md)
- Need project conventions? → [../../.github/copilot-instructions.md](../../.github/copilot-instructions.md)
