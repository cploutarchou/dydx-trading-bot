# Database Module - Complete Documentation

## Overview

The database module provides a unified interface for working with both **SQLite** (local development/testing) and **PostgreSQL** (production) databases using SQLModel and SQLAlchemy ORM.

## Architecture

```
┌─────────────────────────────────────────┐
│      Your Application Code              │
│   (FastAPI, scripts, services)          │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│   Repository Layer                      │
│   (RepositoryRegistry + Repositories)   │
│   - UserRepository                      │
│   - BacktestRunRepository               │
│   - StrategyRepository                  │
│   └── RepositoryRegistry (registry)     │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│   Database Module                       │
│   - Connection Management               │
│   - Session Handling                    │
│   - CRUD Base Operations                │
│   - Health Checks                       │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│   SQLAlchemy Core                       │
│   - Connection Pooling                  │
│   - Transaction Management              │
│   - Query Building                      │
└──────────────────┬──────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
    ┌────────┐         ┌────────────┐
    │ SQLite │         │ PostgreSQL │
    │ (Local)│         │ (Production)
    └────────┘         └────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `database.py` | Core database connection and session management |
| `services/repository.py` | CRUD repository layer for all models |
| `db_setup.py` | Database initialization utilities and CLI |
| `examples_database.py` | Usage examples and documentation |

## Configuration

Database configuration is stored in `config/config.py` in the `DatabaseSettings` dataclass:

```python
@dataclass
class DatabaseSettings:
    type: str = "postgresql"  # "sqlite" or "postgresql"
    host: str = "localhost"
    port: int = 5432
    dbname: str = "dydx_bot"
    user: str = "dydx_bot"
    password: str = ""
    ssl: bool = False
    timeout: int = 5
    max_connections: int = 10
    pool_size: int = 5
    max_overflow: int = 10
```

### Environment Variables

```bash
# Database type
DB_TYPE=postgresql              # or "sqlite"

# Common
DB_NAME=dydx_bot               # DB name or SQLite file path
DB_TIMEOUT=5

# PostgreSQL only
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password
DB_SSL=false
DB_MAX_CONNECTIONS=10
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
```

## Quick Start

### 1. Initialize Database

```python
from db_setup import DatabaseSetup

# Option A: Local SQLite
db = DatabaseSetup.initialize_sqlite_local("dydx_bot.db")

# Option B: In-memory SQLite (testing)
db = DatabaseSetup.initialize_sqlite_memory()

# Option C: PostgreSQL from environment
db = DatabaseSetup.initialize_from_env()

# Option D: PostgreSQL with explicit parameters
db = DatabaseSetup.initialize_postgresql(
    host="localhost",
    port=5432,
    database="dydx_bot",
    user="postgres",
    password="your_password"
)
```

### 2. Use the Database

```python
from database import Database
from services.repository import RepositoryRegistry
from models.sqlmodel_models import User

# Get session with context manager (auto-commit/rollback)
with Database.session_context() as session:
    # Create user
    user = RepositoryRegistry.users.create(
        session,
        User,
        username="alice",
        email="alice@example.com",
        hashed_password="hash123"
    )
    
    # Get user
    user = RepositoryRegistry.users.get_by_username(session, "alice")
    
    # Update user
    RepositoryRegistry.users.update(session, User, user.id, full_name="Alice Smith")
    
    # Delete user
    RepositoryRegistry.users.delete(session, User, user.id)
    
    # Auto-commit on success, auto-rollback on error
```

## Core Components

### Database Class (Singleton)

The main database connection manager:

```python
class Database:
    # Initialize database
    Database.initialize(config, echo=False)
    
    # Get/create session
    session = Database.get_session()
    
    # Context manager for safe session handling
    with Database.session_context() as session:
        ...  # Do work
    
    # Get engine
    engine = Database.get_engine()
    
    # Check database health
    is_healthy = Database.health_check()
    
    # Reset database (drop all tables)
    Database.reset_database()
    
    # Get configuration
    config = Database.get_config()
    
    # Check database type
    is_postgres = Database.is_postgresql()
    is_sqlite = Database.is_sqlite()
