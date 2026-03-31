# Dev Container Setup - Getting Started

This document provides detailed instructions for setting up and using the dYdX Trading Bot development container.

## Prerequisites

- **Docker Desktop** (or Docker + Docker Compose)
  - [Download Docker Desktop](https://www.docker.com/products/docker-desktop)
  - Ensure Docker daemon is running

- **VS Code** with Dev Containers extension
  - [Install VS Code](https://code.visualstudio.com/)
  - [Install Dev Containers Extension](vscode:extension/ms-vscode-remote.remote-containers)

- **Git** (for version control)
  - [Install Git](https://git-scm.com/)

- **At least 4GB RAM** available for containers (8GB recommended)

## Quick Start (VS Code)

### Option 1: Using VS Code Dev Containers UI

1. **Open workspace in VS Code**

   ```bash
   cd /path/to/dydx-trading-bot/bot
   code .
   ```

2. **Reopen in container**
   - Click the green remote indicator at the bottom-left corner
   - Select "Reopen in Container"
   - VS Code will rebuild the container and mount your workspace

3. **Wait for initialization**
   - The container will build and run `post-create.sh`
   - Dependencies will be installed automatically
   - Environment will be ready for development

4. **Start working**
   - Open terminal in VS Code (Ctrl+`)
   - Run commands directly in the dev container

### Option 2: Using Docker Compose CLI

```bash
# Navigate to bot directory
cd /path/to/dydx-trading-bot/bot

# Build and start services
make up

# Open shell in dev container
make shell

# Inside the container, verify setup
python --version
pytest --version
```

## First-Time Setup

### First-Time Setup

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your dYdX credentials
nano .env
# or
vim .env
```

Key variables to set:

```
DYDX_CHAIN_ADDRESS=...
DYDX_CHAIN_SECRET=...
DYDX_TESTNET_ENABLED=true  # Start with testnet
```

### SSH Setup (For Git Operations)

For secure Git operations, the container uses SSH agent forwarding instead of mounting SSH keys:

```bash
# On your host, ensure SSH agent is running
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_rsa
```

See `SSH_SETUP.md` for detailed SSH configuration instructions.

### 2. Configure Trading Parameters

```bash
# Edit trading configuration
nano config.yaml

# Key parameters:
# - is_testnet: true (for testing)
# - botSettings.placeTrades: false (enable when ready)
# - botSettings.usdPerTrade: 10.0 (start small)
```

### 3. Run Database Migrations

```bash
make migrate

# Or manually:
alembic upgrade head
```

### 4. Test the Setup

```bash
# Run tests
make test

# Format code
make format

# Type checking
make type-check
```

## Common Development Workflows

### Testing Your Changes

```bash
# Run all tests
make test

# Run specific test file
make shell
pytest tests/test_specific.py -v

# Run with coverage report
make test-cov
```

### Starting the API Server

```bash
# Terminal 1: Start API
python start_api.py

# Terminal 2: Check API status
curl http://localhost:8889/docs

# Terminal 3: Run bot
python main.py
```

### Database Management

```bash
# Access PostgreSQL
make db-shell

# List tables
\dt

# Exit
\q

# Reset database
make db-reset
```

### Redis Management

```bash
# Access Redis CLI
make redis-shell

# Check keys
keys *

# Exit
exit
```

## Project Structure in Container

```
/workspace
├── .devcontainer/          # This directory
├── migrations/             # Alembic database migrations
├── logs/                   # Application logs
├── data/                   # Data files
├── reports/                # Backtest reports
├── start_api.py            # API launcher (compatibility shim)
├── src/api/server.py       # Canonical FastAPI app
├── main.py                 # Bot entry point
├── config.yaml             # Trading configuration
├── .env                    # Environment variables
└── requirements.txt        # Python dependencies
```

## Port Mappings

These services are available on your host machine:

| Port | Service | URL | Login |
|------|---------|-----|-------|
| 8889 | Bot API | `http://localhost:8889` | - |
| 8889/docs | API Docs | `http://localhost:8889/docs` | - |
| 5432 | PostgreSQL | `postgresql://postgres:postgres@localhost:5432/dydx_bot` | - |
| 5050 | pgAdmin | `http://localhost:5050` | `admin@dydx.local:admin` |
| 6379 | Redis | `redis://localhost:6379` | - |
| 8081 | Redis Commander | `http://localhost:8081` | - |
| 8888 | Jupyter | `http://localhost:8888` | (token in logs) |

## Troubleshooting

### Container won't start

```bash
# Check Docker is running
docker ps

# Rebuild container
make clean
make build
make up
```

### Ports already in use

```bash
# Find and kill process using port
lsof -i :8889
kill -9 <PID>

# Or change port in docker-compose.yml
```

### Database connection failed

```bash
# Check PostgreSQL is running
make logs | grep postgres

# Verify database exists
make db-shell
\l

# Reset database if needed
make db-reset
```

### Dependencies installation failed

```bash
# Reinstall dependencies
make shell
pip install -r requirements.txt --force-reinstall
```

### Git permission denied

```bash
# Ensure SSH keys are accessible
ls ~/.ssh

# Make sure SSH is mounted in docker-compose.yml:
# volumes:
#   - ~/.ssh:/home/vscode/.ssh:ro
```

## VS Code Tips

### Terminal Integration

- Open integrated terminal: `Ctrl +` (backtick)
- All commands run in container automatically

### Extensions Already Installed

- Python
- Pylance (advanced type checking)
- Black Formatter (code formatting)
- Ruff (fast linting)
- Docker
- REST Client
- GitLens

### Debug Configuration

To debug Python code:

1. Set breakpoint (click line number)
2. Run with debugger: `Ctrl + Shift + D`
3. Select "Python: Current File"
4. Execution stops at breakpoint
5. Inspect variables in debug panel

### Format on Save

Already enabled! When you save a Python file:

1. Black formats the code
2. Imports are organized
3. Ruff checks for issues

## Advanced Usage

### Custom Environment Variables

Add to `.env`:

```
LOG_LEVEL=DEBUG
API_TIMEOUT=30
BATCH_SIZE=100
```

### Installing Additional Packages

```bash
make shell
pip install package-name

# Or update requirements.txt
echo "package-name==1.0.0" >> requirements.txt
pip install -r requirements.txt
```

### Running Specific Tests

```bash
# Test a single file
make shell
pytest tests/test_api.py

# Test a specific function
pytest tests/test_api.py::test_create_bot

# Test with verbose output
pytest -vv

# Test with print statements
pytest -s
```

### Jupyter Notebooks

```bash
make jupyter

# Open browser to http://localhost:8888
# Notebooks can access all bot code directly
```

## Performance Optimization

### Reduce Container Build Time

```bash
# Use --no-cache to rebuild from scratch
docker-compose build --no-cache

# Clean up old images
docker system prune
```

### Monitor Resource Usage

```bash
# Check container resource usage
docker stats

# Limit container resources in docker-compose.yml
# services:
#   dev:
#     deploy:
#       resources:
#         limits:
#           cpus: '2'
#           memory: 2G
```

## Next Steps

1. ✅ Follow Quick Start section above
2. ✅ Configure credentials in `.env`
3. ✅ Update `config.yaml`
4. ✅ Run `make migrate`
5. ✅ Run `make test` to verify setup
6. ✅ Read QUICK_START.md for bot usage
7. ✅ Start with testnet trading

## Support & Documentation

- **Quick Start**: See `QUICK_START.md`
- **API Reference**: See `API_USAGE_GUIDE.md`
- **Deployment**: See `SETUP_AND_DEPLOYMENT.md`
- **Developer Guide**: See `DEVELOPER_REFERENCE.md`
- **Dev Container Setup**: See `DEVCONTAINER_README.md` (in .devcontainer folder)

## Tips for Smooth Development

1. **Keep .env private**: Never commit with real credentials
2. **Use git branches**: Create feature branches for changes
3. **Run tests before committing**: `make check`
4. **Use meaningful commit messages**: For clear history
5. **Document complex code**: Leave comments for future you
6. **Monitor resource usage**: If container is slow, check `docker stats`
7. **Regular backups**: Commit your changes regularly

## Getting Help

If you encounter issues:

1. Check the troubleshooting section above
2. Review Docker logs: `make logs`
3. Check container status: `docker ps`
4. Verify network connectivity: `docker network ls`
5. Check resource limits: `docker stats`

Happy trading! 🚀
