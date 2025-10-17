# 🐳 Running Backend & Frontend in Dev Container

This guide explains how to run both the FastAPI backend and React frontend in VS Code Dev Container for seamless development.

## 🚀 Quick Start (5 minutes)

### Step 1: Open in Dev Container

```bash
# Option A: From command line
cd /home/chris/workspace/dydx-trading-bot
make devcontainer

# Option B: In VS Code
1. Open the project folder
2. Press Cmd/Ctrl + Shift + P
3. Type "Dev Containers: Reopen in Container"
4. Wait for container to build and start (~2-3 minutes first time)
```

### Step 2: Install Dependencies (One-time)

Inside the dev container terminal:

```bash
# Backend dependencies
pip install -r backend/requirements.txt

# Frontend dependencies
cd frontend
npm install
cd ..
```

### Step 3: Run Backend (Terminal 1)

```bash
# Terminal 1 - Backend on port 8000
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Output should show:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### Step 4: Run Frontend (Terminal 2)

```bash
# Terminal 2 - Frontend on port 5173
cd frontend
npm run dev
```

Output should show:

```
  VITE v5.0.7  ready in 234 ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

### Step 5: Access Services

Open in browser:

| Service | URL |
|---------|-----|
| **Frontend** | <http://localhost:5173> |
| **Backend API** | <http://localhost:8000> |
| **Swagger API Docs** | <http://localhost:8000/docs> |
| **ReDoc** | <http://localhost:8000/redoc> |

---

## 📋 Complete Setup Guide

### Prerequisites

- ✅ VS Code installed
- ✅ Docker Desktop running
- ✅ VS Code Dev Containers extension installed

  ```bash
  # Install if not already present
  code --install-extension ms-vscode-remote.remote-containers
  ```

### Initial Container Setup

#### Opening in Dev Container

**Method 1: VS Code Command Palette**

```
Cmd/Ctrl + Shift + P → "Dev Containers: Reopen in Container"
```

**Method 2: VS Code Remote Explorer**

1. Click Remote Explorer icon (left sidebar)
2. Select "Dev Containers"
3. Click folder icon next to your workspace
4. Select "dydx-trading-bot"

**Method 3: Command Line**

```bash
make devcontainer
```

#### First-Time Setup

The container automatically runs these commands:

- ✅ Installs Python dependencies
- ✅ Sets up Git and Docker-in-Docker
- ✅ Installs Node.js for frontend
- ✅ Configures VS Code extensions

Estimated time: **2-3 minutes**

---

## 🔧 Development Workflow

### Multiple Terminals in Dev Container

VS Code allows multiple terminals inside the container. Use Ctrl+Shift+` to open new terminals:

**Terminal 1: Backend**

```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2: Frontend**

```bash
cd frontend
npm run dev
```

**Terminal 3: Git/Utilities**

```bash
# Available for git commands, running scripts, etc.
git status
python scripts/fast_cointegration.py
```

### Hot Reload

Both services support hot reload:

**Backend:**

- Changes to `.py` files → Auto-reload
- Fast API docs update automatically

**Frontend:**

- Changes to `.tsx`, `.ts`, `.css` files → Auto-reload
- Vite hot module replacement (HMR)

### Debugging

#### Backend Debugging

```bash
# Option 1: Use debugpy (configured in dev container)
cd backend
python -m debugpy --listen 5678 -m uvicorn main:app --reload

# Option 2: Use VS Code debugger
# 1. Set breakpoint in Python code
# 2. Press F5 or Run → Start Debugging
# 3. Select "Python: Remote Attach" configuration
```

#### Frontend Debugging

```bash
# Built-in browser DevTools (F12)
# VS Code debugger for Chrome/Edge:
# 1. Install "Debugger for Chrome" extension
# 2. Add breakpoints in .tsx files
# 3. Press F5 to start debugging
```

---

## 🐘 Database Setup (Optional)

