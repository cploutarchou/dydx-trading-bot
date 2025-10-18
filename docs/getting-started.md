# 🚀 Getting Started - 5 Minute Setup

Get the dYdX Trading Bot running in just 5 minutes!

## ⚡ Quick Start (TL;DR)

```bash
# 1. Clone and navigate
cd /home/chris/workspace/dydx-trading-bot

# 2. Setup (1 min)
make setup              # Create virtual environment
make install            # Install dependencies

# 3. Configure (1 min)
make config             # Create app/config.yaml

# 4. Run (1 min)
make backend-run        # Terminal 1: Backend on port 8000
make run                # Terminal 2: Trading bot

# 5. Verify (2 min)
curl http://localhost:8000/docs  # Backend API docs
```

✅ You're done! Backend running on <http://localhost:8000>

---

## 📋 Step-by-Step Setup

### Step 1: Prerequisites Check (1 min)

Ensure you have:

- ✅ Python 3.12+
- ✅ Git
- ✅ Make
- ✅ 2GB free disk space

**Check versions:**

```bash
python3 --version      # Should be 3.12+
git --version          # Should be 2.0+
make --version         # Should be present
```

### Step 2: Initial Setup (1 min)

```bash
# Navigate to project
cd /home/chris/workspace/dydx-trading-bot

# Create virtual environment
make setup

# Output should show:
# Virtual environment created. Activate with: source .venv/bin/activate
```

### Step 3: Install Dependencies (2 min)

```bash
# Install all project dependencies
make install

# This will:
# ✅ Upgrade pip
# ✅ Install main requirements (trading bot, API client)
# ✅ Install backend package (FastAPI, SQLAlchemy, etc)
# ✅ Install dev tools (testing, linting, formatting)
```

### Step 4: Create Configuration (30 sec)

```bash
# Create configuration file
make config

# This creates app/config.yaml with defaults
# Edit it to configure:
# - dYdX network (testnet/mainnet)
# - Trading parameters (Z-score threshold, position size)
# - Telegram notifications
```

### Step 5: Run Backend (30 sec)

```bash
# Terminal 1: Start FastAPI backend
make backend-run

# Expected output:
# 🚀 Starting FastAPI backend server...
# 📊 API running on http://localhost:8000
# ...
# INFO: Application startup complete.
```

### Step 6: Run Trading Bot (Optional)

```bash
# Terminal 2: Start trading bot (requires config.yaml)
make run

# Or start in background:
make start
```

---

## 🎯 Environment Options

Choose your preferred development environment:

### **Option A: Local Development** (Simplest)

Best for: Quick testing, learning, debugging

```bash
make setup
make install
make backend-run
```

✅ Pros:

- Fastest setup
- Direct access to files
- Easy debugging

❌ Cons:

- Requires local Python 3.12
- System dependencies needed

---

### **Option B: Dev Container** (Recommended)

Best for: Full development with IDE integration

**Prerequisites:**

- VS Code installed
- Docker Desktop running
- VS Code Dev Containers extension

**Setup:**

```bash
# Open project in dev container
make devcontainer

# Inside container terminal:
make install
make backend-run    # Terminal 1
make frontend-run   # Terminal 2
```

✅ Pros:

- Isolated environment
- All dependencies included
- IDE integration (debugging, etc)
- Same as CI/CD environment

❌ Cons:

- Requires Docker
- Slightly slower first time

---

### **Option C: Docker** (Production-like)

Best for: Testing production deployment

```bash
# Build Docker image
make docker-build

# Run in Docker
make docker-run
```

✅ Pros:

- Reproducible environment
- Production-like setup
- Easy to share

❌ Cons:

- Slightly slower
- Less interactive

---

### **Option D: Docker Compose** (Full Stack)

Best for: Testing complete backend + frontend

```bash
# Start full stack
make docker-up

# Services running:
# - Backend: http://localhost:8000
# - Frontend: http://localhost:5173
# - Postgres: localhost:5432
```

