#!/usr/bin/env python3
"""Unit test for ConnectionPoolMonitor class functionality."""

import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_connection_pool_monitor_class():
    """Test the ConnectionPoolMonitor class independently."""
    print("🧪 Testing ConnectionPoolMonitor Class...")

    try:
        # Import only the monitor class
        from src.infrastructure.database import ConnectionPoolMonitor
        print("✅ Successfully imported ConnectionPoolMonitor")

        # Test 1: Create monitor instance
        print("\n📊 Test 1: Create Monitor Instance")
        monitor = ConnectionPoolMonitor(
            alert_threshold_percentage=80.0,
            alert_threshold_wait_time=5.0,
            alert_threshold_failure_rate=0.1,
            monitoring_interval_seconds=1,
            metrics_window_size=10
        )
        print("✅ ConnectionPoolMonitor instance created")
        print(f"   - Alert threshold: {monitor.alert_threshold_percentage}%")
        print(f"   - Monitoring interval: {monitor.monitoring_interval_seconds}s")
        print(f"   - Metrics window size: {monitor.metrics_window_size}")

        # Test 2: Test connection failure recording
        print("\n📊 Test 2: Connection Failure Recording")
        test_error = Exception("Connection failed")
        monitor.record_connection_failure(test_error)
        print("✅ Recorded connection failure")

        # Test 3: Test connection timeout recording
        print("\n📊 Test 3: Connection Timeout Recording")
        monitor.record_connection_timeout(10.5)
        print("✅ Recorded connection timeout")

        # Test 4: Test metrics when no pool is attached
        print("\n📊 Test 4: Get Metrics Without Pool")
        metrics = monitor.get_current_metrics()
        print(f"✅ Retrieved metrics: {metrics.get('status', 'unknown')}")
        print(f"   - Monitoring active: {metrics.get('monitoring_active', False)}")

        # Test 5: Test health status without pool
        print("\n📊 Test 5: Get Health Status Without Pool")
        health = monitor.get_health_status()
        print(f"✅ Retrieved health status: {health.get('status', 'unknown')}")

        # Test 6: Test metrics history
        print("\n📊 Test 6: Get Metrics History")
        history = monitor.get_metrics_history(limit=5)
        print(f"✅ Retrieved history: {len(history)} samples")

        print("\n🎉 All ConnectionPoolMonitor class tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_connection_pool_monitor_class()
    sys.exit(0 if success else 1)