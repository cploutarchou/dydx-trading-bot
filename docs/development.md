# 👨‍💻 Development Guide

Complete guide for developing the dYdX Trading Bot - local setup, testing, code style, and workflow.

## 🎯 Development Overview

The project consists of:

- **Trading Bot** (`app/`) - Python cointegration analysis engine
- **Backend** (`backend/`) - FastAPI REST API
- **Frontend** (`frontend/`) - React dashboard
- **Tests** (`tests/`) - Pytest suite

---

## 📦 Local Development Setup

### Prerequisites

```bash
# Check requirements
python3 --version      # 3.12+
git --version          # 2.0+
docker --version       # For dev container (optional)
npm --version          # 18+ (for frontend development)
```

### Initial Setup

```bash
# Clone and navigate
cd /home/chris/workspace/dydx-trading-bot

# Create virtual environment
make setup

# Install all dependencies
make install

# Create configuration
make config
```

### Activate Virtual Environment

```bash
# Linux/Mac
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

---

## 🏗️ Project Structure

```
dydx-trading-bot/
├── app/                        # Trading bot (main logic)
│   ├── main.py                 # Entry point
│   ├── config.yaml             # Configuration
│   ├── config.py               # Config parser
│   ├── constants.py            # Constants from config
│   ├── func_*.py               # Functional modules
│   ├── models/                 # Data models
│   │   ├── pair_storage.py     # Cointegration storage
│   │   └── backtest_models.py  # Backtest data models
│   └── logging_setup.py        # Logging configuration
│
├── backend/                    # FastAPI backend
│   ├── setup.py                # Package definition
│   ├── main.py                 # FastAPI app
│   ├── auth.py                 # Authentication
│   ├── database.py             # Database ORM
│   ├── services.py             # Business logic
│   └── requirements.txt         # Backend deps
│
├── frontend/                   # React dashboard
│   ├── package.json            # Dependencies
│   ├── vite.config.ts          # Vite config
│   ├── src/
│   │   ├── main.tsx            # Entry point
│   │   ├── App.tsx             # Main component
│   │   ├── pages/              # Page components
│   │   └── store/              # Zustand store
│   └── index.html              # HTML template
│
├── tests/                      # Test suite
│   └── test_config.py          # Config tests
│
├── scripts/                    # Utility scripts
│   ├── run_backtest.py         # Backtesting
│   ├── close_open_positions.py # Emergency cleanup
│   └── ...
│
├── Makefile                    # Build automation
├── requirements.txt            # Main dependencies
├── requirements-dev.txt        # Dev dependencies
└── docker-compose.yml          # Docker setup
```

---

## 🚀 Running in Development

### Backend Development

```bash
# Terminal 1: Start backend with auto-reload
make backend-run

# Or manually:
.venv/bin/python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Backend will:**

- Listen on <http://localhost:8000>
- Auto-reload on file changes
- Show API docs at <http://localhost:8000/docs>

### Trading Bot Development

```bash
# Terminal 2: Start trading bot
make run

# Or in background:
make start
make logs  # View logs

# To stop:
make stop
```

### Frontend Development

```bash
# Terminal 3: Start React dev server
cd frontend
npm install  # One time
npm run dev  # Runs on port 5173
```

### Full Stack (All Three)

```bash
# Terminal 1
make backend-run

# Terminal 2
make frontend-run

# Terminal 3
make run  # Trading bot
```

---

## 🧪 Testing

### Run All Tests

```bash
make test

# Or with coverage:
.venv/bin/pytest tests/ -v --cov=app
```

### Run Specific Tests

```bash
# Test configuration
.venv/bin/pytest tests/test_config.py -v

# Test specific function
.venv/bin/pytest tests/test_config.py::test_load_config -v
```

### Test Patterns

Tests use **pytest**. Examples:

```python
# tests/test_example.py
def test_function():
    result = some_function()
    assert result == expected_value

def test_with_fixture(tmpdir):
    # tmpdir is a pytest fixture
    pass
```

---

## 🔍 Code Quality

