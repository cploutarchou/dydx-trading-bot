# 🔧 Backend Package Setup

Complete guide to the FastAPI backend package configuration and installation.

## Overview

The backend is configured as an installable Python package using modern Python packaging standards (PEP517/PEP518). This allows it to be:

- ✅ Installed from any location
- ✅ Used without PYTHONPATH manipulation
- ✅ Distributed independently
- ✅ Version controlled
- ✅ Production-ready

---

## 📦 Package Structure

```
backend/
├── setup.py                 # Package definition (setuptools)
├── __init__.py              # Package marker with version
├── main.py                  # FastAPI application
├── auth.py                  # Authentication logic
├── database.py              # SQLAlchemy ORM setup
├── services.py              # Business logic layer
└── requirements.txt         # Dependencies
```

## Setup.py Contents

The `backend/setup.py` defines the package:

```python
from setuptools import setup, find_packages

setup(
    name="dydx-trading-bot-backend",
    version="1.0.0",
    description="FastAPI backend for dYdX Trading Bot",
    packages=find_packages(),
    python_requires=">=3.12",
    install_requires=[
        "fastapi==0.104.1",
        "uvicorn[standard]==0.24.0",
        "sqlalchemy==2.0.23",
        # ... all dependencies from requirements.txt
    ],
)
```

This file specifies:

- **Package name** - `dydx-trading-bot-backend`
- **Version** - `1.0.0`
- **Python requirement** - 3.12+
- **Dependencies** - All requirements from `requirements.txt`

---

## 🚀 Installation

### Automatic (Recommended)

```bash
# Via Makefile (includes backend install)
make setup      # Create .venv
make install    # Install all + backend package
```

This automatically runs:

```bash
.venv/bin/pip install -e ./backend --use-pep517
```

### Manual Installation

```bash
# Install backend as editable package
.venv/bin/pip install -e ./backend --use-pep517

# Or with dependencies:
.venv/bin/pip install -e ./backend[dev] --use-pep517
```

### Verification

Verify backend is installed:

```bash
# Check package info
.venv/bin/pip show dydx-trading-bot-backend

# Test import
.venv/bin/python -c "import backend; print('✅ Installed')"

# Test main module
.venv/bin/python -c "import backend.main; print('✅ Main OK')"
```

Expected output:

```
Name: dydx-trading-bot-backend
Version: 1.0.0
Summary: FastAPI backend for dYdX Trading Bot backtest management
Location: .../dydx-trading-bot/backend
```

---

## 🔄 How It Works

### Traditional Approach (BEFORE)

```bash
# Required PYTHONPATH manipulation
PYTHONPATH=. python -m uvicorn backend.main:app

# Problems:
# ❌ Must set environment variable
# ❌ Must run from project root
# ❌ Error-prone
```

### Modern Approach (AFTER)

```bash
# Clean, no PYTHONPATH needed
python -m uvicorn backend.main:app

# Works because:
# ✅ Backend installed via pip
# ✅ Modules in sys.path automatically
# ✅ Works from any directory
```

### Why Editable Install?

```bash
# -e flag = editable mode
pip install -e ./backend

# Creates symbolic link to source files
# Benefits:
# ✅ Changes reflect immediately
# ✅ No reinstall needed during development
# ✅ Still produces installable package
```

---

## 📝 Dependencies

### Main Dependencies

From `backend/requirements.txt`:

```
fastapi==0.104.1           # Web framework
uvicorn[standard]==0.24.0  # ASGI server
sqlalchemy==2.0.23         # ORM
alembic==1.13.0            # Database migrations
pydantic==2.5.0            # Data validation
python-jose==3.3.0         # JWT tokens
passlib==1.7.4             # Password hashing
bcrypt==4.1.1              # Encryption
psycopg2-binary==2.9.9     # PostgreSQL driver
```

### Installation

All dependencies installed automatically via:

```bash
make install              # All-in-one
# or
pip install -r backend/requirements.txt  # Just backend deps
```

---

## 🏃 Running the Backend

### Via Makefile (Recommended)

```bash
# Start with hot-reload
make backend-run

# Output:
# 🚀 Starting FastAPI backend server...
# 📊 API running on http://localhost:8000
# ...
# INFO: Uvicorn running on http://0.0.0.0:8000
# INFO: Application startup complete.
```

### Via Command Line

```bash
# From project root
.venv/bin/python -m uvicorn backend.main:app --reload

# With custom port
.venv/bin/python -m uvicorn backend.main:app --port 9000

# Production mode (no reload)
.venv/bin/python -m uvicorn backend.main:app --workers 4
```

### Via Docker

```bash
# Build and run in Docker
make docker-build
make docker-run

# Or with Compose
make docker-up
```

---

## 🔍 Backend Structure

### Main Entry Point

**`backend/main.py`** - FastAPI application

```python
from fastapi import FastAPI
from backend.auth import router as auth_router

app = FastAPI(title="dYdX Trading Bot API")

# Include routers
app.include_router(auth_router, prefix="/api/v1")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "ok"}
```

Endpoints:

- `GET /health` - Health check
- `GET /docs` - Swagger UI
- `GET /redoc` - ReDoc UI
- `/api/v1/*` - API endpoints

