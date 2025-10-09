#!/usr/bin/env python3
"""
Test script to verify real application logs are being sent to Loki
"""
import os
import sys
import time

# Add the app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import logging

from logging_setup import setup_logging


def test_real_logging():
    """Test that real application logs are sent to Loki"""
    print("🧪 Testing real application log sending...")
    
    # Initialize logging
    setup_logging()
    
    # Get logger
    logger = logging.getLogger("test_app")
    
    # Send various test logs that should appear in Grafana
    print("\n📤 Sending test logs...")
    
    logger.info("🚀 TEST LOG 1: Application startup - this should appear in Grafana")
    time.sleep(1)
    
    logger.info("💰 TEST LOG 2: Trading signal detected - BTC-USD pair")
    time.sleep(1)
    
    logger.warning("⚠️  TEST LOG 3: High volatility warning")
    time.sleep(1)
    
    logger.error("❌ TEST LOG 4: Connection timeout error")
    time.sleep(1)
    
    logger.info("📊 TEST LOG 5: Market data received - ETH price: $2500")
    time.sleep(1)
    
    # Test with the exact same logger name as the main app
    main_logger = logging.getLogger("__main__")
    main_logger.info("🎯 TEST LOG 6: Main application log (same logger as main.py)")
    time.sleep(1)
    
    # Test func_public logger (like in the main app)
    public_logger = logging.getLogger("func_public")
    public_logger.info("📈 TEST LOG 7: Extracting prices for TEST token pair")
    time.sleep(1)
    
    print("\n✅ Test logs sent! Check Grafana with these queries:")
    print("   - {job=\"dydx-trading-bot\"} |= \"TEST LOG\"")
    print("   - {app=\"dydx-trading-bot\"} |= \"TEST LOG\"")
    print("   - {job=\"dydx-trading-bot\"} |= \"Trading signal\"")
    print("   - {job=\"dydx-trading-bot\"} |= \"Market data\"")
    print("\n⏳ Wait 30-60 seconds for logs to appear in Grafana...")

if __name__ == "__main__":
    test_real_logging()