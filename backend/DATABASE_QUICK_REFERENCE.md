# Database Module - Quick Reference Guide

## 🚀 Quick Start (30 seconds)

### 1. Initialize Database
```python
from db_setup import DatabaseSetup

# Local SQLite (development)
db = DatabaseSetup.initialize_sqlite_local("dydx_bot.db")

# Or PostgreSQL (production)
db = DatabaseSetup.initialize_from_env()
```

### 2. Use Repositories
```python
from database import Database
from services.repository import RepositoryRegistry

with Database.session_context() as session:
    # Create
    user = RepositoryRegistry.users.create(
        session, User,
        username="alice",
        email="alice@example.com",
        hashed_password="hash123"
    )
    
    # Read
    user = RepositoryRegistry.users.get_by_username(session, "alice")
    
    # Update
    RepositoryRegistry.users.update(session, User, user.id, full_name="Alice Smith")
    
    # Delete
    RepositoryRegistry.users.delete(session, User, user.id)
```

### 3. With FastAPI
```python
from fastapi import FastAPI, Depends
from database import Database, get_db
from db_setup import DatabaseSetup

app = FastAPI()

@app.on_event("startup")
def startup():
    DatabaseSetup.initialize_from_env()

@app.get("/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    return RepositoryRegistry.users.get_by_id(db, User, user_id)
```

## 📋 Available Repositories

```python
RepositoryRegistry.users                      # User management
RepositoryRegistry.dydx_keys                  # API keys
RepositoryRegistry.dydx_key_settings          # Key settings
RepositoryRegistry.backtest_strategies        # Strategies
RepositoryRegistry.backtest_runs              # Backtest runs
RepositoryRegistry.backtest_results           # Per-pair results
RepositoryRegistry.backtest_candles           # OHLCV data
RepositoryRegistry.backtest_trades            # Trades
RepositoryRegistry.backtest_logs              # Execution logs
RepositoryRegistry.backtest_positions         # Positions
RepositoryRegistry.backtest_comparisons       # Run comparisons
RepositoryRegistry.trade_logs                 # Trade history
RepositoryRegistry.audit_logs                 # Audit trail
RepositoryRegistry.bot_settings               # Configuration
RepositoryRegistry.redis_settings             # Redis config
RepositoryRegistry.strategy_version_history   # Version history
RepositoryRegistry.strategy_execution_state   # Execution state
```

## 🔧 Configuration

### Environment Variables
```bash
DB_TYPE=postgresql              # or "sqlite"
DB_HOST=localhost
DB_PORT=5432
DB_NAME=dydx_bot
DB_USER=postgres
DB_PASSWORD=your_password
DB_SSL=false
DB_MAX_CONNECTIONS=10
DB_POOL_SIZE=5
```

### Or Use Config Object
```python
from config.config import DatabaseSettings

config = DatabaseSettings(
    type="postgresql",
    host="localhost",
    port=5432,
    dbname="dydx_bot",
    user="postgres",
    password="password"
)
db = DatabaseSetup.initialize_from_config(config)
```

## 💾 Common Operations

### Users
```python
# Get by username
user = RepositoryRegistry.users.get_by_username(session, "alice")

# Get by email
user = RepositoryRegistry.users.get_by_email(session, "alice@example.com")

# Get all active users
users = RepositoryRegistry.users.get_active_users(session)

# Get all admins
admins = RepositoryRegistry.users.get_admin_users(session)
```

### Backtest Runs
```python
# Get by run_id
run = RepositoryRegistry.backtest_runs.get_by_run_id(session, "run_123")

# Get by user with pagination
runs = RepositoryRegistry.backtest_runs.get_by_user(
    session, user_id=1, skip=0, limit=50
)

# Get by status
runs = RepositoryRegistry.backtest_runs.get_by_status(session, "completed")

# Count total runs
count = RepositoryRegistry.backtest_runs.count_by_user(session, user_id=1)
```

### Backtest Results
```python
# Get all results for a run
results = RepositoryRegistry.backtest_results.get_by_run(session, run_id=1)

# Get best results sorted by PnL
best = RepositoryRegistry.backtest_results.get_best_results(
    session, run_id=1, limit=10
)

# Get specific market pair result
result = RepositoryRegistry.backtest_results.get_by_market_pair(
    session, run_id=1, market_1="BTC-USD", market_2="ETH-USD"
)
```

