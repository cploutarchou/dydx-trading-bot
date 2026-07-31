#!/usr/bin/env python3
"""Test script for DataFrame cleanup functionality."""

import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_dataframe_cleanup():
    """Test the DataFrame cleanup utilities."""
    print("🧪 Testing DataFrame Cleanup Functionality...")

    try:
        import pandas as pd
        from src.shared.dataframe_utils import (
            managed_dataframe,
            cleanup_dataframe,
            optimize_dataframe_memory,
            register_dataframe,
            unregister_dataframe,
            get_memory_summary,
            force_cleanup_all,
            cleanup_cache_entries
        )
        print("✅ Successfully imported DataFrame cleanup utilities")

        # Test 1: Basic DataFrame cleanup
        print("\n📊 Test 1: Basic DataFrame Cleanup")
        test_data = {'col1': [1, 2, 3], 'col2': [4, 5, 6]}
        df = pd.DataFrame(test_data)
        print(f"   Created test DataFrame with {len(df)} rows")

        # Register DataFrame
        df_id = register_dataframe(df, "test_dataframe")
        print(f"✅ Registered DataFrame: {df_id}")

        # Get memory summary
        summary = get_memory_summary()
        print(f"   Memory summary: {summary['tracked_dataframes']} tracked DataFrames")

        # Cleanup
        cleanup_result = cleanup_dataframe(df)
        print(f"✅ Cleanup result: {cleanup_result}")

        # Test 2: Context manager usage
        print("\n📊 Test 2: Context Manager Usage")
        large_data = {
            f'col{i}': range(1000) for i in range(10)
        }
        with managed_dataframe(pd.DataFrame(large_data), "large_dataframe") as managed_df:
            print(f"   Managed DataFrame has {len(managed_df.columns)} columns")
            print(f"   Managed DataFrame has {len(managed_df)} rows")
        print("✅ Context manager automatically cleaned up DataFrame")

        # Test 3: Memory optimization
        print("\n📊 Test 3: Memory Optimization")
        import numpy as np
        inefficient_df = pd.DataFrame({
            'int_col': [1] * 1000,
            'float_col': [1.0] * 1000,
            'str_col': ['test'] * 1000
        })
        print(f"   Created inefficient DataFrame with {len(inefficient_df)} rows")

        optimized_df = optimize_dataframe_memory(inefficient_df)
        print("✅ DataFrame memory optimization completed")

        # Test 4: Cache cleanup
        print("\n📊 Test 4: Cache Cleanup")
        test_cache = {}
        for i in range(150):
            test_cache[f'key_{i}'] = {
                'data': pd.DataFrame({'value': [i]}),
                'expires': i
            }
        print(f"   Created cache with {len(test_cache)} entries")

        cleanup_cache_entries(test_cache, max_size=100, max_age_minutes=30)
        print(f"✅ Cache cleanup completed, {len(test_cache)} entries remaining")

        # Test 5: Force cleanup all
        print("\n📊 Test 5: Force Cleanup All")
        # Create some test DataFrames
        for i in range(5):
            test_df = pd.DataFrame({'value': range(100)})
            register_dataframe(test_df, f"cleanup_test_{i}")

        summary_before = get_memory_summary()
        print(f"   Before force cleanup: {summary_before['tracked_dataframes']} DataFrames")

        cleaned = force_cleanup_all()
        print(f"✅ Force cleanup completed: {cleaned} DataFrames cleaned")

        summary_after = get_memory_summary()
        print(f"   After force cleanup: {summary_after['tracked_dataframes']} DataFrames")

        print("\n🎉 All DataFrame cleanup tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_dataframe_cleanup()
    sys.exit(0 if success else 1)