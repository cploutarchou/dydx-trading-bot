import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from datetime import datetime, timezone

# SQLAlchemy models
from models.user import User, AuditLog
from models.backtest import (
    BacktestRun, BacktestResult, BacktestLog, BacktestTrade, BacktestPosition, BacktestCandle, BacktestComparison
)
from models.trade import TradeLog
from models.settings import BotSetting, RedisSetting
from models.strategy import BacktestStrategy, StrategyVersionHistory, StrategyExecutionState
from models.dydx_keys import DYDXKey, DYDXKeySettings

# Dataclass models
from bot.models.backtest_models import BacktestTrade as DCBacktestTrade, BacktestMetrics, BacktestResult as DCBacktestResult
from bot.models.pair_storage import CointegrationResult


def test_user_to_dict_from_dict():
    user = User(username="alice", email="alice@example.com", hashed_password="hash")
    d = user.to_dict()
    assert d["username"] == "alice"
    user2 = User()
    user2.from_dict(d)
    assert user2.username == "alice"
    # Test password hashing
    user2.set_password("secret")
    assert user2.check_password("secret")
    # Test to_public_dict
    public = user2.to_public_dict()
    assert "hashed_password" not in public
    assert "is_admin" not in public

def test_auditlog_repr():
    log = AuditLog(user_id=1, action="login", resource_type="user")
    assert "login" in repr(log)

def test_backtest_run_to_dict_from_dict():
    now = datetime.now(timezone.utc)
    run = BacktestRun(run_id="r1", status="running", created_at=now, start_date="2025-01-01", end_date="2025-01-02", num_pairs=2, total_markets=5)
    d = run.to_dict()
    assert d["run_id"] == "r1"
    run2 = BacktestRun()
    run2.from_dict(d)
    assert run2.run_id == "r1"

def test_backtest_result_to_dict_from_dict():
    result = BacktestResult(market_1="BTC-USD", market_2="ETH-USD", run_id_fk=1)
    d = result.to_dict()
    assert d["market_1"] == "BTC-USD"
    result2 = BacktestResult()
    result2.from_dict(d)
    assert result2.market_1 == "BTC-USD"

def test_backtest_log_to_dict_from_dict():
    log = BacktestLog(run_id_fk=1, message="msg", level="info")
    d = log.to_dict()
    assert d["message"] == "msg"
    log2 = BacktestLog()
    log2.from_dict(d)
    assert log2.message == "msg"

def test_backtest_trade_to_dict_from_dict():
    trade = BacktestTrade(trade_id="t1", run_id_fk=1, market_1="BTC-USD", market_2="ETH-USD", entry_timestamp=datetime.now(timezone.utc))
    d = trade.to_dict()
    assert d["trade_id"] == "t1"
    trade2 = BacktestTrade()
    trade2.from_dict(d)
    assert trade2.trade_id == "t1"

def test_backtest_position_to_dict_from_dict():
    pos = BacktestPosition(position_id="p1", run_id_fk=1, market_1="BTC-USD", market_2="ETH-USD", status="OPEN", entry_timestamp=datetime.now(timezone.utc))
    d = pos.to_dict()
    assert d["position_id"] == "p1"
    pos2 = BacktestPosition()
    pos2.from_dict(d)
    assert pos2.position_id == "p1"

def test_backtest_candle_to_dict_from_dict():
    candle = BacktestCandle(run_id_fk=1, market="BTC-USD", timestamp=datetime.now(timezone.utc), resolution="1HOUR", open_price=1, high_price=2, low_price=0.5, close_price=1.5, volume=100, trades_count=10)
    d = candle.to_dict()
    assert d["market"] == "BTC-USD"
    candle2 = BacktestCandle()
    candle2.from_dict(d)
    assert candle2.market == "BTC-USD"

def test_backtest_comparison_to_dict_from_dict():
    comp = BacktestComparison(name="cmp", description="desc", user_id=1, strategy_id_1=1, strategy_id_2=2, run_id_1=1, run_id_2=2)
    d = comp.to_dict()
    assert d["name"] == "cmp"
    comp2 = BacktestComparison()
    comp2.from_dict(d)
    assert comp2.name == "cmp"

def test_tradelog_to_dict_from_dict():
    log = TradeLog(result_id_fk=1, trade_number=1, entry_timestamp=datetime.now(timezone.utc), entry_price_1=1, entry_price_2=2, quantity_1=1, quantity_2=2, side_1="BUY", side_2="SELL")
    d = log.to_dict()
    assert d["trade_number"] == 1
    log2 = TradeLog()
    log2.from_dict(d)
    assert log2.trade_number == 1

def test_botsetting_to_dict_from_dict():
    s = BotSetting(section="bot", key="k", value="v", value_type="string")
    d = s.to_dict()
    assert d["key"] == "k"
    s2 = BotSetting()
    s2.from_dict(d)
    assert s2.key == "k"

def test_redissetting_to_dict_from_dict():
    s = RedisSetting(host="localhost", port=6379, db=0)
    d = s.to_dict()
    assert d["host"] == "localhost"
    s2 = RedisSetting()
    s2.from_dict(d)
    assert s2.host == "localhost"