### Strategies
```python
# Get user's strategies
strategies = RepositoryRegistry.backtest_strategies.get_by_user(
    session, user_id=1
)

# Get public strategies
public = RepositoryRegistry.backtest_strategies.get_public_strategies(session)

# Get default strategy
default = RepositoryRegistry.backtest_strategies.get_default_strategy(session)

# Soft delete strategy
RepositoryRegistry.backtest_strategies.soft_delete(session, strategy_id=1)
```

### Audit Logs
```python
# Get user's audit logs
logs = RepositoryRegistry.audit_logs.get_by_user(session, user_id=1, limit=100)

# Get logs for a resource
logs = RepositoryRegistry.audit_logs.get_by_resource(
    session, resource_type="backtest_run", resource_id="123"
)

# Create audit log
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

## ✔️ Session Context Manager

### Best Practice (Always Use This)
```python
with Database.session_context() as session:
    # Do work
    user = RepositoryRegistry.users.get_by_id(session, User, 1)
    
# Auto-commit on success, auto-rollback on error
```

### Key Benefits
- ✅ Automatic commit on success
- ✅ Automatic rollback on error
- ✅ Automatic session cleanup
- ✅ Simple error handling

## 🔍 Health Checks

```python
# Check database health
is_healthy = Database.health_check()

if not is_healthy:
    print("Database connection failed!")

# Get database config
config = Database.get_config()
print(f"Using {config.type} database")

# Check database type
if Database.is_postgresql():
    print("Using PostgreSQL")
elif Database.is_sqlite():
    print("Using SQLite")
```

## 🛠️ CLI Tools

```bash
# Initialize
python db_setup.py init-local           # Local SQLite
python db_setup.py init-memory          # In-memory (testing)
python db_setup.py init-postgres        # PostgreSQL

# Manage
python db_setup.py health               # Check connection
python db_setup.py info                 # Show database info
python db_setup.py create-tables        # Create tables
python db_setup.py drop-tables          # Drop all tables
python db_setup.py reset                # Reset database
```

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| `DATABASE_MODULE.md` | Complete guide with examples |
| `DATABASE_SUMMARY.md` | Implementation overview |
| `DATABASE_CHECKLIST.md` | Detailed checklist |
| `examples_database.py` | Runnable code examples |
| `main_database_template.py` | FastAPI integration template |

## 🎯 Common Tasks

### Task: Add a New User
```python
with Database.session_context() as session:
    user = RepositoryRegistry.users.create(
        session, User,
        username="bob",
        email="bob@example.com",
        hashed_password="hashed_pwd",
        is_active=True
    )
    print(f"Created user: {user.username} (ID: {user.id})")
```

### Task: Get User's Backtest Runs
```python
with Database.session_context() as session:
    runs = RepositoryRegistry.backtest_runs.get_by_user(
        session, user_id=1, skip=0, limit=50
    )
    for run in runs:
        print(f"{run.run_id}: {run.status} ({run.total_pnl} PnL)")
```

### Task: Find Best Strategy
```python
with Database.session_context() as session:
    results = RepositoryRegistry.backtest_results.get_best_results(
        session, run_id=1, limit=10
    )
    for result in results:
        print(f"{result.market_1}/{result.market_2}: ${result.pnl_usd}")
```

### Task: Log User Action
```python
with Database.session_context() as session:
    RepositoryRegistry.audit_logs.log_action(
        session,
        user_id=1,
        action="created_strategy",
        resource_type="backtest_strategy",
        resource_id="123",
        details={"name": "My Strategy"},
        status="success"
    )
```

## 🚨 Error Handling

```python
try:
    with Database.session_context() as session:
        user = RepositoryRegistry.users.create(
            session, User,
            username="test",
            email="test@example.com",
            hashed_password="hash"
        )
except Exception as e:
    print(f"Error: {e}")
    # Transaction automatically rolled back
```

## 💡 Tips & Tricks

1. **Always use context manager** for automatic transaction handling
2. **Use repositories** instead of raw queries for consistency
3. **Initialize database once** at application startup
4. **Check health** on startup to catch connection issues early
5. **Use FastAPI Depends** for automatic session injection
6. **Paginate** large result sets for better performance
7. **Log actions** via audit logs for compliance

## 📊 Database Support

| Database | Use Case |
|----------|----------|
| SQLite local | Development, prototyping |
| SQLite memory | Unit testing |
| PostgreSQL | Production |

## 🔗 Related Files

- Models: `/backend/models/sqlmodel_models.py`
- Config: `/backend/config/config.py`
- Services: `/backend/services/`

---

**Everything is ready to use. Start with the quick start above!** 🚀