✅ Pros:

- Complete stack ready
- All services coordinated
- Production-like

❌ Cons:

- Requires Docker Compose
- More resources needed

---

## 🌐 Verify Setup

After starting the backend, verify everything works:

### Check Backend Health

```bash
# In another terminal
curl http://localhost:8000/health

# Or visit in browser
open http://localhost:8000/docs
```

### Check Backend is Installable

```bash
.venv/bin/python -c "import backend; print('✅ Backend OK')"
```

### Check Trading Bot (if running)

```bash
# Check bot status
make status

# View logs
make logs
```

---

## 📊 What's Running?

After setup, you have:

| Component | Port | URL | Purpose |
|-----------|------|-----|---------|
| **Backend** | 8000 | <http://localhost:8000> | FastAPI server |
| **API Docs** | 8000 | <http://localhost:8000/docs> | Swagger UI |
| **Trading Bot** | - | - | Cointegration analysis |
| **Frontend** | 5173 | <http://localhost:5173> | React dashboard (optional) |

---

## 🔧 Common Tasks

### Run Backend

```bash
make backend-run
```

### Run Trading Bot

```bash
make run              # Foreground
# or
make start            # Background
make stop             # Stop background bot
```

### Create Configuration

```bash
make config           # Interactive setup
# Edit app/config.yaml with your settings
```

### Test Setup

```bash
make test             # Run test suite
make lint             # Check code quality
```

### View Logs

```bash
make logs             # Show bot logs
```

### Stop Everything

```bash
make stop             # Stop trading bot
# Ctrl+C for backend
```

---

## 🚨 Troubleshooting

### Virtual Environment Not Found

```bash
make setup            # Create new venv
make install          # Install dependencies
```

### Python Version Error

```bash
# Check Python version
python3 --version

# Should be 3.12 or higher
# If not, install Python 3.12
```

### Port 8000 Already in Use

```bash
# Kill existing process
lsof -ti:8000 | xargs kill -9

# Or use different port:
.venv/bin/python -m uvicorn backend.main:app --port 9000
```

### Backend Import Errors

```bash
# Reinstall backend package
.venv/bin/pip install -e ./backend --use-pep517
```

### More Issues?

See [Troubleshooting Guide](./guides/troubleshooting.md) for comprehensive help.

---

## 📚 Next Steps

### After Setup

1. **Explore the Backend API**
   - Visit <http://localhost:8000/docs>
   - Try API endpoints in Swagger UI

2. **Configure the Trading Bot**
   - Edit `app/config.yaml`
   - See [Configuration Guide](./guides/configuration.md)

3. **Understand the System**
   - Read [Architecture Overview](./architecture/system-overview.md)
   - Review [Trading Strategy](./trading/strategy.md)

4. **Start Development**
   - See [Development Guide](./development.md)
   - Check [API Reference](./api/core-modules.md)

5. **Deploy to Production**
   - Read [Deployment Guide](./deployment/docker-setup.md)
   - Review Docker Compose setup

---

## ✅ Success Checklist

After setup, you should have:

- [ ] Virtual environment created (`.venv/`)
- [ ] Dependencies installed (150+ packages)
- [ ] Backend package installed (`dydx-trading-bot-backend`)
- [ ] `app/config.yaml` created
- [ ] Backend running on port 8000
- [ ] API docs accessible at <http://localhost:8000/docs>
- [ ] Tests passing (`make test`)
- [ ] Code linting passing (`make lint`)

---

## 🆘 Need Help?

- **Setup Issues?** → [Troubleshooting Guide](./guides/troubleshooting.md)
- **Configuration Help?** → [Configuration Guide](./guides/configuration.md)
- **Development Questions?** → [Development Guide](./development.md)
- **Deployment?** → [Deployment Guide](./deployment/docker-setup.md)

---

**Last Updated**: October 18, 2025  
**Status**: Quick Start Complete ✅
