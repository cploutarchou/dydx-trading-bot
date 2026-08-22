"""Input-validation coverage for trading API request models.

These tests pin the boundary constraints added to the trading/backtest/strategy
Pydantic models and the global ``RequestValidationError`` envelope handler. The
goal of the underlying change is to reject invalid trades at the API boundary
(strict 422) rather than letting them reach the live runtime.

The route functions are exercised indirectly through their request models; we
do not stand up a full HTTP client here, mirroring the style of
``tests/test_live_risk_controls.py``.
"""

import asyncio
import json

import pytest
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from src.api import server
from src.infrastructure.domain.bot_api_models import (
    BacktestingParameters,
    BotInstanceConfig,
    TradingParameters,
)
from src.infrastructure.domain.models_backtest import BacktestConfigRequest
from src.shared.trading_validators import (
    normalize_market_list,
    validate_iso_date_range,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _valid_trading_params():
    """A baseline TradingParameters payload known to satisfy all constraints."""
    return {
        "is_testnet": True,
        "subaccount_number": 0,
        "capital_allocation_usd": 0.0,
        "stats_window": 21,
        "max_half_life": 24,
        "zscore_threshold": 1.5,
        "usd_per_trade": 10.0,
        "usd_min_collateral": 100.0,
        "max_positions": 5,
        "stop_loss_pct": 2.0,
        "take_profit_pct": 5.0,
        "selected_markets": ["BTC-USD", "ETH-USD"],
    }


def _valid_credentials():
    return {
        "chain_id": "dydx-testnet-4",
        "address": "0x" + "1" * 40,
        "mnemonic": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
    }


# ---------------------------------------------------------------------------
# TradingParameters
# ---------------------------------------------------------------------------


def test_trading_parameters_defaults_are_valid():
    """All defaults must satisfy the new constraints (backwards compatible)."""
    params = TradingParameters()
    assert params.usd_per_trade > 0
    assert params.stats_window >= 2
    assert params.max_positions >= 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"usd_per_trade": 0},
        {"usd_per_trade": -5.0},
        {"zscore_threshold": 0},
        {"zscore_threshold": -1.0},
        {"stats_window": 1},
        {"stats_window": 0},
        {"max_positions": -1},
        {"subaccount_number": -1},
        {"capital_allocation_usd": -1.0},
        {"stop_loss_pct": -0.1},
        {"take_profit_pct": 1500.0},  # above le=1000
        {"rebalance_interval_hours": 9000},  # above le=8760
    ],
)
def test_trading_parameters_rejects_out_of_bounds(overrides):
    payload = {**_valid_trading_params(), **overrides}
    with pytest.raises(ValidationError):
        TradingParameters(**payload)


def test_trading_parameters_normalizes_selected_markets():
    params = TradingParameters(selected_markets=[" btc-usd ", "", "ETH-USD", "BTC-USD"])
    assert params.selected_markets == ["BTC-USD", "ETH-USD"]


# ---------------------------------------------------------------------------
# BacktestingParameters
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"starting_balance": 0},
        {"starting_balance": -10.0},
        {"max_history_days": 0},
        {"transaction_fee": 1.5},  # must be < 1
        {"slippage": 2.0},
        {"risk_free_rate": 1.5},  # must be <= 1
    ],
)
def test_backtesting_parameters_rejects_out_of_bounds(overrides):
    with pytest.raises(ValidationError):
        BacktestingParameters(**overrides)


# ---------------------------------------------------------------------------
# BotInstanceConfig
# ---------------------------------------------------------------------------


def _valid_bot_config():
    return {
        "instance_id": "strategy-1-999",
        "credentials": _valid_credentials(),
        "trading_params": _valid_trading_params(),
    }


@pytest.mark.parametrize("bad_id", ["", "has space", "bad/id!", "has.dot"])
def test_bot_instance_config_rejects_bad_instance_id(bad_id):
    payload = {**_valid_bot_config(), "instance_id": bad_id}
    with pytest.raises(ValidationError):
        BotInstanceConfig(**payload)


def test_bot_instance_config_accepts_slug_format():
    config = BotInstanceConfig(**_valid_bot_config())
    assert config.instance_id == "strategy-1-999"


# ---------------------------------------------------------------------------
# BacktestConfigRequest
# ---------------------------------------------------------------------------


