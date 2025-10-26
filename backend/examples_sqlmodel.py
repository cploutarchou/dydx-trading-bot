"""
SQLModel Examples and Quick Start Guide
Demonstrates usage of SQLModel database service layer.
"""

from datetime import datetime, timezone
from db_sqlmodel import (
    DatabaseSession, 
    create_user, get_user, get_users, update_user, delete_user,
    create_dydx_key, get_dydx_keys_by_user, get_dydx_key_by_network,
    create_dydx_key_settings, get_dydx_key_settings,
    create_backtest_run, get_backtest_run, get_backtest_runs_by_user,
    create_backtest_result, get_backtest_results_by_run,
    create_backtest_candle, get_candles_by_run_id, get_markets_by_run_id,
    create_audit_log, get_audit_logs_by_user,
    create_backtest_strategy, get_user_strategies,
)


def example_user_operations():
    """Example: User CRUD operations with Pydantic validation."""
    print("\n" + "="*70)
    print("USER OPERATIONS")
    print("="*70)
    
    with DatabaseSession() as session:
        # Create user (with automatic Pydantic validation)
        user_data = {
            "username": "alice",
            "email": "alice@example.com",
            "hashed_password": "hashed_pwd_123",
            "full_name": "Alice Trader"
        }
        user = create_user(session, user_data)
        print(f"✅ Created user: {user.username} (ID: {user.id})")
        
        # Get user by ID
        retrieved_user = get_user(session, id=user.id)
        print(f"✅ Retrieved user: {retrieved_user.username}")
        
        # Update user
        updated_user = update_user(session, user.id, {"full_name": "Alice Updated"})
        print(f"✅ Updated user: {updated_user.full_name}")
        
        # Get all users
        all_users = get_users(session, limit=10)
        print(f"✅ Found {len(all_users)} users")


def example_dydx_operations():
    """Example: DYdX keys and settings."""
    print("\n" + "="*70)
    print("DYdX KEYS OPERATIONS")
    print("="*70)
    
    with DatabaseSession() as session:
        # Create user first
        user = create_user(session, {
            "username": "trader_bob",
            "email": "bob@example.com",
            "hashed_password": "hash"
        })
        
        # Create DYdX key
        key_data = {
            "user_id": user.id,
            "network": "testnet",
            "chain_address": "0x123abc...",
            "encrypted_secret": "encrypted_key_data"
        }
        key = create_dydx_key(session, key_data)
        print(f"✅ Created DYdX key: {key.network} (ID: {key.id})")
        
        # Get user's keys
        keys = get_dydx_keys_by_user(session, user.id)
        print(f"✅ Found {len(keys)} DYdX keys for user")
        
        # Get key by network
        testnet_key = get_dydx_key_by_network(session, user.id, "testnet")
        print(f"✅ Retrieved testnet key: {testnet_key.chain_address}")
        
        # Create DYdX key settings
        settings_data = {
            "user_id": user.id,
            "default_network": "testnet",
            "auto_switch_testnet": True
        }
        settings = create_dydx_key_settings(session, settings_data)
        print(f"✅ Created DYdX settings: default_network={settings.default_network}")


def example_backtest_operations():
    """Example: Backtest runs, results, and candles."""
    print("\n" + "="*70)
    print("BACKTEST OPERATIONS")
    print("="*70)
    
    with DatabaseSession() as session:
        # Create user and strategy
        user = create_user(session, {
            "username": "analyst",
            "email": "analyst@example.com",
            "hashed_password": "hash"
        })
        
        strategy = create_backtest_strategy(session, {
            "user_id": user.id,
            "name": "Conservative Strategy",
            "zscore_threshold": 2.0,
            "category": "conservative"
        })
        print(f"✅ Created strategy: {strategy.name}")
        
        # Create backtest run
        run_data = {
            "run_id": "bt_20250101_001",
            "user_id": user.id,
            "strategy_id": strategy.id,
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "num_pairs": 10,
            "total_markets": 20
        }
        run = create_backtest_run(session, run_data)
        print(f"✅ Created backtest run: {run.run_id}")
        
        # Create backtest results
        result_data = {
            "run_id_fk": run.id,
            "market_1": "BTC-USD",
            "market_2": "ETH-USD",
            "total_trades": 25,
            "pnl": 2500.50
        }
        result = create_backtest_result(session, result_data)
        print(f"✅ Created result: {result.market_1} vs {result.market_2}")
        
        # Add candles (OHLCV data)
        from datetime import timedelta
        base_time = datetime.now(timezone.utc)
        for i in range(10):
            candle_data = {
                "run_id_fk": run.id,
                "market": "BTC-USD",
                "timestamp": base_time + timedelta(hours=i),
                "open_price": 100.0 + i,
                "high_price": 110.0 + i,
                "low_price": 95.0 + i,
                "close_price": 105.0 + i,
                "volume": 1000000 + i*100
            }
            create_backtest_candle(session, candle_data)
        
        # ⭐ Get candles by run ID
        candles = get_candles_by_run_id(session, run.id)
        print(f"✅ Retrieved {len(candles)} candles for run")
        
        # ⭐ Get unique markets
        markets = get_markets_by_run_id(session, run.id)
        print(f"✅ Markets in run: {', '.join(markets)}")


def example_audit_logging():
    """Example: Audit logging."""
    print("\n" + "="*70)
    print("AUDIT LOGGING")
    print("="*70)
    
    with DatabaseSession() as session:
        user = create_user(session, {
            "username": "security_admin",
            "email": "admin@example.com",
            "hashed_password": "hash"
        })
        
        # Create audit logs
        log_data = {
            "user_id": user.id,
            "action": "login",
            "resource_type": "user",
            "ip_address": "192.168.1.1"
        }
        log = create_audit_log(session, log_data)
        print(f"✅ Created audit log: {log.action}")
        
        # Get user's audit logs
        logs = get_audit_logs_by_user(session, user.id)
        print(f"✅ Found {len(logs)} audit logs")


def example_pydantic_validation():
    """Example: Automatic Pydantic validation."""
    print("\n" + "="*70)
    print("PYDANTIC VALIDATION")
    print("="*70)
    
    with DatabaseSession() as session:
        try:
            # This will fail validation (username too short would fail max_length)
            invalid_data = {
                "username": "x" * 51,  # Exceeds max_length of 50
                "email": "test@example.com",
                "hashed_password": "hash"
            }
            # SQLModel will raise validation error automatically
            user = create_user(session, invalid_data)
        except ValueError as e:
            print(f"✅ Validation error caught: {str(e)[:80]}...")
        
        # Valid user
        valid_data = {
            "username": "valid_user",
            "email": "valid@example.com",
            "hashed_password": "hash"
        }
        user = create_user(session, valid_data)
        print(f"✅ User created with valid data: {user.username}")


def run_all_examples():
    """Run all examples."""
    print("\n" + "🚀 "*35)
    print("SQLModel Examples - Quick Start Guide")
    print("🚀 "*35)
    
    try:
        example_user_operations()
        example_dydx_operations()
        example_backtest_operations()
        example_audit_logging()
        example_pydantic_validation()
        
        print("\n" + "✅ "*35)
        print("All examples completed successfully!")
        print("✅ "*35 + "\n")
    except Exception as e:
        print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    run_all_examples()