```

### CRUDBase Class

Base CRUD operations for all models:

```python
class CRUDBase:
    # Create
    obj = CRUDBase.create(session, Model, field1=value1, field2=value2)
    
    # Read
    obj = CRUDBase.get_by_id(session, Model, 123)
    objs = CRUDBase.get_all(session, Model, skip=0, limit=100, active=True)
    
    # Update
    obj = CRUDBase.update(session, Model, 123, field1=new_value)
    
    # Delete
    success = CRUDBase.delete(session, Model, 123)
    count = CRUDBase.delete_all(session, Model, active=False)
    
    # Query
    count = CRUDBase.count(session, Model, active=True)
    exists = CRUDBase.exists(session, Model, username="alice")
```

### Repository Classes

Specialized repositories for each model with domain-specific queries:

```python
# Users
RepositoryRegistry.users.get_by_username(session, "alice")
RepositoryRegistry.users.get_by_email(session, "alice@example.com")
RepositoryRegistry.users.get_active_users(session)

# Backtest Runs
RepositoryRegistry.backtest_runs.get_by_run_id(session, "run_123")
RepositoryRegistry.backtest_runs.get_by_user(session, user_id=1, skip=0, limit=20)
RepositoryRegistry.backtest_runs.get_by_status(session, "completed")

# Backtest Results
RepositoryRegistry.backtest_results.get_by_run(session, run_id=1)
RepositoryRegistry.backtest_results.get_best_results(session, run_id=1, limit=10)

# Strategies
RepositoryRegistry.backtest_strategies.get_by_user(session, user_id=1)
RepositoryRegistry.backtest_strategies.get_public_strategies(session)

# And more...
```

## Usage Examples

### Basic CRUD

```python
from database import Database
from services.repository import RepositoryRegistry
from models.sqlmodel_models import User

# Create
with Database.session_context() as session:
    user = RepositoryRegistry.users.create(
        session, User,
        username="bob",
        email="bob@example.com",
        hashed_password="hashed",
        is_active=True
    )
    print(f"Created user ID: {user.id}")

# Read
with Database.session_context() as session:
    user = RepositoryRegistry.users.get_by_id(session, User, 1)
    print(f"User: {user.username}")

# Update
with Database.session_context() as session:
    RepositoryRegistry.users.update(
        session, User, 1,
        full_name="Bob Smith"
    )

# Delete
with Database.session_context() as session:
    RepositoryRegistry.users.delete(session, User, 1)
```

### Complex Queries

```python
with Database.session_context() as session:
    # Get user's backtest runs
    runs = RepositoryRegistry.backtest_runs.get_by_user(
        session, user_id=1, skip=0, limit=50
    )
    
    # Get best results from a run
    results = RepositoryRegistry.backtest_results.get_best_results(
        session, run_id=1, limit=10
    )
    
    # Get open positions in a run
    positions = RepositoryRegistry.backtest_positions.get_open_positions(
        session, run_id=1
    )
    
    # Log audit event
    RepositoryRegistry.audit_logs.log_action(
        session,
        user_id=1,
        action="create_strategy",
        resource_type="backtest_strategy",
        resource_id="123",
        status="success",
        ip_address="127.0.0.1"
    )
```

### FastAPI Integration

```python
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database import get_db, Database
from db_setup import DatabaseSetup
from services.repository import RepositoryRegistry
from models.sqlmodel_models import User

app = FastAPI()

@app.on_event("startup")
def startup():
    DatabaseSetup.initialize_from_env(echo=False)

