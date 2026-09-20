import asyncio
import json
from pathlib import Path

import pytest

from src.api import server
from src.shared.live_risk_controls import (
    assert_supported_live_risk_controls,
    describe_unsupported_live_risk_controls,
    validate_live_risk_controls,
)
from src.trading import position_manager


def _runtime_payload():
    return {
        "instance_id": "strategy-1-999",
        "instance_name": "Risk Test",
        "credentials": {
            "chain_id": "dydx-testnet-4",
            "address": "0x1234567890123456789012345678901234567890",
            "mnemonic": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
        },
        "trading_params": {
            "is_testnet": True,
            "subaccount_number": 0,
            "capital_allocation_usd": 0.0,
            "find_cointegrated_pairs": False,
            "manage_exits": True,
            "place_trades": False,
            "abort_all_positions": False,
            "resolution_timeframe": "1HOUR",
            "strategy": "cointegration",
            "stats_window": 21,
            "max_half_life": 24,
            "zscore_threshold": 1.5,
            "usd_per_trade": 10.0,
            "usd_min_collateral": 100.0,
            "close_at_zscore_cross": True,
            "max_positions": 2,
            "max_drawdown_pct": 0.0,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 5.0,
            "trailing_stop_pct": 0.0,
            "rebalance_interval_hours": 24,
            "position_timeout_hours": 72,
            "selected_markets": ["BTC-USD", "ETH-USD"],
        },
        "backtesting_params": {
            "candle_resolution": "1HOUR",
            "max_history_days": 90,
            "starting_balance": 1000.0,
            "transaction_fee": 0.0005,
            "slippage": 0.001,
            "benchmark_symbol": "BTC-USD",
            "risk_free_rate": 0.02,
        },
    }


def test_runtime_preflight_rejects_unsupported_risk_controls(monkeypatch):
    payload = _runtime_payload()
    payload["trading_params"]["max_drawdown_pct"] = 1.0
    response = asyncio.run(
        server.runtime_preflight(
            server.RuntimePreflightRequest(**payload),
            current_user=object(),
        )
    )
    payload = json.loads(response.body)

    assert response.status_code == 422
    assert payload["data"]["error"] == "UNSUPPORTED_RISK_CONTROL"


def test_runtime_preflight_names_each_unsupported_risk_control():
    payload = _runtime_payload()
    payload["trading_params"]["max_drawdown_pct"] = 15.0
    payload["trading_params"]["trailing_stop_pct"] = 1.0
    response = asyncio.run(
        server.runtime_preflight(
            server.RuntimePreflightRequest(**payload),
            current_user=object(),
        )
    )
    body = json.loads(response.body)

    assert response.status_code == 422
    unsupported = body["data"]["unsupported_fields"]
    assert [(entry["field"], entry["value"]) for entry in unsupported] == [
        ("max_drawdown_pct", 15.0),
        ("trailing_stop_pct", 1.0),
    ]
    assert all(entry["field"] in entry["message"] for entry in unsupported)


def test_create_bot_instance_rejects_unsupported_risk_controls(monkeypatch):
    payload = _runtime_payload()
    payload["trading_params"]["trailing_stop_pct"] = 1.0
    response = asyncio.run(
        server.create_bot_instance(
            server.BotInstanceConfig(**payload),
            current_user=object(),
            _rate=None,
        )
    )
    payload = json.loads(response.body)

    assert response.status_code == 422
    assert payload["data"]["error"] == "UNSUPPORTED_RISK_CONTROL"


def test_supported_live_risk_controls_pass_validation():
    assert_supported_live_risk_controls(_runtime_payload()["trading_params"])


def test_stop_loss_take_profit_and_timeout_exit_rules_are_enforced(monkeypatch):
    monkeypatch.setattr(position_manager, "STOP_LOSS_PCT", 2.0)
    monkeypatch.setattr(position_manager, "TAKE_PROFIT_PCT", 5.0)
    monkeypatch.setattr(position_manager, "POSITION_TIMEOUT_HOURS", 24)
    monkeypatch.setattr(position_manager, "CLOSE_AT_ZSCORE_CROSS", False)

    assert (
        position_manager._resolve_exit_reason(
            z_score_current=0.1,
            z_score_traded=1.0,
            unrealized_pnl_pct=-2.1,
            position_age_hours=1.0,
        )
        == "stop_loss"
    )
    assert (
        position_manager._resolve_exit_reason(
            z_score_current=0.1,
            z_score_traded=1.0,
            unrealized_pnl_pct=5.1,
            position_age_hours=1.0,
        )
        == "take_profit"
    )
    assert (
        position_manager._resolve_exit_reason(
            z_score_current=0.1,
            z_score_traded=1.0,
            unrealized_pnl_pct=0.0,
            position_age_hours=24.0,
        )
        == "timeout"
    )


def test_unsupported_risk_controls_are_rejected():
    with pytest.raises(ValueError, match="max_drawdown_pct"):
        assert_supported_live_risk_controls(
            {
                "max_drawdown_pct": 1.0,
                "trailing_stop_pct": 0.0,
                "capital_allocation_usd": 0.0,
            }
        )


def test_describing_unsupported_controls_never_relaxes_the_rejection():
    payload = {
        "max_drawdown_pct": 0.0,
        "trailing_stop_pct": 2.5,
        "capital_allocation_usd": 1000.0,
    }

    described = describe_unsupported_live_risk_controls(payload)

    assert [entry["field"] for entry in described] == [
        "trailing_stop_pct",
        "capital_allocation_usd",
    ]
    assert validate_live_risk_controls(payload) == [
        entry["message"] for entry in described
    ]
    with pytest.raises(ValueError, match="trailing_stop_pct"):
        assert_supported_live_risk_controls(payload)
    assert (
        describe_unsupported_live_risk_controls(_runtime_payload()["trading_params"])
        == []
    )


def test_risk_control_matrix_file_exists():
    matrix_path = Path("docs/bot-risk-control-matrix.md")

    assert matrix_path.exists()