def _valid_backtest_config():
    return {
        "name": "Q1 run",
        "start_date": "2026-01-01",
        "end_date": "2026-03-31",
        "trading_parameters": {"zscore_threshold": 1.5},
        "pairs": ["BTC-USD", "ETH-USD"],
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"start_date": "01/01/2026"},  # bad format (regex reject)
        {"start_date": "2026-03-31", "end_date": "2026-01-01"},  # end < start
        {
            "end_date": "2026-13-40"
        },  # passes regex, invalid calendar date (strptime reject)
        {"initial_balance": 0},
        {"initial_balance": -1.0},
        {"name": ""},
        {"max_pairs": -1},
        {"max_pairs": 5000},
        {"timeout_seconds": 0},
        {"timeout_seconds": -5.0},
        {"strategy_id": 0},
    ],
)
def test_backtest_config_rejects_out_of_bounds(overrides):
    payload = {**_valid_backtest_config(), **overrides}
    with pytest.raises(ValidationError):
        BacktestConfigRequest(**payload)


def test_backtest_config_normalizes_pairs():
    config = BacktestConfigRequest(
        **{**_valid_backtest_config(), "pairs": [" btc ", "", "ETH-USD", "BTC-USD"]}
    )
    assert "BTC" in config.pairs
    assert config.pairs.count("BTC") == 1


# ---------------------------------------------------------------------------
# BacktestRunRequestCompat + StrategyRequest (server.py models)
# ---------------------------------------------------------------------------


def test_backtest_run_request_rejects_end_before_start():
    with pytest.raises(ValidationError):
        server.BacktestRunRequestCompat(
            start_date="2026-03-31",
            end_date="2026-01-01",
        )


def test_backtest_run_request_rejects_non_positive_balance():
    with pytest.raises(ValidationError):
        server.BacktestRunRequestCompat(
            start_date="2026-01-01",
            end_date="2026-03-31",
            initial_balance=0,
        )


def test_strategy_request_rejects_negative_trade_size():
    with pytest.raises(ValidationError):
        server.StrategyRequest(name="x", usd_per_trade=-1.0)


def test_strategy_request_rejects_empty_name():
    with pytest.raises(ValidationError):
        server.StrategyRequest(name="")


# ---------------------------------------------------------------------------
# New request models (raw-dict -> schema conversions)
# ---------------------------------------------------------------------------


def test_backtest_comparison_request_requires_two_run_ids():
    with pytest.raises(ValidationError):
        server.BacktestComparisonRequest(run_ids=["only-one"])


def test_backtest_comparison_request_accepts_two():
    req = server.BacktestComparisonRequest(run_ids=["run-a", "run-b"])
    assert len(req.run_ids) == 2


def test_backtest_metadata_request_requires_object_metadata():
    with pytest.raises(ValidationError):
        server.BacktestMetadataRequest(metadata="not-an-object")


def test_arbitrage_runtime_settings_ignores_unknown_keys():
    req = server.ArbitrageRuntimeSettingsRequest(
        **{"UNKNOWN_FLAG": True, "PAIR_PRIORITY_MAX_PAIRS": 5}
    )
    dumped = req.model_dump(exclude_unset=True)
    assert "UNKNOWN_FLAG" not in dumped
    assert dumped["PAIR_PRIORITY_MAX_PAIRS"] == 5


def test_arbitrage_runtime_settings_rejects_negative_pairs():
    with pytest.raises(ValidationError):
        server.ArbitrageRuntimeSettingsRequest(PAIR_PRIORITY_MAX_PAIRS=-1)


# ---------------------------------------------------------------------------
# Shared validators
# ---------------------------------------------------------------------------


def test_validate_iso_date_range_accepts_equal_dates():
    validate_iso_date_range("2026-01-01", "2026-01-01")  # no raise


def test_normalize_market_list_caps_items():
    many = [f"M{i}" for i in range(300)]
    assert len(normalize_market_list(many, max_items=10)) == 10


# ---------------------------------------------------------------------------
# Global RequestValidationError handler (envelope shape)
# ---------------------------------------------------------------------------


def _make_validation_error():
    try:
        TradingParameters(usd_per_trade=-5)
    except ValidationError as ve:
        return RequestValidationError(ve.errors(), body={})
    raise AssertionError("expected ValidationError")


def test_validation_handler_returns_envelope():
    exc = _make_validation_error()
    response = asyncio.run(server._validation_exception_handler(request=None, exc=exc))

    assert response.status_code == 422
    payload = json.loads(response.body)
    assert payload["success"] is False
    assert payload["message"] == "Validation error"
    assert "errors" in payload["data"]
    assert "trace_id" in payload
    assert payload["data"]["errors"], "expected at least one validation error entry"
