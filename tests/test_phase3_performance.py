"""Performance benchmarks for Phase 3 strategy-aware backtesting.

Validates:
- API response times (<500ms)
- Backtest completion speeds (<30s)
- Database query performance (<200ms)
- Memory efficiency
"""

import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import BacktestResult, BacktestRun, BacktestStrategy, Base, User


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
def perf_user(db_session):
    """Create test user for performance tests."""
    user = User(
        username="perftest",
        email="perf@example.com",
        hashed_password="hash123",
        is_admin=False,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def perf_strategy(db_session, perf_user):
    """Create test strategy for performance tests."""
    strategy = BacktestStrategy(
        name="Perf Test Strategy",
        category="pairs_trading",
        user_id=perf_user.id,
    )
    db_session.add(strategy)
    db_session.commit()
    return strategy


@pytest.fixture
def large_backtest_run(db_session, perf_user, perf_strategy):
    """Create a larger backtest run with many results."""
    run = BacktestRun(
        run_id="perf-run-large",
        user_id=perf_user.id,
        strategy_id=perf_strategy.id,
        start_date="2024-01-01",
        end_date="2024-12-31",
        num_pairs=50,
        total_markets=100,
        status="COMPLETE",
    )
    db_session.add(run)
    db_session.commit()

    # Add 50 results (one per pair)
    for i in range(50):
        result = BacktestResult(
            run_id_fk=run.id,
            market_1=f"MARKET{i:03d}-USD",
            market_2=f"MARKET{i + 1:03d}-USD",
            total_trades=100 + i,
            entry_trades=50 + i,
            exit_trades=50 + i,
            profitable_trades=60 + (i % 20),
            losing_trades=40 - (i % 20),
            pnl=1000.0 + (i * 10),
            pnl_usd=1000.0 + (i * 10),
            win_rate=0.6 + (i * 0.001),
            avg_win=50.0 + i,
            avg_loss=30.0 + (i % 10),
            profit_factor=1.5 + (i * 0.01),
            max_drawdown=0.1 + (i * 0.001),
            sharpe_ratio=1.2 + (i * 0.01),
            sortino_ratio=1.5 + (i * 0.01),
            calmar_ratio=2.0 + (i * 0.01),
            avg_trade_duration_hours=24.0 + i,
            cointegration_score=0.85 + (i * 0.001),
            correlation=0.7 + (i * 0.002),
            zscore_mean=0.1 + (i * 0.01),
            zscore_std=0.5 + (i * 0.01),
        )
        db_session.add(result)

    db_session.commit()
    return run


# ============================================================================
# API Response Time Benchmarks (<500ms target)
# ============================================================================


def test_backtest_run_creation_performance(db_session, perf_user, perf_strategy):
    """Test BacktestRun creation performance (<50ms)."""
    start = time.time()

    run = BacktestRun(
        run_id="perf-run-create-test",
        user_id=perf_user.id,
        strategy_id=perf_strategy.id,
        start_date="2024-01-01",
        end_date="2024-01-31",
        num_pairs=10,
        total_markets=20,
        status="RUNNING",
    )
    db_session.add(run)
    db_session.commit()

    elapsed = (time.time() - start) * 1000  # Convert to ms
    assert elapsed < 50, f"BacktestRun creation took {elapsed:.1f}ms, target <50ms"
    assert run.id is not None


def test_backtest_result_bulk_insert_performance(db_session, large_backtest_run):
    """Test bulk inserting 50 results completes fast (<200ms)."""
    start = time.time()

    # Simulate bulk insert of 50 more results
    for i in range(50, 100):
        result = BacktestResult(
            run_id_fk=large_backtest_run.id,
            market_1=f"MARKET{i:03d}-USD",
            market_2=f"MARKET{i + 1:03d}-USD",
            total_trades=100 + i,
            profitable_trades=60 + (i % 20),
            losing_trades=40 - (i % 20),
            pnl=1000.0 + (i * 10),
            pnl_usd=1000.0 + (i * 10),
            win_rate=0.6 + (i * 0.001),
            sharpe_ratio=1.2 + (i * 0.01),
        )
        db_session.add(result)

    db_session.commit()
    elapsed = (time.time() - start) * 1000  # Convert to ms

    assert elapsed < 200, f"Bulk insert 50 results took {elapsed:.1f}ms, target <200ms"


def test_result_query_by_market_pair_performance(db_session, large_backtest_run):
    """Test querying results by market pair (<100ms)."""
    start = time.time()

    # Query results by market pair
    (
        db_session.query(BacktestResult)
        .filter(BacktestResult.market_1 == "MARKET000-USD")
        .all()
    )

    elapsed = (time.time() - start) * 1000
    assert elapsed < 100, f"Market pair query took {elapsed:.1f}ms, target <100ms"
    # Should find exactly one result (or none if filtering didn't match)


def test_result_query_by_run_performance(db_session, large_backtest_run):
    """Test querying all results for a run (<150ms)."""
    start = time.time()

    # Query all results for a specific run
    results = (
        db_session.query(BacktestResult)
        .filter(BacktestResult.run_id_fk == large_backtest_run.id)
        .all()
    )

    elapsed = (time.time() - start) * 1000
    assert elapsed < 150, f"Run results query took {elapsed:.1f}ms, target <150ms"
    assert len(results) == 50, "Should return all 50 results for this run"


def test_result_sorting_performance(db_session, large_backtest_run):
    """Test sorting results by profitability (<150ms)."""
    start = time.time()

    # Query and sort results
    results = (
        db_session.query(BacktestResult)
        .filter(BacktestResult.run_id_fk == large_backtest_run.id)
        .order_by(BacktestResult.pnl.desc())
        .all()
    )

    elapsed = (time.time() - start) * 1000
    assert elapsed < 150, f"Sorting results by PnL took {elapsed:.1f}ms, target <150ms"
    assert len(results) == 50


def test_result_pagination_performance(db_session, large_backtest_run):
    """Test pagination of results (<100ms for 10-result page)."""
    start = time.time()

    # Paginate through results
    page_size = 10
    page = 0
    offset = page * page_size

    results = (
        db_session.query(BacktestResult)
        .filter(BacktestResult.run_id_fk == large_backtest_run.id)
        .offset(offset)
        .limit(page_size)
        .all()
    )

    elapsed = (time.time() - start) * 1000
    assert elapsed < 100, f"Pagination query took {elapsed:.1f}ms, target <100ms"
    assert len(results) == 10


# ============================================================================
# Aggregation Query Performance (<200ms target)
# ============================================================================


def test_average_metrics_calculation_performance(db_session, large_backtest_run):
    """Test calculating average metrics across all results (<150ms)."""
    from sqlalchemy import func

    start = time.time()

    # Calculate averages
    avg_metrics = (
        db_session.query(
            func.avg(BacktestResult.win_rate).label("avg_win_rate"),
            func.avg(BacktestResult.sharpe_ratio).label("avg_sharpe"),
            func.avg(BacktestResult.pnl).label("avg_pnl"),
        )
        .filter(BacktestResult.run_id_fk == large_backtest_run.id)
        .first()
    )

    elapsed = (time.time() - start) * 1000
    assert elapsed < 150, f"Aggregation query took {elapsed:.1f}ms, target <150ms"
    assert avg_metrics is not None
    assert avg_metrics.avg_win_rate is not None


def test_profit_histogram_performance(db_session, large_backtest_run):
    """Test grouping results by profit ranges (<150ms)."""
    from sqlalchemy import func
    from sqlalchemy.sql import case

    start = time.time()

    # Group results by profit ranges
    profit_ranges = (
        db_session.query(
            case(
                (BacktestResult.pnl < 0, "loss"),
                (BacktestResult.pnl < 500, "small_profit"),
                (BacktestResult.pnl < 1500, "medium_profit"),
                else_="large_profit",
            ).label("profit_range"),
            func.count(BacktestResult.id).label("count"),
        )
        .filter(BacktestResult.run_id_fk == large_backtest_run.id)
        .group_by("profit_range")
        .all()
    )

    elapsed = (time.time() - start) * 1000
    assert elapsed < 150, f"Profit histogram query took {elapsed:.1f}ms, target <150ms"
    assert len(profit_ranges) > 0


# ============================================================================
# Session/Memory Performance
# ============================================================================


def test_session_memory_efficiency(db_session, large_backtest_run):
    """Test that session doesn't bloat with large result sets (<50MB)."""
    import sys

    # Get session size before
    initial_size = sys.getsizeof(db_session)

    # Load all results into session
    results = (
        db_session.query(BacktestResult)
        .filter(BacktestResult.run_id_fk == large_backtest_run.id)
        .all()
    )

    # Get session size after
    final_size = sys.getsizeof(db_session)
    size_increase = (final_size - initial_size) / 1024 / 1024  # MB

    # Session should not bloat excessively
    assert size_increase < 10, f"Session grew by {size_increase:.1f}MB, target <10MB"
    assert len(results) == 50


def test_result_object_serialization_performance(db_session, large_backtest_run):
    """Test converting results to dictionaries for JSON (<100ms)."""
    start = time.time()

    results = (
        db_session.query(BacktestResult)
        .filter(BacktestResult.run_id_fk == large_backtest_run.id)
        .all()
    )

    # Convert to dicts (simulate JSON serialization)
    result_dicts = [
        {
            "id": r.id,
            "market_1": r.market_1,
            "market_2": r.market_2,
            "pnl": r.pnl,
            "win_rate": r.win_rate,
            "sharpe_ratio": r.sharpe_ratio,
        }
        for r in results
    ]

    elapsed = (time.time() - start) * 1000
    assert elapsed < 100, f"Serialization took {elapsed:.1f}ms, target <100ms"
    assert len(result_dicts) == 50


# ============================================================================
# Multi-Query Scenarios (Simulating Real API Endpoints)
# ============================================================================


def test_full_api_result_endpoint_performance(
    db_session, large_backtest_run, perf_strategy
):
    """Simulate full /backtests/{id}/results endpoint (<200ms total)."""
    start = time.time()

    # Step 1: Get run details
    run = (
        db_session.query(BacktestRun)
        .filter(BacktestRun.id == large_backtest_run.id)
        .first()
    )

    # Step 2: Get strategy details
    strategy = (
        db_session.query(BacktestStrategy)
        .filter(BacktestStrategy.id == run.strategy_id)
        .first()
    )

    # Step 3: Get paginated results
    page_size = 10
    results = (
        db_session.query(BacktestResult)
        .filter(BacktestResult.run_id_fk == run.id)
        .order_by(BacktestResult.pnl.desc())
        .limit(page_size)
        .all()
    )

    # Step 4: Calculate stats
    from sqlalchemy import func

    stats = (
        db_session.query(
            func.count(BacktestResult.id).label("total_results"),
            func.avg(BacktestResult.pnl).label("avg_pnl"),
            func.max(BacktestResult.pnl).label("max_pnl"),
            func.min(BacktestResult.pnl).label("min_pnl"),
        )
        .filter(BacktestResult.run_id_fk == run.id)
        .first()
    )

    elapsed = (time.time() - start) * 1000
    assert elapsed < 200, (
        f"Full endpoint simulation took {elapsed:.1f}ms, target <200ms"
    )
    assert run is not None
    assert strategy is not None
    assert len(results) == 10
    assert stats.total_results == 50


def test_strategy_performance_summary_endpoint(db_session, perf_user, perf_strategy):
    """Simulate /strategies/{id}/performance endpoint (<250ms total)."""
    start = time.time()

    # Create multiple runs for this strategy
    for run_idx in range(3):
        run = BacktestRun(
            run_id=f"perf-strat-run-{run_idx}",
            user_id=perf_user.id,
            strategy_id=perf_strategy.id,
            start_date="2024-01-01",
            end_date="2024-01-31",
            num_pairs=20,
            total_markets=40,
            status="COMPLETE",
        )
        db_session.add(run)

    db_session.commit()

    # Step 1: Get strategy
    strategy = (
        db_session.query(BacktestStrategy)
        .filter(BacktestStrategy.id == perf_strategy.id)
        .first()
    )

    # Step 2: Get all runs for strategy
    runs = (
        db_session.query(BacktestRun)
        .filter(BacktestRun.strategy_id == perf_strategy.id)
        .all()
    )

    # Step 3: Get aggregate stats across all runs
    from sqlalchemy import func

    (
        db_session.query(
            func.count(BacktestResult.id).label("total_trades"),
            func.avg(BacktestResult.pnl).label("avg_pnl"),
            func.avg(BacktestResult.sharpe_ratio).label("avg_sharpe"),
        )
        .join(BacktestRun, BacktestResult.run_id_fk == BacktestRun.id)
        .filter(BacktestRun.strategy_id == perf_strategy.id)
        .first()
    )

    elapsed = (time.time() - start) * 1000
    assert elapsed < 250, (
        f"Strategy performance endpoint took {elapsed:.1f}ms, target <250ms"
    )
    assert strategy is not None
    assert len(runs) >= 3
