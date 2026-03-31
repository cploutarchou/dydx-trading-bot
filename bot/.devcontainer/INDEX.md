# 🐳 Dev Container - Complete Documentation Index

## 📋 Quick Navigation

Start here based on your needs:

### 👶 Just Getting Started?
→ Read: **GETTING_STARTED.md** (5-15 minutes)
- Prerequisites checklist
- Step-by-step setup
- Common tasks
- Troubleshooting

### �� Want Quick Commands?
→ Check: **DEV_CONTAINER_SETUP.md** (2 minutes)
- Summarized quick start options
- All commands in one place
- Access points and ports

### 🔧 Detailed Dev Container Info?
→ See: **DEVCONTAINER_README.md** (10 minutes)
- Container structure
- Services included
- Workflow examples
- Advanced usage

### 📖 Need Full Reference?
→ Use all files together for complete understanding

## 📂 File Reference

### Configuration Files

**devcontainer.json** (2.5 KB)
- VS Code dev container configuration
- Extensions list
- Port forwarding configuration
- Python settings

**docker-compose.yml** (2.5 KB)
- 5 services: dev, postgres, redis, pgAdmin, redis-commander
- Volume management
- Network configuration
- Health checks

**Dockerfile** (1.5 KB)
- Python 3.11 Bullseye base
- System dependencies
- Python tools installation
- Health check configuration

**post-create.sh** (2.6 KB)
- Automatic setup after container creation
- Dependency installation
- Pre-commit setup
- Database initialization
- Directory creation

### Configuration & Linting

**.pre-commit-config.yaml** (1.7 KB)
- Git pre-commit hooks
- Black, Ruff, MyPy configuration
- Code quality automation

**pyproject.toml** (1.8 KB)
- Black settings
- Ruff linting rules
- MyPy type checking
- Pytest configuration
- Coverage settings

**.bandit** (144 B)
- Security checking configuration

**init-db.sql** (415 B)
- PostgreSQL initialization script
- Database schema setup

### Documentation

**INDEX.md** (This file)
- Quick navigation guide
- File reference
- Usage patterns

**GETTING_STARTED.md** (8.0 KB) ⭐ START HERE
- Prerequisites
- Quick start options (4 methods)
- First-time setup
- Common workflows
- Troubleshooting
- Port mappings

**DEV_CONTAINER_SETUP.md** (14 KB)
- Complete overview
- What was created
- Services included
- All commands reference
- Configuration details
- Next steps

**DEVCONTAINER_README.md** (5.1 KB)
- Container structure details
- Services reference
- Environment variables
- Common tasks
- Troubleshooting guide
- File structure

### Root Level Files

**Makefile** (8.0 KB)
- 30+ convenient make targets
- Development commands
- Bot management
- Database operations
- Utility commands

**devcontainer.sh** (8.0 KB)
- Interactive helper script
- All commands with color output
- Docker management
- Development workflow
- Error handling

## 🎯 Common Workflows

### First Time Setup

```
1. Read GETTING_STARTED.md
2. Run: make up
3. Run: make shell
4. Configure .env
5. Update config.yaml
6. Run: make migrate
7. Run: make test
```

### Daily Development

```
1. Start: make up
2. Work: Edit files (auto-format on save)
3. Test: make test
4. Commit: git commit (pre-commit hooks run automatically)
5. Stop: make down (at end of day)
```

### Debugging

```
1. Set breakpoint in VS Code
2. Run: Ctrl+Shift+D (debug)
3. Select Python debugger
4. Inspect variables
5. Step through code
```

### Production Deployment

```
1. Read SETUP_AND_DEPLOYMENT.md (in parent docs)
2. Test in container
3. Follow deployment guide
4. Monitor with systemd
```

## 📚 Related Documentation

Parent documentation files:

- **../QUICK_START.md** - Bot quick start (5 minutes)
- **../API_USAGE_GUIDE.md** - Complete API reference
- **../SETUP_AND_DEPLOYMENT.md** - Deployment guide
- **../DEVELOPER_REFERENCE.md** - Technical deep dive
- **../DOCUMENTATION_COMPLETE.md** - Feature overview

## �� Quick Links

### Ports & Services

| Service | Port | URL |
|---------|------|-----|
| Bot API | 8889 | http://localhost:8889 |
| API Docs | 8889/docs | http://localhost:8889/docs |
| PostgreSQL | 5432 | postgresql://localhost:5432 |
| pgAdmin | 5050 | http://localhost:5050 |
| Redis | 6379 | redis://localhost:6379 |
| Redis Commander | 8081 | http://localhost:8081 |
| Jupyter | 8888 | http://localhost:8888 |

### Quick Commands

```bash
# Start environment
make up

# Open shell
make shell

# Run tests
make test

# Format code
make format

# All checks
make check

# Start API
python start_api.py

# Database
make db-shell

# Help
make help
```

### Helper Script

```bash
# Show help
./devcontainer.sh help

# Start
./devcontainer.sh start

# Shell
./devcontainer.sh shell

# Status
./devcontainer.sh status

# Logs
./devcontainer.sh logs
```

## ✅ Checklist Before Starting

- [ ] Docker Desktop installed and running
- [ ] VS Code with Dev Containers extension
- [ ] Git configured
- [ ] At least 4GB RAM available
- [ ] Port 5432, 6379, 8889 not in use (or update docker-compose.yml)

## 🚀 Start Now

### Quickest Path (< 5 minutes)

```bash
cd /home/chris/workspace/dydx-trading-bot/bot
make up
make shell
```

### VS Code Path (Recommended)

```bash
code /home/chris/workspace/dydx-trading-bot/bot
# Click green remote indicator → Reopen in Container
# Wait for build
# Ctrl+` to open terminal
```

### Full Setup Path

1. Read **GETTING_STARTED.md**
2. Follow step-by-step instructions
3. Configure credentials
4. Run tests
5. Start trading

## 📞 Troubleshooting Quick Links

| Issue | Solution |
|-------|----------|
| Container won't start | See GETTING_STARTED.md → Troubleshooting |
| Ports in use | Edit docker-compose.yml port mappings |
| DB connection failed | `make restart` then `make migrate` |
| Dependencies missing | `make install-deps` |

## 📊 What's Included

- ✅ Python 3.11 with all dependencies
- ✅ PostgreSQL 15 database
- ✅ Redis 7 cache
- ✅ FastAPI web framework
- ✅ SQLAlchemy ORM
- ✅ Pytest testing framework
- ✅ Black code formatter
- ✅ Ruff linter
- ✅ MyPy type checker
- ✅ Pre-commit hooks
- ✅ Jupyter Lab
- ✅ pgAdmin & Redis Commander
- ✅ 13 VS Code extensions

## 🎓 Learning Path

**Beginner (New to dev containers):**
1. GETTING_STARTED.md - Learn basics
2. DEV_CONTAINER_SETUP.md - See what's available
3. Start with `make up` and explore

**Intermediate (Familiar with Docker):**
1. Review docker-compose.yml
2. Understand service relationships
3. Customize configuration as needed

**Advanced (Deploying to production):**
1. Understand production requirements
2. Review Dockerfile
3. Read SETUP_AND_DEPLOYMENT.md
4. Deploy with confidence

---

**Start with:** Read **GETTING_STARTED.md** → Run `make up` → Start coding! 🚀
