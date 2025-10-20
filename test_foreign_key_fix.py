"""
Test script to verify foreign key constraint fix for BacktestPosition and BacktestTrade.

This test validates that:
1. save_backtest_position validates run_id exists before inserting
2. save_backtest_trade validates run_id exists before inserting
3. Proper error messages are raised for invalid run_id values
4. Valid positions and trades are saved successfully
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))
sys.path.insert(0, os.path.dirname(__file__))

# Configure test database
os.environ["DB_TYPE"] = "sqlite"
os.environ["DB_NAME"] = "test_backtest.db"

from backend.backtest_helpers import save_backtest_position, save_backtest_trade
from backend.database import BacktestRun, Base, SessionLocal, engine


def test_foreign_key_validation():
    """Test that foreign key validation prevents orphaned references."""
    print("\n" + "=" * 80)
    print("TEST: Foreign Key Validation for BacktestPosition and BacktestTrade")
    print("=" * 80)

    # Create test database
    print("\n1. Setting up test database...")
    Base.metadata.drop_all(bind=engine)  # Clean slate
    Base.metadata.create_all(bind=engine)
    print("   ✓ Database tables created")

    db = SessionLocal()

    try:
        # TEST 1: Attempt to insert position with non-existent run_id
        print("\n2. TEST: Insert position with invalid run_id (should fail)...")
        invalid_run_id = 9999
        try:
            save_backtest_position(
                db=db,
                run_id=invalid_run_id,
                market_1="BTC-USD",
                market_2="ETH-USD",
                status="OPEN",
                entry_timestamp=datetime.now(tz=timezone.utc),
                entry_price_1=45000.0,
                entry_price_2=2500.0,
                entry_z_score=1.5,
                size_1=0.01,
                size_2=0.2,
                side_1="BUY",
                side_2="SELL",
                hedge_ratio=0.05,
            )
            print("   ✗ FAILED: Should have raised ValueError for invalid run_id")
            return False
        except ValueError as e:
            print(f"   ✓ PASSED: Correctly raised ValueError: {e}")
        except Exception as e:
            print(f"   ✗ FAILED: Raised unexpected exception: {type(e).__name__}: {e}")
            return False

        # TEST 2: Create a valid BacktestRun
        print("\n3. Creating valid BacktestRun for testing...")
        run = BacktestRun(
            run_id="test-run-001",
            status="running",
            start_date="2024-01-01",
            end_date="2024-01-31",
            num_pairs=5,
            total_markets=10,
            user_id=1,
            config={},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        valid_run_id = run.id
        print(f"   ✓ Created BacktestRun with id={valid_run_id}")

        # TEST 3: Insert position with valid run_id (should succeed)
        print(
            f"\n4. TEST: Insert position with valid run_id={valid_run_id} (should succeed)..."
        )
        try:
            position = save_backtest_position(
                db=db,
                run_id=valid_run_id,
                market_1="BTC-USD",
                market_2="ETH-USD",
                status="OPEN",
                entry_timestamp=datetime.now(tz=timezone.utc),
                entry_price_1=45000.0,
                entry_price_2=2500.0,
                entry_z_score=1.5,
                size_1=0.01,
                size_2=0.2,
                side_1="BUY",
                side_2="SELL",
                hedge_ratio=0.05,
            )
            print(f"   ✓ PASSED: Position saved successfully with id={position.id}")
        except Exception as e:
            print(
                f"   ✗ FAILED: Should have succeeded but raised {type(e).__name__}: {e}"
            )
            return False

        # TEST 4: Insert trade with valid run_id (should succeed)
        print(
            f"\n5. TEST: Insert trade with valid run_id={valid_run_id} (should succeed)..."
        )
        try:
            trade = save_backtest_trade(
                db=db,
                run_id=valid_run_id,
                market_1="BTC-USD",
                market_2="ETH-USD",
                entry_timestamp=datetime.now(tz=timezone.utc),
                entry_price_1=45000.0,
                entry_price_2=2500.0,
                entry_z_score=1.5,
                side_1="BUY",
                side_2="SELL",
                size_1=0.01,
                size_2=0.2,
                hedge_ratio=0.05,
                transaction_fee=0.0005,
                slippage=0.001,
                exit_timestamp=datetime.now(tz=timezone.utc),
                exit_price_1=44950.0,
                exit_price_2=2490.0,
                exit_z_score=0.5,
                pnl=125.50,
                pnl_pct=1.25,
                duration_hours=2.5,
            )
            print(f"   ✓ PASSED: Trade saved successfully with id={trade.id}")
        except Exception as e:
            print(
                f"   ✗ FAILED: Should have succeeded but raised {type(e).__name__}: {e}"
            )
            return False

        # TEST 5: Attempt trade with non-existent run_id
        print("\n6. TEST: Insert trade with invalid run_id (should fail)...")
        try:
            save_backtest_trade(
                db=db,
                run_id=invalid_run_id,
                market_1="BTC-USD",
                market_2="ETH-USD",
                entry_timestamp=datetime.now(tz=timezone.utc),
                entry_price_1=45000.0,
                entry_price_2=2500.0,
                entry_z_score=1.5,
                side_1="BUY",
                side_2="SELL",
                size_1=0.01,
                size_2=0.2,
                hedge_ratio=0.05,
                transaction_fee=0.0005,
                slippage=0.001,
            )
            print("   ✗ FAILED: Should have raised ValueError for invalid run_id")
            return False
        except ValueError as e:
            print(f"   ✓ PASSED: Correctly raised ValueError: {e}")
        except Exception as e:
            print(f"   ✗ FAILED: Raised unexpected exception: {type(e).__name__}: {e}")
            return False

        # TEST 6: Verify data in database
        print("\n7. TEST: Verify saved data in database...")
        from backend.database import BacktestPosition, BacktestTrade

        position_count = (
            db.query(BacktestPosition).filter_by(run_id_fk=valid_run_id).count()
        )
        trade_count = db.query(BacktestTrade).filter_by(run_id_fk=valid_run_id).count()
        print(f"   ✓ Found {position_count} position(s) for run_id={valid_run_id}")
        print(f"   ✓ Found {trade_count} trade(s) for run_id={valid_run_id}")

        if position_count >= 1 and trade_count >= 1:
            print("   ✓ PASSED: Data verification successful")
        else:
            print("   ✗ FAILED: Expected at least 1 position and 1 trade")
            return False

        print("\n" + "=" * 80)
        print("✓ ALL TESTS PASSED!")
        print("=" * 80)
        return True

    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        db.close()
        # Clean up test database
        if Path("test_backtest.db").exists():
            os.remove("test_backtest.db")


if __name__ == "__main__":
    success = test_foreign_key_validation()
    sys.exit(0 if success else 1)
