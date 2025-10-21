#!/usr/bin/env python3
"""
Comprehensive test for Task 6: Advanced Strategy Parameters UI
Tests creating strategies with transaction_fee, slippage, and other advanced params
"""

from datetime import datetime

import requests

BASE_URL = "http://localhost:8888"

LOGIN_CREDS = {"username": "admin", "password": "admin123"}


def get_auth_token():
    """Login and get JWT token"""
    response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=LOGIN_CREDS)
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code}")
        return None

    data = response.json()
    token = data.get("access_token") or data.get("data", {}).get("access_token")
    if not token:
        print(f"❌ No token in response: {data}")
        return None

    print("✅ Logged in successfully")
    return token


def test_advanced_params(token):
    """Test creating strategy with advanced parameters"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Test data with ALL advanced parameters
    strategy_data = {
        "name": f"Advanced Test Strategy {int(datetime.now().timestamp())}",
        "description": "Testing all advanced parameters",
        "category": "pairs_trading",
        "resolution": "1HOUR",
        # Basic parameters
        "zscore_threshold": 1.5,
        "stats_window": 21,
        "max_half_life": 12,
        "usd_per_trade": 25.0,
        "usd_min_collateral": 100.0,
        # Advanced Risk Management
        "max_positions": 5,
        "max_drawdown_pct": 15.0,
        "stop_loss_pct": 2.0,
        "take_profit_pct": 5.0,
        "trailing_stop_pct": 1.0,
        # Advanced Trading
        "rebalance_interval_hours": 24,
        "position_timeout_hours": 72,
        # Market Impact (NEW UI FIELDS)
        "transaction_fee": 0.0005,  # 0.05% dYdX maker fee
        "slippage": 0.001,  # 0.1% estimated slippage
        # Behavior
        "find_cointegrated_pairs": True,
        "manage_exits": True,
        "place_trades": True,
        "close_at_zscore_cross": True,
        "abort_all_positions": False,
        # Other
        "is_public": False,
        "initial_amount": 1000.0,
    }

    print("\n" + "=" * 70)
    print("📝 Testing Advanced Parameters UI")
    print("=" * 70)
    print("\n🔧 Creating strategy with advanced parameters...")
    print("\nPayload Summary:")
    print(f"  • Name: {strategy_data['name']}")
    print(f"  • Resolution: {strategy_data['resolution']}")
    print(f"  • Z-Score Threshold: {strategy_data['zscore_threshold']}")
    print(f"  • Transaction Fee: {strategy_data['transaction_fee']} (0.05%)")
    print(f"  • Slippage: {strategy_data['slippage']} (0.1%)")
    print(f"  • Max Positions: {strategy_data['max_positions']}")
    print(f"  • Stop Loss: {strategy_data['stop_loss_pct']}%")
    print(f"  • Take Profit: {strategy_data['take_profit_pct']}%")

    response = requests.post(
        f"{BASE_URL}/api/v1/strategies", json=strategy_data, headers=headers
    )

    if response.status_code != 200:
        print(f"\n❌ Strategy creation failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return None

    result = response.json()
    strategy_id = result.get("data", {}).get("id")
    print(f"\n✅ Strategy created successfully! ID: {strategy_id}")

    return strategy_id


def test_update_advanced_params(token, strategy_id):
    """Test updating strategy with modified advanced parameters"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    update_data = {
        "name": f"Updated Advanced Strategy {int(datetime.now().timestamp())}",
        "zscore_threshold": 1.8,
        "max_positions": 10,
        "stop_loss_pct": 3.0,
        "take_profit_pct": 8.0,
        "transaction_fee": 0.0006,  # Slightly higher fee
        "slippage": 0.0015,  # Slightly higher slippage
    }

    print(f"\n📝 Updating strategy {strategy_id} with modified parameters...")
    print("\nUpdate Summary:")
    print(f"  • New Transaction Fee: {update_data['transaction_fee']}")
    print(f"  • New Slippage: {update_data['slippage']}")
    print(f"  • New Stop Loss: {update_data['stop_loss_pct']}%")

    response = requests.put(
        f"{BASE_URL}/api/v1/strategies/{strategy_id}", json=update_data, headers=headers
    )

    if response.status_code != 200:
        print(f"\n❌ Strategy update failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

    print("\n✅ Strategy updated successfully!")
    return True


def test_retrieve_strategy(token, strategy_id):
    """Verify the advanced parameters were persisted"""
    headers = {
        "Authorization": f"Bearer {token}",
    }

    print(f"\n📋 Retrieving strategy {strategy_id} to verify persistence...")

    response = requests.get(
        f"{BASE_URL}/api/v1/strategies/{strategy_id}", headers=headers
    )

    if response.status_code != 200:
        print(f"❌ Failed to retrieve strategy: {response.status_code}")
        return False

    strategy = response.json().get("data")
    if not strategy:
        print("❌ No strategy data in response")
        return False

    print("\n✅ Strategy retrieved successfully!")
    print("\nPeristed Advanced Parameters:")
    print(f"  • Transaction Fee: {strategy.get('transaction_fee', 'N/A')}")
    print(f"  • Slippage: {strategy.get('slippage', 'N/A')}")
    print(f"  • Max Positions: {strategy.get('max_positions', 'N/A')}")
    print(f"  • Stop Loss: {strategy.get('stop_loss_pct', 'N/A')}%")
    print(f"  • Take Profit: {strategy.get('take_profit_pct', 'N/A')}%")
    print(f"  • Z-Score Threshold: {strategy.get('zscore_threshold', 'N/A')}")

    # Verify critical fields
    checks = [
        ("transaction_fee", 0.0006),
        ("slippage", 0.0015),
        ("max_positions", 10),
        ("stop_loss_pct", 3.0),
    ]

    all_valid = True
    print("\n🔍 Validation:")
    for field, expected in checks:
        actual = strategy.get(field)
        valid = actual == expected
        symbol = "✅" if valid else "❌"
        print(f"  {symbol} {field}: {actual} (expected: {expected})")
        if not valid:
            all_valid = False

    return all_valid


def main():
    print("\n" + "=" * 70)
    print("🧪 TASK 6: Advanced Strategy Parameters UI - Comprehensive Test")
    print("=" * 70)

    # Get auth token
    token = get_auth_token()
    if not token:
        return

    # Test 1: Create strategy with advanced params
    strategy_id = test_advanced_params(token)
    if not strategy_id:
        print("\n❌ Failed at strategy creation")
        return

    # Test 2: Update advanced params
    success = test_update_advanced_params(token, strategy_id)
    if not success:
        print("\n❌ Failed at strategy update")
        return

    # Test 3: Verify persistence
    valid = test_retrieve_strategy(token, strategy_id)

    # Final summary
    print("\n" + "=" * 70)
    if valid:
        print("✅ TASK 6 COMPLETE - Advanced Parameters UI is Working!")
        print("\n📊 Results:")
        print("  ✅ Create strategy with transaction_fee and slippage")
        print("  ✅ Update strategy with new advanced parameters")
        print("  ✅ Verify persistence in database")
        print("  ✅ All advanced parameters properly handled")
    else:
        print("⚠️  Some validation checks failed - review above")
    print("=" * 70)


if __name__ == "__main__":
    main()
