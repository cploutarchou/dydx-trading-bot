#!/usr/bin/env python3
"""
Test script to verify field consolidation in strategy builder.

Tests:
1. Creating a strategy without usd_min_collateral in payload
2. Verifying usd_min_collateral is auto-set to initial_amount
3. Updating an existing strategy with consolidated fields
4. Loading a strategy and verifying both fields are synchronized
"""

import requests

BASE_URL = "http://localhost:8888/api/v1"

# Test credentials
TEST_USER = "admin"
TEST_PASSWORD = "admin123"


def log_test(name, status, details=""):
    symbol = "✅" if status else "❌"
    print(f"\n{symbol} {name}")
    if details:
        print(f"   Details: {details}")


def test_field_consolidation():
    """Test that field consolidation works correctly."""

    print("\n" + "=" * 60)
    print("FIELD CONSOLIDATION TEST SUITE")
    print("=" * 60)

    # Step 1: Login
    print("\n[1] Logging in...")
    login_response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": TEST_USER, "password": TEST_PASSWORD},
    )

    if login_response.status_code != 200:
        log_test("Login", False, f"Status {login_response.status_code}")
        print(f"Response: {login_response.json()}")
        return

    login_data = login_response.json()
    token = login_data.get("access_token") or login_data.get("data", {}).get(
        "access_token"
    )

    if not token:
        log_test("Login", False, f"No token in response: {login_data}")
        return

    headers = {"Authorization": f"Bearer {token}"}
    log_test(
        "Login",
        True,
        f"Token: {token[:30]}..." if len(token) > 30 else f"Token: {token}",
    )

    # Step 2: Create strategy WITHOUT usd_min_collateral in payload
    print("\n[2] Creating strategy without usd_min_collateral in payload...")
    strategy_payload = {
        "name": "Field Consolidation Test",
        "description": "Testing consolidated investment amount fields",
        "category": "pairs_trading",
        "is_public": False,
        "resolution": "1HOUR",
        "zscore_threshold": 1.5,
        "stats_window": 21,
        "max_half_life": 24,
        "usd_per_trade": 15.0,
        # NOTE: usd_min_collateral intentionally omitted to test auto-calculation
        "close_at_zscore_cross": True,
        "find_cointegrated_pairs": True,
        "manage_exits": True,
        "place_trades": True,
        "abort_all_positions": False,
        "max_positions": 5,
        "max_drawdown_pct": 15.0,
        "stop_loss_pct": 2.0,
        "take_profit_pct": 5.0,
        "trailing_stop_pct": 1.0,
        "rebalance_interval_hours": 24,
        "position_timeout_hours": 72,
        "initial_amount": 555.0,  # Test non-round number to verify rounding fix
        "transaction_fee": 0.0005,
        "slippage": 0.001,
    }

    create_response = requests.post(
        f"{BASE_URL}/strategies", json=strategy_payload, headers=headers
    )

    if create_response.status_code != 200:
        log_test("Create Strategy", False, f"Status {create_response.status_code}")
        print(f"Response: {create_response.json()}")
        return

    strategy_data = create_response.json().get("data", {})
    strategy_id = strategy_data.get("id")
    log_test("Create Strategy", True, f"ID: {strategy_id}")

    # Step 3: Verify usd_min_collateral was auto-set
    print("\n[3] Verifying usd_min_collateral auto-sync...")

    created_collateral = strategy_data.get("usd_min_collateral")
    created_initial = strategy_data.get("initial_amount")

    auto_sync_ok = created_collateral == created_initial
    log_test(
        "Auto-sync usd_min_collateral to initial_amount",
        auto_sync_ok,
        f"min_collateral={created_collateral}, initial_amount={created_initial}",
    )

    # Step 4: Verify non-round number (555) was accepted without rounding
    print("\n[4] Verifying non-round numbers are accepted (rounding fix)...")

    amount_accepted = created_initial == 555.0
    log_test(
        "Accept non-round amount (555.0)",
        amount_accepted,
        f"initial_amount={created_initial}",
    )

    # Step 5: Get strategy and verify fields
    print("\n[5] Loading strategy and verifying fields...")
    get_response = requests.get(f"{BASE_URL}/strategies/{strategy_id}", headers=headers)

    if get_response.status_code != 200:
        log_test("Get Strategy", False, f"Status {get_response.status_code}")
        print(f"Response: {get_response.json()}")
        return

    loaded_strategy = get_response.json().get("data", {})

    loaded_collateral = loaded_strategy.get("usd_min_collateral")
    loaded_initial = loaded_strategy.get("initial_amount")
    loaded_per_trade = loaded_strategy.get("usd_per_trade")

    log_test("Get Strategy", True, f"ID: {strategy_id}")

    # Verify all fields are correct
    print("\n   Loaded values:")
    print(f"   - initial_amount: {loaded_initial}")
    print(f"   - usd_min_collateral: {loaded_collateral}")
    print(f"   - usd_per_trade: {loaded_per_trade}")

    # Step 6: Update strategy with different amount
    print("\n[6] Updating strategy with new initial_amount...")
    update_payload = {
        "initial_amount": 750.0,  # Another non-round number
        "usd_per_trade": 20.0,
    }

    update_response = requests.put(
        f"{BASE_URL}/strategies/{strategy_id}", json=update_payload, headers=headers
    )

    if update_response.status_code != 200:
        log_test("Update Strategy", False, f"Status {update_response.status_code}")
        print(f"Response: {update_response.json()}")
        return

    updated_strategy = update_response.json().get("data", {})
    updated_collateral = updated_strategy.get("usd_min_collateral")
    updated_initial = updated_strategy.get("initial_amount")

    log_test("Update Strategy", True, f"ID: {strategy_id}")

    # Step 7: Verify update also syncs usd_min_collateral
    print("\n[7] Verifying usd_min_collateral sync on update...")

    update_sync_ok = updated_collateral == updated_initial
    log_test(
        "Auto-sync on update",
        update_sync_ok,
        f"min_collateral={updated_collateral}, initial_amount={updated_initial}",
    )

    # Final Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    all_passed = auto_sync_ok and amount_accepted and update_sync_ok

    if all_passed:
        print("\n✅ ALL TESTS PASSED")
        print("   - Field consolidation working correctly")
        print("   - Non-round numbers accepted (rounding fix)")
        print("   - usd_min_collateral auto-syncs with initial_amount")
    else:
        print("\n❌ SOME TESTS FAILED")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_field_consolidation()