### Using PostgreSQL in Dev Container

#### Option 1: Start with Database Profile

```bash
# From host machine (before opening in dev container)
docker-compose -f .devcontainer/docker-compose.yml --profile with-db up -d
```

#### Option 2: Manual Setup Inside Container

```bash
# Terminal 3 - Start PostgreSQL
docker-compose -f .devcontainer/docker-compose.yml --profile with-db up postgres-dev

# Access PostgreSQL
PGPASSWORD=dev_password psql -h localhost -U dydx_user -d dydx_trading_dev

# Verify connection from Python
python -c "
import psycopg2
conn = psycopg2.connect('host=localhost user=dydx_user password=dev_password dbname=dydx_trading_dev')
print('✅ Connected to PostgreSQL')
"
```

#### Update Backend Config

```python
# backend/database.py
DATABASE_URL = "postgresql://dydx_user:dev_password@localhost:5432/dydx_trading_dev"
```

---

## 📊 Monitoring & Logging

### View Backend Logs

```bash
# Terminal 1 shows all backend logs automatically
# Or tail them:
tail -f logs/backend.log
```

### View Frontend Logs

```bash
# Terminal 2 shows Vite dev server logs
# Browser DevTools (F12) shows JavaScript console
```

### Optional: Grafana + Loki Stack

```bash
# Start monitoring stack
docker-compose -f .devcontainer/docker-compose.yml --profile with-monitoring up -d

# Access Grafana
# URL: http://localhost:3000
# Username: admin
# Password: dev123
```

---

## 🧪 Testing in Dev Container

### Run Tests

```bash
# Terminal 3 - Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_config.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Watch mode (re-run on file changes)
pytest-watch tests/
```

### Backend Testing

```bash
cd backend
pytest tests/ -v --cov=backend

# Or with Makefile
make test
```

### Frontend Testing

```bash
cd frontend
npm run test  # If test script exists in package.json
```

---

## 🔌 Port Forwarding

Dev container automatically forwards these ports:

| Port | Service | URL |
|------|---------|-----|
| **5173** | Frontend (Vite) | <http://localhost:5173> |
| **8000** | Backend (FastAPI) | <http://localhost:8000> |
| **8080** | Alternative server | <http://localhost:8080> |
| **5432** | PostgreSQL | localhost:5432 |
| **6379** | Redis | localhost:6379 |
| **3000** | Grafana | <http://localhost:3000> |
| **3100** | Loki | <http://localhost:3100> |

Access from host machine using `localhost:PORT`

---

## 📁 File Mounting

All files are mounted inside dev container:

```
Host Machine                 Dev Container
/home/chris/...       →      /workspaces/dydx-trading-bot
  ├── backend/        →        ├── backend/
  ├── frontend/       →        ├── frontend/
  ├── app/            →        ├── app/
  └── ...             →        └── ...
```

Changes on host machine appear immediately in container.

---

## 🛠️ Dev Container Commands

### Common Commands

```bash
# Inside dev container

# Install new Python package
pip install package-name

# Install new NPM package (frontend)
cd frontend && npm install package-name

# Run linting
make lint format

# Run specific script
python scripts/fast_cointegration.py

# Git operations (all configured)
git status
git add .
git commit -m "message"
```

### Rebuilding Container

If you modify `.devcontainer/devcontainer.json` or `.devcontainer/Dockerfile`:

```bash
# VS Code: Cmd/Ctrl + Shift + P → "Dev Containers: Rebuild Container"

# Or from command line:
make devcontainer-build
```

---

## 🐛 Troubleshooting

### Container Won't Start

```bash
# Check Docker is running
docker ps

# Check dev container logs
docker logs dydx-trading-bot-dev

# Rebuild container
make devcontainer-build
```

### Port Already in Use

```bash
# Find what's using the port
lsof -i :8000  # or :5173

# Kill the process
kill -9 <PID>

# Or use different port
cd backend
python -m uvicorn main:app --reload --port 8001
```

