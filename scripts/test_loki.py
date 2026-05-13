#!/usr/bin/env python3
"""
Test script for Loki logging configuration
Usage: python test_loki.py [development|production]
"""

import logging
import sys
from pathlib import Path

import yaml

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

def test_loki_connection(environment="development"):
    """Test Loki connection with specified environment"""
    
    # Temporarily modify config for testing
    from pathlib import Path
    
    config_path = Path(__file__).parent.parent / "app" / "config.yaml"
    
    # Read current config
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    # Store original environment
    original_environment = config_data.get('environment', 'development')
    
    # Temporarily update environment in config
    config_data['environment'] = environment
    
    # Write temporary config
    with open(config_path, 'w') as f:
        yaml.dump(config_data, f, default_flow_style=False)
    
    try:
        # Import after modifying config
        from logging_setup import setup_logging
        
        print(f"\n🧪 Testing Loki connection with environment: {environment}")
        print("=" * 50)
        
        # Setup logging
        setup_logging()
        
        # Get logger and test different log levels
        logger = logging.getLogger("test_loki")
        
        print("\n📝 Sending test logs...")
        
        # Test different log levels
        logger.debug("🔍 DEBUG: This is a debug message for testing")
        logger.info("ℹ️  INFO: Loki connection test - info level")
        logger.warning("⚠️  WARNING: This is a test warning message")
        logger.error("❌ ERROR: Test error message (don't worry, this is just a test)")
        
        # Test with extra context
        logger.info("📊 Trading Bot Status", extra={
            "market": "BTC-USD",
            "action": "test",
            "environment": environment
        })
        
        print("✅ Test logs sent successfully!")
        print("   Check your Loki instance to verify logs are being received")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Restore original environment in config
        config_data['environment'] = original_environment
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False)

if __name__ == "__main__":
    environment = sys.argv[1] if len(sys.argv) > 1 else "development"
    
    if environment not in ["development", "dev", "production", "prod"]:
        print("Usage: python test_loki.py [development|production]")
        sys.exit(1)
        
    test_loki_connection(environment)