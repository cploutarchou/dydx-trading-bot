#!/usr/bin/env python3
"""
Debug test to capture what payload is being sent to the backend.
"""

import requests

BASE_URL = "http://localhost:8888/api/v1"

# Test credentials
TEST_USER = "admin"
TEST_PASSWORD = "admin123"

print("Testing what the backend receives...\n")

# Step 1: Login
print("[1] Logging in...")
login_response = requests.post(
    f"{BASE_URL}/auth/login", json={"username": TEST_USER, "password": TEST_PASSWORD}
)

login_data = login_response.json()
token = login_data.get("access_token") or login_data.get("data", {}).get("access_token")

headers = {"Authorization": f"Bearer {token}"}
print("✅ Logged in")

# Step 2: Create with explicit payload and NO usd_min_collateral
print("[2] Creating strategy WITHOUT usd_min_collateral...")
strategy_payload = {
    "name": "Debug Test",
    "description": "Debug test",
    "category": "pairs_trading",
    "is_public": False,
    "resolution": "1HOUR",
    "zscore_threshold": 1.5,
    "stats_window": 21,
    "max_half_life": 24,
    "usd_per_trade": 15.0,
    # usd_min_collateral NOT included
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
    "initial_amount": 333.0,
    "transaction_fee": 0.0005,
    "slippage": 0.001,
}

print(f"Payload keys: {list(strategy_payload.keys())}")
print(f"Has usd_min_collateral: {'usd_min_collateral' in strategy_payload}")
print(f"initial_amount: {strategy_payload['initial_amount']}")

create_response = requests.post(
    f"{BASE_URL}/strategies", json=strategy_payload, headers=headers
)

print(f"\nResponse status: {create_response.status_code}")
strategy_data = create_response.json().get("data", {})
print("Created strategy:")
print(f"  - ID: {strategy_data.get('id')}")
print(f"  - initial_amount: {strategy_data.get('initial_amount')}")
print(f"  - usd_min_collateral: {strategy_data.get('usd_min_collateral')}")
print(f"  - usd_per_trade: {strategy_data.get('usd_per_trade')}")
