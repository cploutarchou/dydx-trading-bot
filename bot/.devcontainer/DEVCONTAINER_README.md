# dYdX Trading Bot - Dev Container Setup Guide

## Quick Start

### Using VS Code Dev Containers

1. **Prerequisites**
   - VS Code with "Dev Containers" extension installed
   - Docker Desktop running
   - Git configured

2. **Open in Container**
   - Open the workspace folder in VS Code
   - Click the green remote indicator at the bottom left
   - Select "Reopen in Container"
   - Wait for container to build and initialize

3. **After Opening**
   - All dependencies will be automatically installed
   - Pre-commit hooks will be configured
   - Database migrations will be applied

### Using Docker Compose Directly

```bash
# Navigate to the .devcontainer directory
cd .devcontainer

# Start all services
docker-compose up -d

# Run shell in dev container
docker-compose exec dev bash

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

## Container Structure

### Services Included

**Main Development Container (dev)**

- Python 3.11
- Pre-installed project dependencies
- Development tools (pytest, black, ruff, mypy)
- Jupyter Lab for notebooks
- Pre-commit hooks configured
- Volume mounted workspace

**PostgreSQL (postgres)**

- PostgreSQL 15
- Pre-initialized database: `dydx_bot`
- Default credentials: `postgres:postgres`
- Port: 5432
- Health checks enabled

**Redis (redis)**

- Redis 7 Alpine
- Persistence enabled (AOF)
- Port: 6379
- Health checks enabled

**pgAdmin (optional)**

- Web-based PostgreSQL management
- URL: <http://localhost:5050>
- Credentials: `admin@dydx.local:admin`
- Port: 5050

**Redis Commander (optional)**

- Web-based Redis management
- URL: <http://localhost:8081>
- Port: 8081

## Environment Variables

The dev container automatically loads:

- `.env` - copied from `example.env` on first setup
- `config.yaml` - your trading configuration

Key variables:

```
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/dydx_bot
REDIS_URL=redis://redis:6379
ENV=development
```

## Available Ports

| Port | Service | URL |
|------|---------|-----|
| 8889 | Bot API Server | <http://localhost:8889> |
| 8000 | FastAPI | <http://localhost:8000> |
| 5432 | PostgreSQL | postgresql://localhost:5432 |
| 6379 | Redis | redis://localhost:6379 |
| 8888 | Jupyter | <http://localhost:8888> |
| 5050 | pgAdmin | <http://localhost:5050> |
| 8081 | Redis Commander | <http://localhost:8081> |

## Common Tasks

### Running the Bot

```bash
python main.py
```

### Running the API Server

```bash
python bot_api_server.py
```

### Running Tests

```bash
pytest
pytest -v
pytest --cov
```

### Formatting Code

```bash
black .
ruff check . --fix
```

### Type Checking

```bash
mypy . --ignore-missing-imports
```

### Starting Jupyter Lab

```bash
jupyter lab --ip=0.0.0.0 --no-browser
```

### Accessing PostgreSQL

```bash
psql postgresql://postgres:postgres@postgres/dydx_bot
```

### Accessing Redis

```bash
redis-cli -h redis
```

### Database Migrations

```bash
# Apply migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Description"

# Downgrade
alembic downgrade -1
```

## Development Workflow

1. **Make code changes** in your editor
2. **Hot reload** happens automatically for API server
3. **Run tests** with `pytest` to validate
4. **Format code** with `black` before committing
5. **Pre-commit hooks** run automatically on git commit

## Troubleshooting

### Container won't start

```bash
docker-compose down -v
docker-compose up --build
```

### Dependencies not installed

```bash
docker-compose exec dev pip install -r requirements.txt
```

### Database connection refused

```bash
# Check postgres is running
docker-compose logs postgres

# Restart postgres
docker-compose restart postgres
```

### Redis connection refused

```bash
# Check redis is running
docker-compose logs redis

# Restart redis
docker-compose restart redis
```

### Permission denied on scripts

```bash
chmod +x .devcontainer/*.sh
```

## Extensions Installed

- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Black Formatter (ms-python.black-formatter)
- Ruff (charliermarsh.ruff)
- Docker (ms-azuretools.vscode-docker)
- REST Client (httpYac.httpClient)
- GitLens (eamodio.gitlens)
- Post Client (Postman.postman-for-vscode)

## Next Steps

1. Copy `.env` from `example.env` and add your credentials
2. Update `config.yaml` with trading parameters
3. Run migrations: `alembic upgrade head`
4. Test bot: `pytest`
5. Start development: `python bot_api_server.py`

## Additional Resources

- [VS Code Dev Containers Docs](https://code.visualstudio.com/docs/devcontainers/containers)
- [Docker Documentation](https://docs.docker.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)

## File Structure

```
.devcontainer/
├── devcontainer.json       # VS Code dev container config
├── Dockerfile              # Development container image
├── docker-compose.yml      # Multi-service orchestration
├── post-create.sh          # Setup script run after container creation
├── init-db.sql             # Database initialization
└── DEVCONTAINER_README.md  # This file
```
