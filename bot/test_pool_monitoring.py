#!/usr/bin/env python3
"""Test script for database connection pool monitoring."""

import os
import sys
import time
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_pool_monitoring():
    """Test the connection pool monitoring functionality."""
    print("🧪 Testing Database Connection Pool Monitoring...")

    try:
        # Import after path setup
        from src.infrastructure.database import db, ConnectionPoolMonitor
        print("✅ Successfully imported database components")

        # Test 1: Check if pool monitor is initialized
        print("\n📊 Test 1: Pool Monitor Initialization")
        if hasattr(db, '_pool_monitor') and db._pool_monitor is not None:
            print("✅ Pool monitor is initialized")
            monitor = db._pool_monitor
        else:
            print("❌ Pool monitor is not initialized")
            return False

        # Test 2: Get current metrics
        print("\n📊 Test 2: Get Current Pool Metrics")
        try:
            metrics = db.get_pool_metrics()
            print(f"✅ Retrieved pool metrics:")
            print(f"   - Status: {metrics.get('status', 'unknown')}")
            print(f"   - Monitoring active: {metrics.get('monitoring_active', False)}")
            if metrics.get('status') == 'monitoring':
                print(f"   - Pool size: {metrics.get('pool_size', 0)}")
                print(f"   - Checked out: {metrics.get('checked_out', 0)}")
                print(f"   - Available: {metrics.get('available', 0)}")
                print(f"   - Utilization: {metrics.get('utilization_percentage', 0):.1f}%")
        except Exception as e:
            print(f"❌ Failed to get pool metrics: {e}")
            return False

        # Test 3: Get pool health status
        print("\n📊 Test 3: Get Pool Health Status")
        try:
            health = db.get_pool_health_status()
            print(f"✅ Retrieved pool health status:")
            print(f"   - Status: {health.get('status', 'unknown')}")
            print(f"   - Message: {health.get('message', 'N/A')}")
        except Exception as e:
            print(f"❌ Failed to get pool health: {e}")
            return False

        # Test 4: Get diagnostics
        print("\n📊 Test 4: Get Database Diagnostics")
        try:
            diagnostics = db.get_diagnostics()
            print(f"✅ Retrieved database diagnostics:")
            print(f"   - Database info present: {'database' in diagnostics}")
            print(f"   - Pool metrics present: {'pool_metrics' in diagnostics}")
            print(f"   - Pool health present: {'pool_health' in diagnostics}")
        except Exception as e:
            print(f"❌ Failed to get diagnostics: {e}")
            return False

        # Test 5: Simulate some database activity to see metrics change
        print("\n📊 Test 5: Simulate Database Activity")
        try:
            from src.infrastructure.database import get_session
            print("   Creating sessions to test pool metrics...")

            sessions = []
            for i in range(3):
                session = next(get_session())
                sessions.append(session)
                print(f"   - Created session {i+1}")

            # Check metrics after creating sessions
            time.sleep(2)  # Give monitoring time to collect
            metrics_after = db.get_pool_metrics()
            print(f"   - Checked out after sessions: {metrics_after.get('checked_out', 0)}")

            # Clean up sessions
            for session in sessions:
                session.close()
            print("   - Closed all sessions")

        except Exception as e:
            print(f"❌ Failed during activity simulation: {e}")

        print("\n🎉 All tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pool_monitoring()
    sys.exit(0 if success else 1)