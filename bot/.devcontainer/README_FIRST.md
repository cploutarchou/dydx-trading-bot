# 🐳 Dev Container - Start Here!

## ⚡ 60-Second Quick Start

### Option A: VS Code (Easiest)
```bash
code /home/chris/workspace/dydx-trading-bot/bot
# Click green remote indicator (bottom-left)
# Select "Reopen in Container"
# Wait 3-5 minutes
# Done! Press Ctrl+` to open terminal
```

### Option B: Command Line (Fastest)
```bash
cd /home/chris/workspace/dydx-trading-bot/bot
make up      # Start services (wait 30 seconds)
make shell   # Enter container
echo "Ready to code!"
```

---

## 📚 Documentation Quick Links

**👶 New to Dev Containers?**
→ [GETTING_STARTED.md](GETTING_STARTED.md) (15 min read, super detailed)

**🎯 Just Give Me Commands**
→ [DEV_CONTAINER_SETUP.md](DEV_CONTAINER_SETUP.md) (2 min, all commands)

**🗺️ Need to Navigate All Docs**
→ [INDEX.md](INDEX.md) (2 min, file reference)

**🔧 Technical Deep Dive**
→ [DEVCONTAINER_README.md](DEVCONTAINER_README.md) (10 min, detailed info)

---

## 🔥 Most Common Commands

```bash
make up              # Start all services
make down            # Stop all services
make shell           # Open shell
make test            # Run tests
make format          # Format code
python start_api.py  # Start API server
make help            # List all commands
```

---

## ✅ What You Get

- ✅ Python 3.11 with all dependencies
- ✅ PostgreSQL 15 database
- ✅ Redis 7 cache
- ✅ Jupyter Lab
- ✅ Automatic code formatting
- ✅ Pre-commit hooks
- ✅ 13 VS Code extensions
- ✅ All development tools

---

## 🎯 Next Step

### Choose your path:

**Path 1: I'm in a rush**
```bash
make up && make shell
```

**Path 2: I want detailed setup**
→ Read [GETTING_STARTED.md](GETTING_STARTED.md)

**Path 3: I'm using VS Code**
Click green remote indicator → Reopen in Container

---

## 📞 Help

- `make help` - All commands
- `./devcontainer.sh help` - Interactive help
- [GETTING_STARTED.md](GETTING_STARTED.md) - Detailed guide
- [INDEX.md](INDEX.md) - Navigation

---

## 🚀 You're Ready!

Pick an option above and start coding. Everything is auto-configured! 🎉