@app.get("/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = RepositoryRegistry.users.get_by_id(db, User, user_id)
    if not user:
        raise HTTPException(status_code=404)
    return user

@app.post("/users/")
def create_user(username: str, email: str, db: Session = Depends(get_db)):
    return RepositoryRegistry.users.create(
        db, User,
        username=username,
        email=email,
        hashed_password="placeholder"
    )
```

### Error Handling with Transactions

```python
try:
    with Database.session_context() as session:
        # Create related objects
        strategy = RepositoryRegistry.backtest_strategies.create(
            session, BacktestStrategy, ...
        )
        run = RepositoryRegistry.backtest_runs.create(
            session, BacktestRun,
            strategy_id=strategy.id, ...
        )
        # If any error occurs, entire transaction rolls back automatically
except Exception as e:
    print(f"Transaction failed: {e}")
    # No manual rollback needed - context manager handles it
```

## CLI Commands

```bash
# Initialize databases
python db_setup.py init-local                 # SQLite local
python db_setup.py init-memory                # SQLite in-memory
python db_setup.py init-postgres              # PostgreSQL (uses env vars)

# Database operations
python db_setup.py health                     # Check connection
python db_setup.py info                       # Show database info
python db_setup.py create-tables              # Create all tables
python db_setup.py drop-tables                # Drop all tables
python db_setup.py reset                      # Reset database
```

## Environment Setup Example

### Local Development (SQLite)

```bash
export DB_TYPE=sqlite
export DB_NAME=dydx_bot.db
```

### Production (PostgreSQL)

```bash
export DB_TYPE=postgresql
export DB_HOST=db.example.com
export DB_PORT=5432
export DB_NAME=dydx_bot
export DB_USER=postgres
export DB_PASSWORD=your_secure_password
export DB_SSL=true
export DB_MAX_CONNECTIONS=20
export DB_POOL_SIZE=10
```

## Features

✅ **Dual Database Support** - SQLite for local development, PostgreSQL for production  
✅ **Connection Pooling** - Automatic connection management  
✅ **Transaction Management** - Automatic commit/rollback  
✅ **Health Checks** - Verify database connectivity  
✅ **Type Safety** - Full type hints with SQLModel  
✅ **CRUD Operations** - Base CRUD class for all models  
✅ **Specialized Repositories** - Domain-specific query methods  
✅ **Error Handling** - Comprehensive error handling  
✅ **FastAPI Integration** - Easy dependency injection  
✅ **CLI Tools** - Database management from command line  
✅ **Singleton Pattern** - One database instance across application  
✅ **Environment Configuration** - 12-factor app compliant  

## Best Practices

1. **Always use context managers** for sessions:
   ```python
   with Database.session_context() as session:
       # Do work
   # Auto-commit on success, auto-rollback on error
   ```

2. **Use repositories for queries**:
   ```python
   # Good - domain-specific, reusable
   users = RepositoryRegistry.users.get_by_username(session, "alice")
   
   # Avoid - raw queries
   users = session.query(User).filter(User.username == "alice").all()
   ```

3. **Initialize database once at startup**:
   ```python
   @app.on_event("startup")
   def startup():
       DatabaseSetup.initialize_from_env()
   ```

4. **Use FastAPI dependency injection**:
   ```python
   @app.get("/users/{user_id}")
   def get_user(user_id: int, db: Session = Depends(get_db)):
       # Session is automatically managed
   ```

5. **Check database health on startup**:
   ```python
   if not Database.health_check():
       raise RuntimeError("Database unavailable")
   ```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Database not initialized" | Call `Database.initialize()` or `DatabaseSetup.initialize_*()` |
| Connection timeout | Increase `DB_TIMEOUT`, check network/firewall |
| PostgreSQL auth failed | Check `DB_USER`, `DB_PASSWORD`, `DB_HOST` |
| SQLite file locked | Ensure only one process is accessing the database |
| Out of connections | Increase `DB_MAX_CONNECTIONS` and `DB_POOL_SIZE` |

---

**Status**: ✅ **Complete and production-ready**

For examples, see `examples_database.py`