### Linting (Code Style Check)

```bash
make lint

# Runs:
# - flake8: Style violations
# - pylint: Code quality
# - mypy: Type checking
# - bandit: Security issues
```

### Fix Common Issues

```bash
make format

# Runs:
# - black: Code formatting
# - isort: Import organization
```

### Pre-commit Hooks (Optional)

```bash
# Install pre-commit hooks
.venv/bin/pip install pre-commit
pre-commit install

# Now hooks run automatically before commit
pre-commit run --all-files  # Run manually
```

---

## 🐛 Debugging

### Backend Debugging

```bash
# Use VS Code debugger
# 1. Open .vscode/launch.json
# 2. Add FastAPI configuration:
{
    "name": "FastAPI",
    "type": "python",
    "request": "launch",
    "module": "uvicorn",
    "args": ["backend.main:app", "--reload"],
    "jinja": true,
}

# 3. Press F5 to start debugging
```

### Bot Debugging

```bash
# Enable debug logging
# In app/config.yaml:
logging:
  level: "DEBUG"

# Then run:
make run
```

### Print Debugging

```python
# Add print statements
import logging
logger = logging.getLogger(__name__)
logger.debug("Debug message: %s", variable)

# View in logs:
make logs
```

---

## 📝 Code Style Guidelines

### Python Code Style

We use **Black** for formatting:

```python
# Line length: 88 characters
# String quotes: double quotes
# Import organization: isort

# Format before committing:
make format
```

### Naming Conventions

```python
# Classes: PascalCase
class MyClass:
    pass

# Functions/variables: snake_case
def my_function():
    my_variable = 1
    return my_variable

# Constants: UPPER_SNAKE_CASE
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
```

### Documentation

```python
def my_function(arg1: str, arg2: int) -> bool:
    """
    Short description.

    Long description explaining what the function does,
    parameters, return value, and examples.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Description of return value

    Raises:
        ValueError: When X happens
    """
    pass
```

---

## 🔄 Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/my-feature
# or
git checkout -b bugfix/my-bug
```

### 2. Make Changes

```bash
# Edit files, add tests
nano app/func_something.py
nano tests/test_something.py
```

### 3. Test Locally

```bash
make test      # Run tests
make lint      # Check code quality
make format    # Format code
```

### 4. Commit Changes

```bash
make format    # Format first
git add .
git commit -m "Add feature: description"
```

### 5. Push and Create PR

```bash
git push origin feature/my-feature
# Create pull request on GitHub
```

---

## 📚 Module Guide

### `app/func_cointegration.py`

Statistical analysis for cointegration:

- **ADF test** - Augmented Dickey-Fuller test
- **Johansen test** - Cointegration test
- **Z-score calculation** - Mean reversion metric

```python
from backend.app.func_cointegration import calculate_zscore, johansen_test

# Calculate Z-score for pair
z_score = calculate_zscore(series1, series2, hedge_ratio)

# Test cointegration
p_value = johansen_test(series1, series2)
```

### `app/func_bot_agent.py`

Atomic paired position management:

- Opens both positions atomically
- Emergency close if one fails
- State management

```python
from backend.app.func_bot_agent import BotAgent

agent = BotAgent(client, market1, market2, ...)
result = await agent.open_trades()
# result["pair_status"] == "LIVE" or "FAILED"
```

### `backend/main.py`

FastAPI application:

- REST endpoints
- WebSocket support
- Authentication

```python
from backend.main import app

# Access endpoints
GET /api/v1/backtests
POST /api/v1/backtests
GET /docs  # Swagger UI
```

---

## 🔗 Configuration During Development

Edit `app/config.yaml` for development:

```yaml
environment: "development"  # Verbose logging

dydx:
  is_testnet: true          # Use testnet
  dydx_chain_address: "..."
  dydx_secret_phrase: "..."

botSettings:
  findCointegratedPairs: true
  placeTrades: false        # Disable trading during dev
  manageExits: false        # Don't close positions

logging:
  level: "DEBUG"            # Verbose logs
  loki:
    enabled: false          # Don't send to Loki

