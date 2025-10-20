#!/usr/bin/env python
"""
Test script to verify the market column size fix for BacktestCandle.

This test validates that:
1. Long market names (>50 chars) can be stored in the database
2. The migration was applied successfully
3. Candle data persists correctly
"""

import logging
import sys
from datetime import datetime, timezone

# Setup path
sys.path.insert(0, "/home/chris/workspace/dydx-trading-bot")

from sqlalchemy import text

from backend.database import BacktestCandle, BacktestRun, SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_market_column_size():
    """Test that market column can store long market names."""
    print("\n" + "=" * 70)
    print("TEST: Market Column Size Fix for BacktestCandle")
    print("=" * 70)

    # Test data with long market names
    test_cases = [
        ("BTC-USD", "Standard market name (7 chars)"),
        ("ETHEREUM-PERP", "Medium market name (14 chars)"),
        (
            "FARTCOIN,RAYDIUM,9BB6NFECJBCTNNLFKO2FQVQBQ8HHM13KCYYCDQBGPUMP-USD",
            "Long composite market (61 chars) - Original error case",
        ),
        ("A" * 200 + "-USD", "Maximum safe length (204 chars)"),
    ]

    session = SessionLocal()
    try:
        # 1. Check column definition
        print("\n1. Verifying column definition...")
        inspector_query = """
        SELECT column_name, data_type, character_maximum_length 
        FROM information_schema.columns 
        WHERE table_name='backtest_candles' AND column_name='market'
        """
        result = session.execute(text(inspector_query)).first()
        if result:
            col_name, data_type, max_length = result
            print(f"   ✓ Column: {col_name}")
            print(f"   ✓ Type: {data_type}")
            print(f"   ✓ Max Length: {max_length} characters")

            if max_length >= 255:
                print("   ✓ Column size is sufficient (>= 255)")
            else:
                print(f"   ✗ ERROR: Column size is {max_length}, expected >= 255")
                return False
        else:
            print("   ✗ ERROR: Could not find market column")
            return False

        # 2. Create test backtest run
        print("\n2. Creating test BacktestRun...")
        test_run = BacktestRun(
            run_id="test_market_column_fix",
            start_date="2025-01-01",
            end_date="2025-01-31",
            num_pairs=1,
            total_markets=1,
            config={},
            status="RUNNING",
        )
        session.add(test_run)
        session.commit()
        print(f"   ✓ Created BacktestRun with id={test_run.id}")

        # 3. Test each market name
        print("\n3. Testing market name storage...")
        for market_name, description in test_cases:
            try:
                candle = BacktestCandle(
                    run_id_fk=test_run.id,
                    market=market_name,
                    timestamp=datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
                    resolution="1HOUR",
                    open_price=100.0,
                    high_price=105.0,
                    low_price=95.0,
                    close_price=102.0,
                    volume=1000.0,
                )
                session.add(candle)
                session.commit()

                # Verify it was stored
                retrieved = (
                    session.query(BacktestCandle)
                    .filter(BacktestCandle.market == market_name)
                    .first()
                )

                if retrieved:
                    print(f"   ✓ {description}")
                    print(
                        f"      Stored: '{market_name[:50]}{'...' if len(market_name) > 50 else ''}' ({len(market_name)} chars)"
                    )
                else:
                    print(f"   ✗ Failed to retrieve: {description}")
                    return False

            except Exception as e:
                print(f"   ✗ ERROR storing {description}: {str(e)}")
                return False

        # 4. Verify data integrity
        print("\n4. Verifying data integrity...")
        count = (
            session.query(BacktestCandle)
            .filter(BacktestCandle.run_id_fk == test_run.id)
            .count()
        )
        expected = len(test_cases)
        if count == expected:
            print(f"   ✓ All {count} candles stored and retrieved successfully")
        else:
            print(f"   ✗ Expected {expected} candles, found {count}")
            return False

        print("\n" + "=" * 70)
        print("✓ TEST PASSED: Market column size fix is working correctly!")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"\n✗ TEST FAILED: {str(e)}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        # Cleanup
        try:
            session.query(BacktestCandle).filter(
                BacktestCandle.run_id_fk == test_run.id
            ).delete()
            session.query(BacktestRun).filter(BacktestRun.id == test_run.id).delete()
            session.commit()
            print("\n✓ Cleanup completed")
        except Exception:  # noqa: E722
            pass
        finally:
            session.close()


if __name__ == "__main__":
    success = test_market_column_size()
    sys.exit(0 if success else 1)
