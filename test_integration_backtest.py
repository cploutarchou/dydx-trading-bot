"""
Integration test for BacktestPosition and BacktestTrade saves during actual backtesting.

This test simulates the exact scenario that was causing foreign key constraint violations:
1. Create a BacktestRun in one session (like the FastAPI route handler)
2. Pass the run_id to background task with a different session
3. Attempt to save positions and trades from the background task
4. Verify all data is saved correctly

This test validates the fix for: https://github.com/dydx-trading-bot/issues/XXX
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Setup paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))
sys.path.insert(0, os.path.dirname(__file__))

# Configure test database
os.environ["DB_TYPE"] = "sqlite"
os.environ["DB_NAME"] = "test_integration_backtest.db"

from backend.backtest_helpers import save_backtest_position, save_backtest_trade
from backend.database import BacktestRun, Base, SessionLocal, engine


def test_backtest_background_task_scenario():
    """
    Simulate the exact scenario from the backtesting workflow:

    1. Route handler creates BacktestRun in session A
    2. Background task gets the run_id
    3. Background task opens session B
    4. Background task saves positions/trades using session B
    5. Verify data integrity
    """
    print("\n" + "=" * 80)
    print("INTEGRATION TEST: BacktestRun with Multiple Database Sessions")
    print("=" * 80)

    # Setup test database
    print("\n1. Setting up test database...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("   ✓ Database ready")

    # ========== PHASE 1: Route Handler Creates BacktestRun ==========
    print("\n2. PHASE 1: Route handler creates BacktestRun (Session A)...")
    session_a = SessionLocal()
    try:
        # Simulate route handler
        run = BacktestRun(
            run_id="backtest-integration-001",
            status="running",
            start_date="2024-01-01",
            end_date="2024-01-31",
            num_pairs=5,
            total_markets=10,
            user_id=1,
            config={"strategy": "test"},
        )
        session_a.add(run)
        session_a.commit()
        session_a.refresh(run)
        run_id_from_route = run.id
        print(f"   ✓ Created BacktestRun with id={run_id_from_route}")
        print(f"   ✓ Run ID stored in database: {run.run_id}")
    finally:
        session_a.close()

    # ========== PHASE 2: Background Task Saves Data ==========
    print("\n3. PHASE 2: Background task saves positions/trades (Session B)...")
    print(f"   Using run_id={run_id_from_route} from different session")

    session_b = SessionLocal()
    saved_positions = []
    saved_trades = []

    try:
        # Simulate background task saving multiple positions
        print("\n   Saving positions from background task...")
        for i in range(3):
            market_1 = ["BTC-USD", "ETH-USD", "SOL-USD"][i]
            market_2 = ["ETH-USD", "BNB-USD", "ADA-USD"][i]

            position = save_backtest_position(
                db=session_b,
                run_id=run_id_from_route,
                market_1=market_1,
                market_2=market_2,
                status="OPEN",
                entry_timestamp=datetime.now(tz=timezone.utc),
                entry_price_1=45000.0 + (i * 1000),
                entry_price_2=2500.0 + (i * 100),
                entry_z_score=1.5 + (i * 0.1),
                size_1=0.01 + (i * 0.001),
                size_2=0.2 + (i * 0.01),
                side_1="BUY" if i % 2 == 0 else "SELL",
                side_2="SELL" if i % 2 == 0 else "BUY",
                hedge_ratio=0.05 + (i * 0.01),
            )
            saved_positions.append(position)
            print(f"     ✓ Saved position {i + 1}/3: {market_1}/{market_2}")

        # Simulate background task saving multiple trades
        print("\n   Saving trades from background task...")
        for i in range(2):
            market_1 = ["BTC-USD", "ETH-USD"][i]
            market_2 = ["ETH-USD", "BNB-USD"][i]

            trade = save_backtest_trade(
                db=session_b,
                run_id=run_id_from_route,
                market_1=market_1,
                market_2=market_2,
                entry_timestamp=datetime.now(tz=timezone.utc),
                entry_price_1=45000.0 + (i * 1000),
                entry_price_2=2500.0 + (i * 100),
                entry_z_score=1.5,
                side_1="BUY",
                side_2="SELL",
                size_1=0.01,
                size_2=0.2,
                hedge_ratio=0.05,
                transaction_fee=0.0005,
                slippage=0.001,
                exit_timestamp=datetime.now(tz=timezone.utc),
                exit_price_1=44900.0 + (i * 1000),
                exit_price_2=2480.0 + (i * 100),
                exit_z_score=0.5,
                pnl=125.50 + (i * 50),
                pnl_pct=1.25 + (i * 0.2),
                duration_hours=2.5 + (i * 0.5),
            )
            saved_trades.append(trade)
            print(f"     ✓ Saved trade {i + 1}/2: {market_1}/{market_2}")

    finally:
        session_b.close()

    # ========== PHASE 3: Verification ==========
    print("\n4. PHASE 3: Verify data persistence (Session C)...")
    session_c = SessionLocal()

    try:
        from backend.database import BacktestPosition, BacktestTrade

        # Verify BacktestRun still exists
        run_check = session_c.query(BacktestRun).filter_by(id=run_id_from_route).first()
        if run_check:
            print(f"   ✓ BacktestRun found: {run_check.run_id}")
        else:
            print("   ✗ BacktestRun NOT found!")
            return False

        # Verify positions were saved
        positions = (
            session_c.query(BacktestPosition)
            .filter_by(run_id_fk=run_id_from_route)
            .all()
        )
        print(f"   ✓ Found {len(positions)} saved positions")
        if len(positions) != 3:
            print(f"   ✗ Expected 3 positions, got {len(positions)}")
            return False

        # Verify trades were saved
        trades = (
            session_c.query(BacktestTrade).filter_by(run_id_fk=run_id_from_route).all()
        )
        print(f"   ✓ Found {len(trades)} saved trades")
        if len(trades) != 2:
            print(f"   ✗ Expected 2 trades, got {len(trades)}")
            return False

        # Verify position data integrity
        print("\n   Verifying position data integrity...")
        for i, pos in enumerate(positions):
            print(
                f"     Position {i + 1}: {pos.market_1}/{pos.market_2} "
                f"Status={pos.status} Zscore={pos.entry_z_score:.2f}"
            )
            if not pos.market_1 or not pos.market_2:
                print("     ✗ Missing market data!")
                return False

        # Verify trade data integrity
        print("\n   Verifying trade data integrity...")
        for i, trade in enumerate(trades):
            pnl_pct = trade.pnl_pct or 0
            print(
                f"     Trade {i + 1}: {trade.market_1}/{trade.market_2} "
                f"PnL=${trade.pnl:.2f} ({pnl_pct:.1f}%) Duration={trade.duration_hours:.1f}h"
            )
            if not trade.market_1 or not trade.market_2:
                print("     ✗ Missing market data!")
                return False

        print("\n" + "=" * 80)
        print("✓ INTEGRATION TEST PASSED!")
        print("=" * 80)
        print("\nSummary:")
        print(f"  • Created BacktestRun: {run_check.run_id}")
        print(f"  • Saved positions: {len(positions)}")
        print(f"  • Saved trades: {len(trades)}")
        print(f"  • Total database records: {len(positions) + len(trades) + 1}")
        print("\nTest validates that:")
        print("  ✓ Multiple sessions can save related records")
        print("  ✓ Foreign key constraints are properly respected")
        print("  ✓ Data persists correctly across sessions")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"\n✗ VERIFICATION FAILED: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        session_c.close()
        # Cleanup
        if Path("test_integration_backtest.db").exists():
            os.remove("test_integration_backtest.db")


if __name__ == "__main__":
    try:
        success = test_backtest_background_task_scenario()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
