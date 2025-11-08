"""Integration tests for Phase 3 strategy-aware backtesting."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models import BacktestTrade
from backend.database import BacktestRun, BacktestStrategy, Base, User


@pytest.fixture(scope="function")
def db_engine():
    """Create in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create database session."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_user(db_session):
    """Create test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hash123",
        is_admin=False,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_strategy(db_session, test_user):
    """Create test strategy."""
    strategy = BacktestStrategy(
        name="Test Strategy",
        category="pairs_trading",
        user_id=test_user.id,
    )
    db_session.add(strategy)
    db_session.commit()
    return strategy


@pytest.fixture
def test_run(db_session, test_user, test_strategy):
    """Create test backtest run."""
    run = BacktestRun(
        run_id="test-run-001",
        user_id=test_user.id,
        strategy_id=test_strategy.id,
        start_date="2024-01-01",
        end_date="2024-01-31",
        num_pairs=5,
        total_markets=10,
        status="COMPLETE",
    )
    db_session.add(run)
    db_session.commit()
    return run


def test_trade_has_strategy_metadata():
    """Test BacktestTrade includes strategy fields."""
    trade = BacktestTrade(
        timestamp="2024-01-15T10:30:00Z",
        market_1="BTC-USD",
        market_2="ETH-USD",
        side_1="BUY",
        side_2="SELL",
        size_1=0.5,
        size_2=5.0,
        entry_price_1=50000.0,
        entry_price_2=2000.0,
        z_score_entry=2.5,
        hedge_ratio=0.1,
        trade_id="trade-001",
        strategy_id=1,
        strategy_name="Test",
        strategy_zscore_threshold=2.0,
    )
    assert trade.strategy_id == 1
    assert trade.strategy_name == "Test"
    assert trade.strategy_zscore_threshold == 2.0


def test_result_has_market_data(db_session, test_run):
    """Test BacktestResult stores market pair data."""
    from backend.database import BacktestResult as DBBacktestResult

    result = DBBacktestResult(
        run_id_fk=test_run.id,
        market_1="BTC-USD",
        market_2="ETH-USD",
        total_trades=10,
        profitable_trades=6,
        losing_trades=4,
        win_rate=0.6,
        pnl=1000.0,
        pnl_usd=1000.0,
        profit_factor=1.5,
        sharpe_ratio=1.2,
    )
    db_session.add(result)
    db_session.commit()

    assert result.market_1 == "BTC-USD"
    assert result.market_2 == "ETH-USD"
    assert result.pnl == 1000.0


def test_backtest_run_has_strategy(db_session, test_user, test_strategy):
    """Test BacktestRun links to BacktestStrategy."""
    run = BacktestRun(
        run_id="test-run-002",
        user_id=test_user.id,
        strategy_id=test_strategy.id,
        start_date="2024-01-01",
        end_date="2024-01-31",
        num_pairs=5,
        total_markets=10,
        status="COMPLETE",
    )
    db_session.add(run)
    db_session.commit()

    assert run.strategy_id == test_strategy.id
    assert run.strategy is not None
    assert run.strategy.name == "Test Strategy"


def test_multiple_strategies_different_runs(db_session, test_user):
    """Test multiple strategies can have different runs."""
    strat1 = BacktestStrategy(
        name="Strategy 1",
        category="pairs_trading",
        user_id=test_user.id,
    )
    strat2 = BacktestStrategy(
        name="Strategy 2",
        category="pairs_trading",
        user_id=test_user.id,
    )
    db_session.add_all([strat1, strat2])
    db_session.commit()

    run1 = BacktestRun(
        run_id="run-1",
        user_id=test_user.id,
        strategy_id=strat1.id,
        start_date="2024-01-01",
        end_date="2024-01-31",
        num_pairs=3,
        total_markets=6,
        status="COMPLETE",
    )
    run2 = BacktestRun(
        run_id="run-2",
        user_id=test_user.id,
        strategy_id=strat2.id,
        start_date="2024-02-01",
        end_date="2024-02-28",
        num_pairs=5,
        total_markets=10,
        status="COMPLETE",
    )
    db_session.add_all([run1, run2])
    db_session.commit()

    # Verify different strategies have different runs
    assert run1.strategy_id == strat1.id
    assert run2.strategy_id == strat2.id
    assert run1.strategy_id != run2.strategy_id
    assert run1.id != run2.id


def test_strategy_has_multiple_runs(db_session, test_user):
    """Test one strategy can have multiple runs."""
    strategy = BacktestStrategy(
        name="Multi-Run Strategy",
        category="pairs_trading",
        user_id=test_user.id,
    )
    db_session.add(strategy)
    db_session.commit()

    run1 = BacktestRun(
        run_id="multi-run-1",
        user_id=test_user.id,
        strategy_id=strategy.id,
        start_date="2024-01-01",
        end_date="2024-01-31",
        num_pairs=5,
        total_markets=10,
        status="COMPLETE",
    )
    run2 = BacktestRun(
        run_id="multi-run-2",
        user_id=test_user.id,
        strategy_id=strategy.id,
        start_date="2024-02-01",
        end_date="2024-02-28",
        num_pairs=5,
        total_markets=10,
        status="COMPLETE",
    )
    db_session.add_all([run1, run2])
    db_session.commit()

    # Verify same strategy has multiple runs
    runs = db_session.query(BacktestRun).filter_by(strategy_id=strategy.id).all()
    assert len(runs) == 2
    assert all(r.strategy_id == strategy.id for r in runs)
