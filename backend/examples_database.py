"""
Database Usage Examples and Documentation.
Demonstrates how to use the Database module with SQLModel for CRUD operations.
"""

from database import Database, get_db
from services.repository import RepositoryRegistry
from models.sqlmodel_models import User, BacktestRun, BacktestStrategy
from db_setup import DatabaseSetup
from datetime import datetime


# ========== INITIALIZATION EXAMPLES ==========

def example_initialization():
    """Examples of initializing the database."""
    
    # Option 1: Initialize local SQLite database
    db = DatabaseSetup.initialize_sqlite_local("dydx_bot.db", echo=False)
    
    # Option 2: Initialize in-memory SQLite (for testing)
    db = DatabaseSetup.initialize_sqlite_memory()
    
    # Option 3: Initialize PostgreSQL from environment variables
    # Set env vars: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
    db = DatabaseSetup.initialize_from_env()
    
    # Option 4: Initialize PostgreSQL with explicit parameters
    db = DatabaseSetup.initialize_postgresql(
        host="localhost",
        port=5432,
        database="dydx_bot",
        user="postgres",
        password="your_password",
        ssl=False
    )


# ========== BASIC CRUD OPERATIONS ==========

def example_create_user():
    """Create a new user."""
    with Database.session_context() as session:
        user = RepositoryRegistry.users.create(
            session,
            User,
            username="alice",
            email="alice@example.com",
            hashed_password="hashed_pwd_123",
            full_name="Alice Smith",
            is_active=True
        )
        session.commit()
        print(f"Created user: {user.username} (ID: {user.id})")
        return user.id


def example_get_user():
    """Retrieve a user by ID."""
    with Database.session_context() as session:
        user = RepositoryRegistry.users.get_by_id(session, User, user_id=1)
        if user:
            print(f"Found user: {user.username} - {user.email}")
        else:
            print("User not found")


def example_get_user_by_username():
    """Find user by username."""
    with Database.session_context() as session:
        user = RepositoryRegistry.users.get_by_username(session, "alice")
        if user:
            print(f"User: {user.username}, Email: {user.email}")


def example_update_user():
    """Update a user."""
    with Database.session_context() as session:
        user = RepositoryRegistry.users.update(
            session,
            User,
            obj_id=1,
            full_name="Alice Johnson",
            is_active=True
        )
        session.commit()
        if user:
            print(f"Updated user: {user.full_name}")


def example_delete_user():
    """Delete a user."""
    with Database.session_context() as session:
        success = RepositoryRegistry.users.delete(session, User, obj_id=1)
        session.commit()
        if success:
            print("User deleted")


def example_list_users():
    """List all active users with pagination."""
    with Database.session_context() as session:
        users = RepositoryRegistry.users.get_all(
            session,
            User,
            skip=0,
            limit=10,
            is_active=True
        )
        for user in users:
            print(f"- {user.username} ({user.email})")


# ========== BACKTEST OPERATIONS ==========

def example_create_backtest_run():
    """Create a backtest run."""
    with Database.session_context() as session:
        run = RepositoryRegistry.backtest_runs.create(
            session,
            BacktestRun,
            run_id="run_20241027_001",
            status="completed",
            start_date="2024-10-01",
            end_date="2024-10-27",
            num_pairs=5,
            total_markets=10,
            user_id=1,
            strategy_id=1,
            total_trades=50,
            profitable_trades=35,
            losing_trades=15,
            win_rate=0.70,
            total_pnl=1250.50,
            sharpe_ratio=1.85
        )
        session.commit()
        print(f"Created backtest run: {run.run_id}")
        return run.id


def example_get_backtest_runs_for_user():
    """Get all backtest runs for a user."""
    with Database.session_context() as session:
        runs = RepositoryRegistry.backtest_runs.get_by_user(
            session,
            user_id=1,
            skip=0,
            limit=20
        )
        for run in runs:
            print(f"- {run.run_id}: {run.status} ({run.total_trades} trades, {run.total_pnl} PnL)")


def example_get_best_results():
    """Get best backtest results from a run."""
    with Database.session_context() as session:
        results = RepositoryRegistry.backtest_results.get_best_results(
            session,
            run_id=1,
            limit=10
        )
        for result in results:
            print(f"- {result.market_1}/{result.market_2}: ${result.pnl_usd:.2f} PnL")


# ========== STRATEGY OPERATIONS ==========

def example_create_strategy():
    """Create a backtest strategy."""
    with Database.session_context() as session:
        strategy = RepositoryRegistry.backtest_strategies.create(
            session,
            BacktestStrategy,
            name="Mean Reversion V1",
            description="Basic mean reversion strategy",
            category="cointegration",
            user_id=1,
            is_public=False,
            zscore_threshold=2.0,
            stats_window=21,
            max_half_life=24.0,
            usd_per_trade=100.0,
            transaction_fee=0.0005,
            slippage=0.001,
            starting_balance=10000.0
        )
        session.commit()
        print(f"Created strategy: {strategy.name} (ID: {strategy.id})")
        return strategy.id


