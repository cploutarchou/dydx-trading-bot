# dYdX Trading Bot - AI Coding Agent Instructions

## System Architecture Overview

This is a **multi-instance API-controlled trading bot** with secure credential management and comprehensive analytics. The system uses a **microservice-like pattern** with distinct API layers, background bot processes, and shared database persistence.

### Core Components

- **API Server (`bot_api_server.py`)** - FastAPI REST API for controlling multiple bot instances
- **Bot Instance Manager (`bot_instance_manager.py`)** - Manages multiple isolated bot processes
- **Main Trading Logic (`main.py`)** - Core trading loop with cointegration detection
- **Database Layer** - SQLAlchemy models for bots, trades, jobs, and events
- **Configuration System (`config.py`)** - Environment-driven configuration with dataclasses

### Data Flow Pattern

```
API Request → Bot Manager → Bot Process → dYdX Client → Database
```

Bot instances run as **separate processes** managed by the API, not threads. Each bot has isolated configuration and state stored in `bot_states/instances.json`.

## Critical Development Patterns

### 1. Environment Configuration

**ALWAYS load environment first:**
```python
from dotenv import load_dotenv
load_dotenv()  # MUST be before other imports
```

Configuration uses **dataclass pattern** in `config.py`. All settings come from environment variables with defaults. Never hardcode credentials.

### 2. Database Models Structure

Three distinct model sets:
- **Core Models (`models.py`)** - Bot instances, jobs, trades, events
- **Backtest Models (`models_backtest.py`)** - Historical analysis data  
- **Realtime Models (`models_realtime.py`)** - Live trading positions and market data

Use **Unit of Work pattern** for database operations:
```python
session = db.get_session()
uow = UnitOfWork(session)
bot = uow.bots.get_by_instance_id(instance_id)
```

### 3. Bot Lifecycle Management

Bots have **distinct states**: CREATED → STARTING → RUNNING → STOPPING → STOPPED. Use `BotInstanceManager` for all bot operations, never manage processes directly.

```python
# Correct pattern
result = await bot_manager.create_instance(config)
await bot_manager.start_instance(instance_id)

# Wrong - never do direct process management
subprocess.Popen(["python", "main.py"])  # ❌
```

### 4. API Response Pattern

All endpoints use **standardized response wrapper**:
```python
return api_response(
    success=True,
    data=result.model_dump(),
    message="Operation successful"
)
```

### 5. Authentication Architecture

JWT-based auth with **2FA support**. Routes use dependency injection:
```python
async def endpoint(current_user: User = Depends(get_current_active_user)):
```

## Essential Development Commands

### Quick Start Development
```bash
# Setup environment (run once)
make setup
make init-env  # Edit docker/.env afterwards

# Development workflow
make dev          # Start with hot reload
make shell        # Access container shell
make logs-api     # Monitor API logs
make db-shell     # Database access
```

### Testing Patterns
```bash
make test         # Run full test suite
make test-auth    # Test authentication
make health       # Check all services
```

### Database Operations
```bash
# Migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Backup/restore
make db-backup
make db-reset     # ⚠️ Destroys all data
```

## Integration Points

### 1. dYdX Client Connection
Always use `func_connections.py` → `connect_dydx()`. Handles testnet/mainnet switching and jurisdiction checks. Supports **backtesting mode** with `wallet=None`.

### 2. Trading Strategy Integration
Core trading flow in `main.py` follows **flag-based control**:
- `ABORT_ALL_POSITIONS` - Close existing positions
- `FIND_COINTEGRATED` - Run pair analysis
- `MANAGE_EXITS` - Handle position exits  
- `PLACE_TRADES` - Open new positions

### 3. Telegram Integration
Use `func_messaging.py` → `TelegramMessenger` for notifications. Handles startup, error, and shutdown messages automatically.

### 4. Cointegration Analysis
`func_cointegration.py` implements **statistical arbitrage** using:
- Half-life mean reversion analysis
- Z-score threshold detection
- Confidence scoring for pair selection

## Security Considerations

### Credential Encryption
- **All wallet credentials encrypted** using Fernet (AES 128)
- Key stored in `CREDENTIALS_ENCRYPTION_KEY` environment variable
- Use `service_dydx_credentials.py` for secure credential operations

### Environment Security
```bash
# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Never commit .env files
# Use different keys for testnet/mainnet
```

## Common Pitfalls to Avoid

1. **Import Order** - Always load environment variables before other imports
2. **Process Management** - Use BotInstanceManager, never direct subprocess calls  
3. **Database Sessions** - Always close sessions in finally blocks or use context managers
4. **Configuration** - Never hardcode settings, use environment variables
5. **Error Handling** - Use structured logging and Telegram notifications for critical errors

## File Structure Conventions

```
bot/
├── main.py              # Primary bot trading logic
├── bot_api_server.py    # REST API server
├── config.py            # Configuration management
├── constants.py         # Trading parameters from config
├── func_*.py            # Trading function modules
├── models*.py           # Database models (core/backtest/realtime)  
├── service_*.py         # Business logic services
├── routes_*.py          # API route handlers
└── docs/                # Comprehensive documentation
```

## Debugging and Monitoring

### Log Levels
Uses **structured logging** with optional Loki integration. Set `LOG_LEVEL=DEBUG` for verbose output.

### Real-time Monitoring
- WebSocket endpoints for live position updates
- Health checks at `/health` and `/api/v1/system/status`
- Comprehensive metrics in database and API responses

When modifying this system, always consider **multi-instance implications** and maintain **backwards compatibility** with existing bot processes.