"""
Database Integration Template for FastAPI Application.
Shows how to integrate the database module into main.py
"""

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from db_setup import DatabaseSetup
from database import Database, get_db
from services.repository import RepositoryRegistry
from models.sqlmodel_models import User, BacktestRun, BacktestStrategy

# Initialize FastAPI app
app = FastAPI(
    title="dYdX Trading Bot API",
    description="Trading bot with backtesting and strategy management",
    version="1.0.0"
)


# ========== Lifecycle Events ==========

@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    print("Starting up application...")
    
    # Initialize database from environment variables
    try:
        DatabaseSetup.initialize_from_env(echo=False)
        print("✓ Database initialized successfully")
        
        # Verify database is healthy
        if not Database.health_check():
            print("✗ Database health check failed!")
            raise RuntimeError("Database connection failed")
        print("✓ Database health check passed")
        
    except Exception as e:
        print(f"✗ Failed to initialize database: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    print("Shutting down application...")
    # Connection pool will be cleaned up automatically


# ========== Root Endpoint ==========

@app.get("/")
async def root():
    """Root endpoint with database status."""
    try:
        db = Database()
        config = db.get_config()
        return {
            "status": "ok",
            "database": {
                "type": config.type,
                "connected": db.health_check()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== User Endpoints ==========

@app.get("/api/users/{user_id}", response_model=dict)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get a specific user by ID."""
    user = RepositoryRegistry.users.get_by_id(db, User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.__dict__


@app.get("/api/users", response_model=List[dict])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """List users with pagination."""
    if active_only:
        users = RepositoryRegistry.users.get_active_users(db)
    else:
        users = RepositoryRegistry.users.get_all(db, User, skip=skip, limit=limit)
    return [u.__dict__ for u in users]


@app.get("/api/users/username/{username}", response_model=dict)
async def get_user_by_username(username: str, db: Session = Depends(get_db)):
    """Get user by username."""
    user = RepositoryRegistry.users.get_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.__dict__


@app.post("/api/users", response_model=dict)
async def create_user(
    username: str,
    email: str,
    hashed_password: str,
    full_name: str = None,
    db: Session = Depends(get_db)
):
    """Create a new user."""
    # Check if user already exists
    if RepositoryRegistry.users.get_by_username(db, username):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    if RepositoryRegistry.users.get_by_email(db, email):
        raise HTTPException(status_code=400, detail="Email already exists")
    
    user = RepositoryRegistry.users.create(
        db, User,
        username=username,
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        is_active=True
    )
    return user.__dict__


# ========== Backtest Strategy Endpoints ==========

@app.get("/api/strategies/{strategy_id}", response_model=dict)
async def get_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """Get a strategy by ID."""
    strategy = RepositoryRegistry.backtest_strategies.get_by_id(
        db, BacktestStrategy, strategy_id
    )
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy.__dict__


@app.get("/api/users/{user_id}/strategies", response_model=List[dict])
async def get_user_strategies(user_id: int, db: Session = Depends(get_db)):
    """Get all strategies for a user."""
    strategies = RepositoryRegistry.backtest_strategies.get_by_user(db, user_id)
    return [s.__dict__ for s in strategies]


@app.get("/api/strategies/public", response_model=List[dict])
async def get_public_strategies(db: Session = Depends(get_db)):
    """Get all public strategies."""
    strategies = RepositoryRegistry.backtest_strategies.get_public_strategies(db)
    return [s.__dict__ for s in strategies]


# ========== Backtest Run Endpoints ==========

@app.get("/api/backtests/{run_id}", response_model=dict)
async def get_backtest_run(run_id: str, db: Session = Depends(get_db)):
    """Get a backtest run by run_id."""
    run = RepositoryRegistry.backtest_runs.get_by_run_id(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return run.__dict__


@app.get("/api/users/{user_id}/backtests", response_model=List[dict])
async def get_user_backtests(
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get backtest runs for a user."""
    runs = RepositoryRegistry.backtest_runs.get_by_user(
        db, user_id, skip=skip, limit=limit
    )
    return [r.__dict__ for r in runs]


@app.get("/api/backtests/status/{status}", response_model=List[dict])
async def get_backtests_by_status(status: str, db: Session = Depends(get_db)):
    """Get backtest runs by status."""
    runs = RepositoryRegistry.backtest_runs.get_by_status(db, status)
    return [r.__dict__ for r in runs]


# ========== Backtest Results Endpoints ==========

@app.get("/api/backtests/{run_id}/results", response_model=List[dict])
async def get_backtest_results(run_id: int, db: Session = Depends(get_db)):
    """Get all results for a backtest run."""
    results = RepositoryRegistry.backtest_results.get_by_run(db, run_id)
    return [r.__dict__ for r in results]


@app.get("/api/backtests/{run_id}/best-results", response_model=List[dict])
async def get_best_backtest_results(
    run_id: int,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get best results from a backtest run."""
    results = RepositoryRegistry.backtest_results.get_best_results(
        db, run_id, limit=limit
    )
    return [r.__dict__ for r in results]


# ========== Health and Diagnostics ==========

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    db = Database()
    is_healthy = db.health_check()
    
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "database": is_healthy
    }


@app.get("/api/debug/database-info", response_model=dict)
async def database_info():
    """Get database information (debug endpoint)."""
    db = Database()
    config = db.get_config()
    
    return {
        "type": config.type,
        "host": config.host if config.type == "postgresql" else "N/A",
        "port": config.port if config.type == "postgresql" else "N/A",
        "database": config.dbname,
        "pool_size": config.pool_size,
        "max_overflow": config.max_overflow,
        "healthy": db.health_check()
    }


# ========== Error Handlers ==========

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return {
        "error": exc.detail,
        "status_code": exc.status_code
    }


# ========== Usage Instructions ==========

"""
SETUP INSTRUCTIONS:

1. Set environment variables:
   export DB_TYPE=postgresql
   export DB_HOST=localhost
   export DB_PORT=5432
   export DB_NAME=dydx_bot
   export DB_USER=postgres
   export DB_PASSWORD=your_password

   Or for local development:
   export DB_TYPE=sqlite
   export DB_NAME=dydx_bot.db

2. Run the application:
   uvicorn main:app --reload

3. API will be available at:
   http://localhost:8000/docs (Swagger UI)
   http://localhost:8000/redoc (ReDoc)

EXAMPLE REQUESTS:

# Check health
curl http://localhost:8000/health

# Create user
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","email":"alice@example.com","hashed_password":"hash123"}'

# List users
curl http://localhost:8000/api/users

# Get user by username
curl http://localhost:8000/api/users/username/alice

# Get user backtest runs
curl http://localhost:8000/api/users/1/backtests

# Get backtest results
curl http://localhost:8000/api/backtests/1/results

# Get best results from backtest
curl http://localhost:8000/api/backtests/1/best-results?limit=10

# Database info (debug)
curl http://localhost:8000/api/debug/database-info
"""

if __name__ == "__main__":
    import uvicorn
    
    # Run the application
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