def example_get_user_strategies():
    """Get all strategies for a user."""
    with Database.session_context() as session:
        strategies = RepositoryRegistry.backtest_strategies.get_by_user(
            session,
            user_id=1
        )
        for strat in strategies:
            print(f"- {strat.name}: {strat.category} (zscore_threshold: {strat.zscore_threshold})")


# ========== TRANSACTION EXAMPLES ==========

def example_transaction_with_error_handling():
    """Example of transaction with error handling."""
    try:
        with Database.session_context() as session:
            # Create strategy
            strategy = RepositoryRegistry.backtest_strategies.create(
                session,
                BacktestStrategy,
                name="Test Strategy",
                user_id=1,
                zscore_threshold=2.0,
                stats_window=21,
                max_half_life=24.0,
                usd_per_trade=100.0,
                transaction_fee=0.0005,
                slippage=0.001,
                starting_balance=10000.0
            )
            
            # Create backtest run
            run = RepositoryRegistry.backtest_runs.create(
                session,
                BacktestRun,
                run_id=f"run_{strategy.id}_{datetime.now().timestamp()}",
                status="running",
                start_date="2024-10-01",
                end_date="2024-10-27",
                num_pairs=5,
                total_markets=10,
                user_id=1,
                strategy_id=strategy.id
            )
            
            session.commit()
            print(f"Created strategy {strategy.id} and run {run.id}")
            
    except Exception as e:
        print(f"Transaction failed: {e}")
        # Transaction automatically rolled back by context manager


# ========== AUDIT LOG EXAMPLES ==========

def example_audit_log():
    """Example of creating audit logs."""
    with Database.session_context() as session:
        # Log user action
        RepositoryRegistry.audit_logs.log_action(
            session,
            user_id=1,
            action="create_strategy",
            resource_type="backtest_strategy",
            resource_id="123",
            details={"name": "My Strategy", "version": "1.0"},
            status="success",
            ip_address="192.168.1.1"
        )
        session.commit()
        print("Audit log created")


# ========== FASTAPI DEPENDENCY INJECTION ==========

def example_fastapi_usage():
    """
    Example of using the database with FastAPI.
    
    from fastapi import FastAPI, Depends
    from database import get_db
    from sqlalchemy.orm import Session
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
            raise HTTPException(status_code=404, detail="User not found")
        return user
    
    @app.post("/users/")
    def create_user(username: str, email: str, db: Session = Depends(get_db)):
        user = RepositoryRegistry.users.create(
            db, User,
            username=username,
            email=email,
            hashed_password="hashed"
        )
        return user
    """
    pass


# ========== DATABASE HEALTH CHECK ==========

def example_health_check():
    """Check database connection health."""
    db = Database()
    is_healthy = db.health_check()
    
    if is_healthy:
        print("✓ Database is healthy and responsive")
    else:
        print("✗ Database connection failed")


# ========== DATABASE INFO ==========

def example_get_database_info():
    """Get information about current database."""
    db = Database()
    config = db.get_config()
    
    print(f"Database Type: {config.type}")
    if db.is_postgresql():
        print(f"Connection: {config.user}@{config.host}:{config.port}/{config.dbname}")
    elif db.is_sqlite():
        print(f"Database File: {config.dbname}")


# ========== MAIN EXAMPLE RUNNER ==========

if __name__ == "__main__":
    # Initialize database
    print("Initializing database...")
    db = DatabaseSetup.initialize_sqlite_local("dydx_bot_example.db", echo=False)
    
    print("\n" + "="*60)
    print("DATABASE EXAMPLES")
    print("="*60)
    
    # User examples
    print("\n1. Creating user...")
    user_id = example_create_user()
    
    print("\n2. Retrieving user...")
    example_get_user()
    
    print("\n3. Getting user by username...")
    example_get_user_by_username()
    
    print("\n4. Updating user...")
    example_update_user()
    
    print("\n5. Listing users...")
    example_list_users()
    
    # Strategy examples
    print("\n6. Creating strategy...")
    strategy_id = example_create_strategy()
    
    print("\n7. Getting user strategies...")
    example_get_user_strategies()
    
    # Backtest examples
    print("\n8. Creating backtest run...")
    run_id = example_create_backtest_run()
    
    print("\n9. Getting backtest runs for user...")
    example_get_backtest_runs_for_user()
    
    # Audit examples
    print("\n10. Creating audit log...")
    example_audit_log()
    
    # Health check
    print("\n11. Database health check...")
    example_health_check()
    
    # Database info
    print("\n12. Database information...")
    example_get_database_info()
    
    print("\n" + "="*60)
    print("✓ All examples completed successfully!")
    print("="*60)
