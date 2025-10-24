#!/usr/bin/env python3
"""
Test script for Docker container - validates basic functionality without trading.
This script tests that the Docker image can:
1. Load configuration
2. Initialize logging
3. Import all required modules
4. Exit cleanly without actually connecting to dYdX
"""

import sys

# Add app directory to path
sys.path.insert(0, '/app')

def test_docker_environment():
    """Test that the Docker environment is working correctly."""
    print("🐳 Testing Docker environment...")
    
    try:
        # Test 1: Configuration loading
        print("📋 Testing configuration loading...")
        from backend.app.config import ConfigurationManager
        config = ConfigurationManager.get_config()
        
        if config is None:
            raise Exception("Failed to load configuration")
        
        print("✅ Configuration loaded successfully")
        print(f"   - Environment: {getattr(config, 'environment', 'development')}")
        print(f"   - Is testnet: {config.is_testnet}")
        print(f"   - Strategy: {config.botSettings.strategy}")
        
        # Test 2: Logging initialization
        print("📊 Testing logging setup...")
        from backend.app.logging_setup import setup_logging
        setup_logging()
        print("✅ Logging initialized successfully")
        
        # Test 3: Import all major modules
        print("🔧 Testing module imports...")
        
        modules_to_test = [
            'app.constants',
            'app.func_connections', 
            'app.func_bot_agent',
            'app.func_private',
            'app.func_public',
            'app.func_utils'
        ]
        
        for module in modules_to_test:
            try:
                __import__(module)
                print(f"   ✅ {module}")
            except ImportError as e:
                print(f"   ❌ {module}: {e}")
                raise
        
        print("✅ All modules imported successfully")
        
        # Test 4: Constants loading
        print("⚙️  Testing constants loading...")
        from backend.app.constants import LOG_LEVEL, MARKET_DATA_MODE, USD_PER_TRADE
        print(f"   ✅ LOG_LEVEL: {LOG_LEVEL}")
        print(f"   ✅ MARKET_DATA_MODE: {MARKET_DATA_MODE}")
        print(f"   ✅ USD_PER_TRADE: {USD_PER_TRADE}")
        
        print("🎉 Docker environment test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Docker environment test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_docker_environment()
    sys.exit(0 if success else 1)