### Packages Not Installing

```bash
# Clear pip cache
pip cache purge

# Reinstall requirements
pip install --force-reinstall -r backend/requirements.txt

# For frontend
cd frontend && rm -rf node_modules && npm install
```

### Can't Connect to Backend from Frontend

```bash
# Check backend is running
curl http://localhost:8000/docs

# Check CORS is configured
# In backend/main.py, ensure CORS is enabled for localhost:5173

# Try directly
curl -X GET http://localhost:8000/api/users
```

### Git Issues in Container

```bash
# SSH key not available
# Solution: SSH key is automatically mounted from ~/.ssh

# If still issues:
# Configure Git inside container
git config --global user.email "you@example.com"
git config --global user.name "Your Name"
```

---

## 💾 Persisting Data

### Volumes in Dev Container

Data persists in these Docker volumes:

- `vscode-extensions` - VS Code extensions (persists across rebuilds)
- `vscode-settings` - VS Code settings
- `postgres-dev-data` - PostgreSQL data (if using DB)
- `redis-dev-data` - Redis data (if using cache)

To reset all data:

```bash
docker volume prune
make devcontainer-build
```

---

## 🚀 Advanced Setup

### Using Environment Variables

Create `.env` file in project root:

```bash
# Backend
DATABASE_URL=postgresql://dydx_user:dev_password@localhost:5432/dydx_trading_dev
JWT_SECRET=your-secret-key-here

# Frontend
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

Container automatically loads these.

### Custom Makefile Targets

```bash
# Inside dev container
make docker-up-logging    # Start full logging stack
make backtest-quick       # Run quick backtest
make test                 # Run all tests
make format lint          # Format and lint code
```

### Using Docker-in-Docker

Dev container includes Docker-in-Docker capability:

```bash
# Build Docker images from within container
docker build -t my-image .

# Run Docker Compose
docker-compose up -d
```

---

## 📚 Useful VS Code Extensions (Auto-Installed)

Already configured in dev container:

- **Python Development**: Python, Pylint, Black Formatter, isort, Flake8, MyPy
- **Web Development**: ES7+ React/Redux/React-Native snippets
- **Testing**: Pytest, Test Explorer
- **Git**: GitLens, GitHub Pull Requests
- **Docker**: Docker extension
- **AI**: GitHub Copilot, Copilot Chat

---

## 🎯 Typical Development Session

```bash
# 1. Open project in VS Code
code /home/chris/workspace/dydx-trading-bot

# 2. VS Code suggests: "Reopen in Container"
# Click "Reopen in Container" button

# Wait 2-3 minutes for first-time setup...

# 3. Inside container, open Terminal (Ctrl + `)
# Then open 2 more terminals (Ctrl + Shift + `)

# Terminal 1: Backend
cd backend && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev

# Terminal 3: Git/utilities
git status

# 4. Open browser
# Frontend: http://localhost:5173
# Backend Docs: http://localhost:8000/docs

# 5. Start coding!
# - Edit .py files → Backend auto-reloads
# - Edit .tsx files → Frontend auto-reloads
```

---

## 🔗 Useful Links

- [VS Code Dev Containers Docs](https://code.visualstudio.com/docs/devcontainers/containers)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)

---

## ✅ Quick Checklist

- [ ] Docker Desktop is running
- [ ] VS Code Dev Containers extension installed
- [ ] Opened project in dev container
- [ ] Backend dependencies installed (`pip install -r backend/requirements.txt`)
- [ ] Frontend dependencies installed (`cd frontend && npm install`)
- [ ] Backend running on port 8000
- [ ] Frontend running on port 5173
- [ ] Can access <http://localhost:5173> (frontend)
- [ ] Can access <http://localhost:8000/docs> (backend)
- [ ] Tests pass (`make test`)

All set! Happy coding! 🎉