def test_backteststrategy_to_dict_from_dict():
    strat = BacktestStrategy(name="strat", user_id=1, zscore_threshold=2.0, stats_window=21, max_half_life=24.0, usd_per_trade=10.0, usd_min_collateral=100.0, close_at_zscore_cross=True, find_cointegrated_pairs=True, manage_exits=True, place_trades=True, abort_all_positions=False, max_positions=5, max_drawdown_pct=15.0, stop_loss_pct=2.0, take_profit_pct=5.0, trailing_stop_pct=1.0, rebalance_interval_hours=24, position_timeout_hours=72, transaction_fee=0.0005, slippage=0.001, starting_balance=1000.0, candle_resolution="1HOUR", max_history_days=90, benchmark_symbol="BTC-USD", risk_free_rate=0.02, initial_amount=1000.0)
    d = strat.to_dict()
    assert d["name"] == "strat"
    strat2 = BacktestStrategy()
    strat2.from_dict(d)
    assert strat2.name == "strat"

def test_strategyversionhistory_to_dict_from_dict():
    v = StrategyVersionHistory(strategy_id=1, version_number=1, config_snapshot={})
    d = v.to_dict()
    assert d["version_number"] == 1
    v2 = StrategyVersionHistory()
    v2.from_dict(d)
    assert v2.version_number == 1

def test_strategyexecutionstate_to_dict_from_dict():
    s = StrategyExecutionState(strategy_id=1, enabled=True, status="running")
    d = s.to_dict()
    assert d["status"] == "running"
    s2 = StrategyExecutionState()
    s2.from_dict(d)
    assert s2.status == "running"

def test_dydxkey_to_dict_from_dict():
    k = DYDXKey(user_id=1, network="testnet", chain_address="0xabc", encrypted_secret="enc", is_active=True)
    d = k.to_dict()
    assert d["network"] == "testnet"
    assert "encrypted_secret" not in d
    d2 = k.to_dict(include_secret=True)
    assert d2["encrypted_secret"] == "enc"
    k2 = DYDXKey()
    k2.from_dict(d2)
    assert k2.encrypted_secret == "enc"

def test_dydxkeysettings_to_dict_from_dict():
    s = DYDXKeySettings(user_id=1, default_network="testnet", auto_switch_testnet=True)
    d = s.to_dict()
    assert d["default_network"] == "testnet"
    s2 = DYDXKeySettings()
    s2.from_dict(d)
    assert s2.default_network == "testnet"

# Dataclass models

def test_dc_backtesttrade_to_dict_from_dict():
    t = DCBacktestTrade(
        timestamp="2025-01-01T00:00:00Z",
        market_1="BTC-USD",
        market_2="ETH-USD",
        side_1="BUY",
        side_2="SELL",
        size_1=1.0,
        size_2=2.0,
        entry_price_1=100.0,
        entry_price_2=200.0,
        z_score_entry=1.5,
        hedge_ratio=0.8,
        trade_id="t1"
    )
    d = t.to_dict()
    assert d["trade_id"] == "t1"
    t2 = DCBacktestTrade.from_dict(d)
    assert t2.trade_id == "t1"

def test_dc_backtestmetrics_to_dict_from_dict():
    m = BacktestMetrics(
        total_pnl=10.0,
        total_return_pct=1.0,
        total_trades=2,
        winning_trades=1,
        losing_trades=1,
        win_rate=50.0,
        avg_win=10.0,
        avg_loss=-10.0,
        profit_factor=1.0,
        max_drawdown=2.0,
        max_drawdown_pct=1.0,
        sharpe_ratio=1.0,
        calmar_ratio=1.0,
        max_consecutive_losses=1,
        avg_trade_duration_hours=1.0
    )
    d = m.to_dict()
    assert d["total_pnl"] == 10.0
    m2 = BacktestMetrics.from_dict(d)
    assert m2.total_pnl == 10.0

def test_dc_backtestresult_to_dict_from_dict():
    m = BacktestMetrics(
        total_pnl=10.0,
        total_return_pct=1.0,
        total_trades=2,
        winning_trades=1,
        losing_trades=1,
        win_rate=50.0,
        avg_win=10.0,
        avg_loss=-10.0,
        profit_factor=1.0,
        max_drawdown=2.0,
        max_drawdown_pct=1.0,
        sharpe_ratio=1.0,
        calmar_ratio=1.0,
        max_consecutive_losses=1,
        avg_trade_duration_hours=1.0
    )
    t = DCBacktestTrade(
        timestamp="2025-01-01T00:00:00Z",
        market_1="BTC-USD",
        market_2="ETH-USD",
        side_1="BUY",
        side_2="SELL",
        size_1=1.0,
        size_2=2.0,
        entry_price_1=100.0,
        entry_price_2=200.0,
        z_score_entry=1.5,
        hedge_ratio=0.8,
        trade_id="t1"
    )
    r = DCBacktestResult(
        start_date="2025-01-01",
        end_date="2025-01-02",
        total_days=1,
        starting_balance=1000.0,
        ending_balance=1010.0,
        metrics=m,
        trades=[t],
        config_snapshot={},
        analysis_timestamp="2025-01-02T00:00:00Z",
        version="1.0"
    )
    d = r.to_dict()
    assert d["start_date"] == "2025-01-01"
    r2 = DCBacktestResult.from_dict(d)
    assert r2.start_date == "2025-01-01"

def test_cointegrationresult_to_dict_from_dict():
    c = CointegrationResult(
        base_market="BTC-USD",
        quote_market="ETH-USD",
        hedge_ratio=0.8,
        half_life=10.0,
        zero_crossings=5,
        p_value=0.01
    )
    d = c.to_dict()
    assert d["base_market"] == "BTC-USD"
    c2 = CointegrationResult.from_dict(d)
    assert c2.base_market == "BTC-USD"
