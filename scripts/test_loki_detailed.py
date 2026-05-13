#!/usr/bin/env python3
"""
Detailed Loki test with timestamp information
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from logging_setup import setup_logging


def test_detailed_loki():
    """Test Loki with detailed timestamp info"""
    
    print(f"\n🧪 Detailed Loki Test - {datetime.now()}")
    print("=" * 60)
    
    # Setup logging
    setup_logging()
    
    # Get logger
    logger = logging.getLogger("loki_test_detailed")
    
    # Send logs with current timestamp information
    current_time = datetime.now()
    
    print(f"\n📝 Sending logs at: {current_time}")
    print("🔍 Look for these messages in Grafana:")
    
    logger.info(f"🎯 LOKI TEST MESSAGE - {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.warning(f"⚠️  LOKI WARNING TEST - {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.error(f"❌ LOKI ERROR TEST - {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test with extra fields
    logger.info("📊 LOKI STRUCTURED TEST", extra={
        "test_timestamp": current_time.isoformat(),
        "test_type": "detailed_verification",
        "market": "TEST-USD"
    })
    
    print(f"\n✅ Test logs sent at: {current_time}")
    print("\n🔍 In Grafana, try these queries:")
    print('   {app="dydx-trading-bot"}')
    print('   {job="dydx-trading-bot"}')
    print('   {environment="cpdevlabs"}')
    print('   {service="dydx-trading-bot"}')
    print('\n⏰ Make sure your Grafana time range includes:')
    print(f'   {current_time.strftime("%Y-%m-%d %H:%M:%S")}')

if __name__ == "__main__":
    test_detailed_loki()