### Authentication

**`backend/auth.py`** - JWT authentication

```python
from backend.auth import create_access_token, verify_token

# Create token
token = create_access_token({"user_id": 123})

# Verify token
payload = verify_token(token)
```

### Database

**`backend/database.py`** - SQLAlchemy setup

```python
from backend.database import Base, get_db, engine

# Create tables
Base.metadata.create_all(bind=engine)

# Get database session
async def get_session():
    async with AsyncSession(engine) as session:
        yield session
```

### Business Logic

**`backend/services.py`** - Application logic

```python
from backend.services import UserService, BacktestRunService

# User operations
service = UserService(db_session)
user = await service.create_user(email="user@example.com")

# Backtest operations
backtest_service = BacktestRunService(db_session)
results = await backtest_service.get_recent_runs()
```

---

## 🌐 API Endpoints

When backend is running, access:

| Endpoint | Purpose |
|----------|---------|
| `http://localhost:8000` | Root/status |
| `http://localhost:8000/docs` | Swagger UI (interactive) |
| `http://localhost:8000/redoc` | ReDoc UI (static) |
| `http://localhost:8000/openapi.json` | OpenAPI schema |
| `http://localhost:8000/health` | Health check |
| `/api/v1/*` | API endpoints |

### Example API Call

```bash
# Get API documentation
curl http://localhost:8000/docs

# Or in browser
open http://localhost:8000/docs
```

---

## 🧪 Testing Backend

### Unit Tests

```bash
# Run all tests
make test

# Run with coverage
.venv/bin/pytest tests/ --cov=backend
```

### Integration Tests

```bash
# Start backend first
make backend-run &

# Run integration tests
.venv/bin/pytest tests/integration/ -v
```

### Manual Testing

```bash
# Test endpoint
curl -X GET http://localhost:8000/health

# With authentication
curl -X GET http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🔄 Development Workflow

### Make Changes

```bash
# Edit backend code
nano backend/services.py

# Changes take effect immediately (hot reload)
```

### Reinstall If Needed

```bash
# If dependencies change
pip install -e ./backend --use-pep517

# Or via Makefile
make install
```

### Check for Issues

```bash
# Linting
make lint

# Type checking
.venv/bin/mypy backend/

# Security scan
.venv/bin/bandit -r backend/
```

---

## 📊 Configuration

Backend configuration in `app/config.yaml`:

```yaml
backend:
  host: "0.0.0.0"
  port: 8000
  workers: 1
  reload: true              # Hot reload in development
  database_url: "..."       # Database connection

logging:
  level: "INFO"
  format: "json"            # For structured logging
```

---

## 🚀 Production Deployment

### Prerequisites

- PostgreSQL database
- Environment variables set
- SSL certificate (for HTTPS)

### Deployment Steps

```bash
# 1. Install package
pip install ./backend

# 2. Set environment
export DATABASE_URL="postgresql://user:pass@host/db"
export SECRET_KEY="your-secret-key"

# 3. Run with Gunicorn
gunicorn backend.main:app -w 4 -b 0.0.0.0:8000

# Or with Uvicorn
uvicorn backend.main:app --workers 4 --port 8000
```

### Docker Deployment

```bash
# Build production image
make docker-build

# Run with Docker Compose
make docker-up
```

---

## 🔐 Security

### CORS Configuration

```python
# backend/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Environment Variables

```bash
# Set before running
export DATABASE_URL="postgresql://..."
export SECRET_KEY="your-secret-key"
export ALLOWED_HOSTS="localhost,example.com"

# Then run
uvicorn backend.main:app
```

### Secrets Management

```bash
# Use .env file (not committed to git)
cp .env.example .env
# Edit .env with actual values

# Load in application
from dotenv import load_dotenv
load_dotenv()
```

---

## 🆘 Troubleshooting

### Import Errors

```bash
# Problem: ModuleNotFoundError: No module named 'backend'
# Solution: Reinstall backend package
pip install -e ./backend --use-pep517
```

### Port Already in Use

```bash
# Problem: Address already in use
# Solution: Kill existing process
lsof -ti:8000 | xargs kill -9

# Or use different port
uvicorn backend.main:app --port 9000
```

### Database Connection Error

```bash
# Problem: Could not connect to database
# Solution: Check DATABASE_URL environment variable
echo $DATABASE_URL

# Or check PostgreSQL is running
psql -c "SELECT 1"
```

### Hot Reload Not Working

```bash
# Problem: Changes not reflected
# Solution: Ensure --reload flag is set
uvicorn backend.main:app --reload

# Or use Makefile
make backend-run
```

---

## 📚 References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Python Packaging Guide](https://packaging.python.org/)

---

## ✅ Verification Checklist

After setup:

- [ ] Backend package installed (`pip show dydx-trading-bot-backend`)
- [ ] Backend imports work (`python -c "import backend"`)
- [ ] Backend starts (`make backend-run`)
- [ ] API accessible (<http://localhost:8000/docs>)
- [ ] All endpoints responsive
- [ ] Tests passing (`make test`)
- [ ] No linting errors (`make lint`)

---

**Last Updated**: October 18, 2025  
**Status**: Backend Setup Complete ✅
