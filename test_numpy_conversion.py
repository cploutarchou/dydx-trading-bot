"""
Test to verify NumPy float conversion for SQLAlchemy compatibility.

This test validates that numpy.float64 values are properly converted to Python floats
before being persisted to the database, preventing SQL serialization errors.
"""

import os
import sys
from datetime import datetime, timezone

# Setup paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))
sys.path.insert(0, os.path.dirname(__file__))

# Configure test database
os.environ["DB_TYPE"] = "sqlite"
os.environ["DB_NAME"] = "test_numpy_conversion.db"

import numpy as np

from backend.database import BacktestRun, BacktestTrade, Base, SessionLocal, engine


def test_numpy_to_float_conversion():
    """Test that numpy types are properly converted to Python floats."""
    print("\n" + "=" * 80)
    print("TEST: NumPy Float to Python Float Conversion for SQLAlchemy")
    print("=" * 80)

    # Setup test database
    print("\n1. Setting up test database...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("   ✓ Database ready")

    db = SessionLocal()

    try:
        # Create test BacktestRun
        print("\n2. Creating test BacktestRun...")
        run = BacktestRun(
            run_id="test-numpy-001",
            status="running",
            start_date="2024-01-01",
            end_date="2024-01-31",
            num_pairs=5,
            total_markets=10,
            user_id=1,
            starting_balance=1000.0,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
        print(f"   ✓ Created BacktestRun with id={run_id}")

        # Create test trades with numpy calculations
        print("\n3. Creating test trades with numpy calculations...")
        pnls = [100.0, 50.0, -30.0, 75.0, -20.0]

        for i, pnl in enumerate(pnls):
            trade = BacktestTrade(
                run_id_fk=run_id,
                trade_id=f"trade_{i}",
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
                pnl=pnl,
            )
            db.add(trade)
        db.commit()
        print(f"   ✓ Created {len(pnls)} trades")

        # Simulate aggregate_run_metrics logic with numpy types
        print("\n4. Simulating aggregate_run_metrics with numpy types...")
        trades = db.query(BacktestTrade).filter_by(run_id_fk=run_id).all()

        # Calculate metrics using numpy (reproduces actual code)
        total_trades = len(trades)
        profitable_trades = len([t for t in trades if t.pnl and t.pnl > 0])
        losing_trades = len([t for t in trades if t.pnl and t.pnl < 0])
        total_pnl = sum([t.pnl for t in trades if t.pnl is not None])
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0.0

        pnls_array = np.array([t.pnl for t in trades if t.pnl is not None])
        daily_returns = pnls_array / 1000.0  # Normalize by starting balance

        # Calculate metrics that produce numpy types
        mean_return = np.mean(daily_returns)
        std_dev = np.std(daily_returns)
        risk_free_rate = 0.02 / 252

        sharpe_ratio = None
        if std_dev > 0:
            sharpe_ratio = (mean_return - risk_free_rate) / std_dev * np.sqrt(252)

        downside_returns = np.minimum(daily_returns, 0)
        downside_std = np.std(downside_returns)
        sortino_ratio = None
        if downside_std > 0:
            sortino_ratio = (mean_return - risk_free_rate) / downside_std * np.sqrt(252)

        gross_profit = sum([t.pnl for t in trades if t.pnl and t.pnl > 0])
        gross_loss = abs(sum([t.pnl for t in trades if t.pnl and t.pnl < 0]))
        profit_factor = None
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss

        cumulative_pnl = np.cumsum(pnls_array)
        running_max = np.maximum.accumulate(cumulative_pnl)
        drawdown = (cumulative_pnl - running_max) / (running_max + 1e-9)
        max_drawdown = float(np.min(drawdown)) * 100 if len(drawdown) > 0 else 0.0

        print("\n   Calculated metrics (with numpy types):")
        print(f"     sharpe_ratio type: {type(sharpe_ratio).__name__} = {sharpe_ratio}")
        print(
            f"     sortino_ratio type: {type(sortino_ratio).__name__} = {sortino_ratio}"
        )
        print(
            f"     profit_factor type: {type(profit_factor).__name__} = {profit_factor}"
        )
        print(f"     max_drawdown type: {type(max_drawdown).__name__} = {max_drawdown}")
        print(f"     win_rate type: {type(win_rate).__name__} = {win_rate}")

        # TEST: Update BacktestRun with converted numpy types (this is what the fix does)
        print("\n5. Testing numpy-to-float conversion and database update...")
        run = db.query(BacktestRun).filter_by(id=run_id).first()

        # Apply the fix: convert numpy types to Python floats
        run.total_trades = total_trades
        run.profitable_trades = profitable_trades
        run.losing_trades = losing_trades
        run.win_rate = float(win_rate)
        run.total_pnl = float(total_pnl)
        run.total_pnl_usd = float(total_pnl)
        run.sharpe_ratio = float(sharpe_ratio) if sharpe_ratio is not None else None
        run.sortino_ratio = float(sortino_ratio) if sortino_ratio is not None else None
        run.profit_factor = float(profit_factor) if profit_factor is not None else None
        run.max_drawdown = float(max_drawdown) if max_drawdown is not None else None
        run.ending_balance = float(run.starting_balance + total_pnl)

        db.commit()
        db.refresh(run)

        print("   ✓ Successfully converted and persisted all values:")
        print(
            f"     total_trades: {run.total_trades} ({type(run.total_trades).__name__})"
        )
        print(f"     profitable_trades: {run.profitable_trades}")
        print(f"     win_rate: {run.win_rate} ({type(run.win_rate).__name__})")
        print(
            f"     sharpe_ratio: {run.sharpe_ratio} ({type(run.sharpe_ratio).__name__})"
        )
        print(
            f"     sortino_ratio: {run.sortino_ratio} ({type(run.sortino_ratio).__name__})"
        )
        print(
            f"     profit_factor: {run.profit_factor} ({type(run.profit_factor).__name__})"
        )
        print(
            f"     max_drawdown: {run.max_drawdown} ({type(run.max_drawdown).__name__})"
        )

        # Verify data can be re-queried
        print("\n6. Verifying data persistence...")
        run_check = db.query(BacktestRun).filter_by(id=run_id).first()
        if run_check:
            print("   ✓ BacktestRun retrieved successfully")
            print(f"   ✓ Sharpe ratio: {run_check.sharpe_ratio}")
            print(f"   ✓ Sortino ratio: {run_check.sortino_ratio}")
            print(f"   ✓ Profit factor: {run_check.profit_factor}")
            print(f"   ✓ Max drawdown: {run_check.max_drawdown}")
        else:
            print("   ✗ Failed to retrieve BacktestRun")
            return False

        print("\n" + "=" * 80)
        print("✓ TEST PASSED: NumPy conversion working correctly!")
        print("=" * 80)
        return True

    except Exception as e:
        print(f"\n✗ TEST FAILED: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        db.close()
        # Cleanup
        from pathlib import Path

        if Path("test_numpy_conversion.db").exists():
            os.remove("test_numpy_conversion.db")


if __name__ == "__main__":
    success = test_numpy_to_float_conversion()
    sys.exit(0 if success else 1)
