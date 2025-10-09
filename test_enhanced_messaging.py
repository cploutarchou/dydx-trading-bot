#!/usr/bin/env python3
"""
Test script for the enhanced Telegram messaging system.
This script tests various message types without affecting actual trading.
"""

import asyncio
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from func_messaging import TelegramMessenger


async def test_enhanced_messaging():
    """Test all enhanced messaging features."""
    
    print("🧪 Testing Enhanced Telegram Messaging System")
    print("=" * 50)
    
    # Initialize messenger
    messenger = TelegramMessenger()
    
    if not messenger.enabled:
        print("❌ Telegram messaging is disabled (missing token or chat_id)")
        print("💡 Configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in config.yaml")
        return False
    
    print("✅ Telegram messenger initialized successfully")
    print(f"📱 Sending test messages to chat ID: {messenger.chat_id[:8]}...")
    
    # Test 1: Startup Message
    print("\n1. Testing startup message...")
    config_info = {
        "environment": "development",
        "is_testnet": True,
        "strategy": "cointegration",
        "usd_per_trade": 10,
        "abort_all_positions": False,
        "find_cointegrated": True,
        "manage_exits": True,
        "place_trades": True
    }
    
    success = messenger.send_startup_message(config_info)
    print(f"   {'✅' if success else '❌'} Startup message: {'Sent' if success else 'Failed'}")
    
    # Test 2: Error Messages
    print("\n2. Testing error messages...")
    
    # Non-critical error
    success = messenger.send_error_message(
        "Test Error",
        "This is a test non-critical error message",
        is_critical=False
    )
    print(f"   {'✅' if success else '❌'} Non-critical error: {'Sent' if success else 'Failed'}")
    
    # Critical error
    success = messenger.send_error_message(
        "Critical Test Error",
        "This is a test CRITICAL error message that requires immediate attention!",
        is_critical=True
    )
    print(f"   {'✅' if success else '❌'} Critical error: {'Sent' if success else 'Failed'}")
    
    # Test 3: Trade Notifications
    print("\n3. Testing trade notifications...")
    
    # Trade opened
    trade_info = {
        "pair": "BTC-USD / ETH-USD",
        "base_market": "BTC-USD",
        "quote_market": "ETH-USD",
        "base_side": "BUY",
        "quote_side": "SELL",
        "base_size": "0.001",
        "quote_size": "0.02",
        "z_score": 2.15,
        "hedge_ratio": 0.85,
        "half_life": 12.5,
        "market_1_order_id": "test_order_123",
        "market_2_order_id": "test_order_456"
    }
    
    success = messenger.send_trade_opened_message(trade_info)
    print(f"   {'✅' if success else '❌'} Trade opened: {'Sent' if success else 'Failed'}")
    
    # Trade closed
    success = messenger.send_trade_closed_message(trade_info, "Z-score reversion")
    print(f"   {'✅' if success else '❌'} Trade closed: {'Sent' if success else 'Failed'}")
    
    # Test 4: Cointegration Results
    print("\n4. Testing cointegration analysis notification...")
    
    success = messenger.send_cointegration_results(12, 285.7)
    print(f"   {'✅' if success else '❌'} Cointegration results: {'Sent' if success else 'Failed'}")
    
    # Test 5: Account Status
    print("\n5. Testing account status notification...")
    
    account_info = {
        "equity": 1500.50,
        "free_collateral": 750.25,
        "total_account_value": 1500.50,
        "open_positions": 2,
        "active_pairs": ["BTC-USD / ETH-USD", "MATIC-USD / SOL-USD"]
    }
    
    success = messenger.send_account_status(account_info, is_testnet=True)
    print(f"   {'✅' if success else '❌'} Account status: {'Sent' if success else 'Failed'}")
    
    # Test 6: Daily Summary
    print("\n6. Testing daily summary notification...")
    
    summary_info = {
        "trades_opened": 5,
        "trades_closed": 3,
        "net_pnl": 42.50,
        "success_rate": 75.0,
        "active_pairs": 2,
        "cointegrated_pairs_found": 12,
        "uptime_hours": 18.5
    }
    
    success = messenger.send_daily_summary(summary_info)
    print(f"   {'✅' if success else '❌'} Daily summary: {'Sent' if success else 'Failed'}")
    
    # Test 7: Shutdown Message
    print("\n7. Testing shutdown notification...")
    
    success = messenger.send_shutdown_message("Test shutdown - system will restart shortly")
    print(f"   {'✅' if success else '❌'} Shutdown message: {'Sent' if success else 'Failed'}")
    
    print("\n" + "=" * 50)
    print("🎉 Enhanced messaging test completed!")
    print("📱 Check your Telegram chat for all test messages")
    print("💡 All messages should have professional HTML formatting")
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_enhanced_messaging())
        if success:
            print("\n✅ Test completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Test failed - check Telegram configuration")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        sys.exit(1)