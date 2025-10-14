#!/usr/bin/env python3
"""
Test script using ONLY custom Loki implementation (bypassing logging_loki)
"""
import os
import sys
import time

# Add the app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import logging

from constants import LOKI_LABELS, LOKI_PASSWORD, LOKI_PUSH_URL, LOKI_USERNAME
from logging_setup import create_loki_fallback_handler


def test_custom_loki():
    """Test using ONLY the custom Loki implementation"""
    print("🧪 Testing CUSTOM Loki implementation (bypassing logging_loki)...")
    
    # Set up basic logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    
    # Create ONLY the custom handler
    custom_handler = create_loki_fallback_handler(
        LOKI_PUSH_URL, 
        LOKI_USERNAME, 
        LOKI_PASSWORD, 
        LOKI_LABELS or {}
    )
    
    # Add to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(custom_handler)
    
    print("\n📤 Sending test logs via CUSTOM implementation...")
    
    # Test various loggers
    test_logger = logging.getLogger("custom_test")
    test_logger.info("🔧 CUSTOM TEST 1: Using fallback Loki handler")
    time.sleep(2)
    
    test_logger.info("💎 CUSTOM TEST 2: Direct Loki send - BTC price analysis")
    time.sleep(2)
    
    test_logger.warning("⚠️  CUSTOM TEST 3: Custom handler warning message")
    time.sleep(2)
    
    test_logger.error("❌ CUSTOM TEST 4: Custom handler error message")
    time.sleep(2)
    
    # Test with app-like logger names
    main_logger = logging.getLogger("__main__")
    main_logger.info("🎯 CUSTOM TEST 5: Main app logger via custom handler")
    time.sleep(2)
    
    public_logger = logging.getLogger("func_public")
    public_logger.info("📊 CUSTOM TEST 6: Extracting prices via custom handler")
    time.sleep(2)
    
    print("\n✅ Custom implementation test complete!")
    print("🔍 Check Grafana for logs with labels:")
    print(f"   - Labels: {LOKI_LABELS}")
    print("   - Query: {job=\"dydx-trading-bot\"} |= \"CUSTOM TEST\"")
    print("\n⏳ Wait 30-60 seconds for logs to appear...")

if __name__ == "__main__":
    test_custom_loki()