backtesting:
  candleResolution: "1HOUR"
  maxHistoryDays: 30        # Faster for testing
```

---

## 🚀 Tips & Tricks

### Use VS Code Dev Container

```bash
# Recommended for consistent development environment
make devcontainer

# Inside container:
make install
# All dependencies pre-installed
```

### Hot Module Reload

Both backend and frontend support auto-reload:

```bash
# Backend: auto-reloads on file changes
make backend-run

# Frontend: HMR (Hot Module Replacement)
cd frontend && npm run dev
```

### Database Debugging

```bash
# View database schema
.venv/bin/python -c "from backend.database import Base; print(Base.metadata.tables)"

# Reset database (careful!)
rm instance/db.sqlite3
# Or for PostgreSQL:
# DROP DATABASE bot_db; CREATE DATABASE bot_db;
```

### Skip Tests

```bash
# Run bot without tests
make run

# Skip linting
.venv/bin/python main.py
```

---

## 🆘 Common Issues

### Module Not Found

```bash
# Reinstall in dev mode
.venv/bin/pip install -e .
.venv/bin/pip install -e ./backend
```

### Import Errors

```bash
# Clear Python cache
find . -type d -name __pycache__ -delete
find . -type f -name "*.pyc" -delete

# Reinstall
make install
```

### Port Already in Use

```bash
# Backend (8000)
lsof -ti:8000 | xargs kill -9

# Frontend (5173)
lsof -ti:5173 | xargs kill -9

# Postgres (5432)
lsof -ti:5432 | xargs kill -9
```

### Virtual Environment Issues

```bash
# Rebuild venv
rm -rf .venv
make setup
make install
```

---

## 📖 Code Examples

### Add a New Endpoint

```python
# backend/main.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/api/v1/example")
async def get_example():
    """Get example data."""
    return {"status": "ok"}
```

### Add a New Test

```python
# tests/test_example.py
def test_my_function():
    from app.func_something import my_function
    
    result = my_function("test")
    assert result == "expected"
```

### Add a New Configuration Option

```yaml
# app/config.yaml
myFeature:
  enabled: true
  timeout: 30
```

```python
# app/constants.py
MY_FEATURE_ENABLED = _CONFIG.myFeature.enabled
MY_TIMEOUT = _CONFIG.myFeature.timeout
```

---

## 🎓 Learning Resources

### Code Understanding

1. Start with `app/main.py` - Main entry point
2. Read `app/func_cointegration.py` - Statistical analysis
3. Review `backend/main.py` - API definition
4. Check `app/config.py` - Configuration system

### Documentation

- [Getting Started](./getting-started.md) - Quick setup
- [Architecture Overview](./architecture/system-overview.md) - System design
- [API Reference](./api/core-modules.md) - Module documentation
- [Trading Strategy](./trading/strategy.md) - Strategy explanation

---

## 📊 Performance Optimization

### Profile Code

```bash
# Use cProfile for performance analysis
.venv/bin/python -m cProfile -s cumulative app/main.py
```

### Monitor Backend

```bash
# Check backend performance
curl http://localhost:8000/metrics

# Monitor logs
make logs
```

---

## 🔐 Security Notes

- **Never commit secrets** - Use `.env` or environment variables
- **Use HTTPS in production** - Configure in Nginx/reverse proxy
- **Validate all inputs** - Pydantic handles this in FastAPI
- **Keep dependencies updated** - Run `pip install --upgrade -r requirements.txt`

---

## 🤝 Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

Key points:

- Follow code style (`make format`)
- Add tests for new features
- Update documentation
- Use descriptive commit messages

---

## 🆘 Need Help?

- **Setup issues?** → [Troubleshooting Guide](./guides/troubleshooting.md)
- **Code questions?** → Check existing code and tests
- **Architecture questions?** → [Architecture Overview](./architecture/system-overview.md)
- **API questions?** → [API Reference](./api/core-modules.md)

---

**Last Updated**: October 18, 2025  
**Status**: Development Guide Complete ✅
