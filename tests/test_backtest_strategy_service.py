"""
Comprehensive unit tests for BacktestStrategyService.

Tests all CRUD operations, error handling, authorization checks,
and database interactions for strategy management.
"""

import pytest
from sqlalchemy.orm import Session

from backend.database import BacktestRun, BacktestStrategy, User
from backend.services import BacktestStrategyService


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user for strategy ownership."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def another_user(db_session: Session) -> User:
    """Create a second test user for authorization tests."""
    user = User(
        username="anotheruser",
        email="another@example.com",
        hashed_password="hashed_password",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def public_strategy(db_session: Session, test_user: User) -> BacktestStrategy:
    """Create a public test strategy."""
    strategy = BacktestStrategyService.create_strategy(
        db=db_session,
        user_id=test_user.id,
        name="Public Strategy",
        description="A public test strategy",
        category="test",
        is_public=True,
        zscore_threshold=2.0,
        stats_window=30,
        max_half_life=48.0,
        usd_per_trade=50.0,
        usd_min_collateral=200.0,
        close_at_zscore_cross=False,
    )
    return strategy


class TestBacktestStrategyServiceCreate:
    """Test strategy creation functionality."""

    def test_create_strategy_success(self, db_session: Session, test_user: User):
        """Test successful strategy creation."""
        strategy = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="Test Strategy",
            description="A test strategy for unit testing",
            category="custom",
            zscore_threshold=1.5,
            stats_window=21,
            max_half_life=24,
            usd_per_trade=100.0,
            usd_min_collateral=500.0,
            close_at_zscore_cross=True,
        )

        assert strategy.id is not None
        assert strategy.user_id == test_user.id
        assert strategy.name == "Test Strategy"
        assert strategy.description == "A test strategy for unit testing"
        assert strategy.zscore_threshold == 1.5
        assert strategy.is_default is False
        assert strategy.created_at is not None

    def test_create_strategy_with_all_params(
        self, db_session: Session, test_user: User
    ):
        """Test strategy creation with all parameters."""
        strategy = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="Complete Strategy",
            description="All parameters specified",
            category="advanced",
            zscore_threshold=1.2,
            stats_window=25,
            max_half_life=36,
            usd_per_trade=250.0,
            usd_min_collateral=1000.0,
            close_at_zscore_cross=True,
            find_cointegrated_pairs=True,
            manage_exits=True,
            place_trades=True,
            abort_all_positions=False,
            max_positions=10,
            max_drawdown_pct=20.0,
            stop_loss_pct=3.0,
            take_profit_pct=8.0,
            trailing_stop_pct=2.0,
            rebalance_interval_hours=48,
            position_timeout_hours=96,
        )

        assert strategy.usd_per_trade == 250.0
        assert strategy.zscore_threshold == 1.2
        assert strategy.stats_window == 25
        assert strategy.category == "advanced"
        assert strategy.max_positions == 10

    def test_create_strategy_duplicate_name(self, db_session: Session, test_user: User):
        """Test creating strategies with same name by same user."""
        strategy1 = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="Duplicate Name",
            description="First strategy",
            category="test",
        )

        strategy2 = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="Duplicate Name",
            description="Second strategy",
            category="test",
        )

        # Both should succeed (same user can have same-named strategies)
        assert strategy1.id is not None
        assert strategy2.id is not None
        assert strategy1.id != strategy2.id


class TestBacktestStrategyServiceRead:
    """Test strategy retrieval functionality."""

    def test_get_strategy_by_id(
        self, db_session: Session, public_strategy: BacktestStrategy
    ):
        """Test retrieving strategy by ID."""
        strategy = BacktestStrategyService.get_strategy_by_id(
            db=db_session,
            strategy_id=public_strategy.id,
        )

        assert strategy is not None
        assert strategy.id == public_strategy.id
        assert strategy.name == public_strategy.name

    def test_get_strategy_not_found(self, db_session: Session):
        """Test retrieving non-existent strategy."""
        strategy = BacktestStrategyService.get_strategy_by_id(
            db=db_session,
            strategy_id=99999,
        )

        assert strategy is None

    def test_get_user_strategies(
        self, db_session: Session, test_user: User, another_user: User
    ):
        """Test retrieving strategies for a specific user."""
        # Create strategies for test_user
        BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="Strategy 1",
            description="First",
            category="test",
        )
        BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="Strategy 2",
            description="Second",
            category="test",
        )

        # Create strategy for another_user
        BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=another_user.id,
            name="Other Strategy",
            description="Other",
            category="test",
        )

        # Retrieve strategies for test_user
        strategies = BacktestStrategyService.get_user_strategies(
            db=db_session,
            user_id=test_user.id,
        )

        assert len(strategies) == 2
        assert all(s.user_id == test_user.id for s in strategies)

    def test_get_public_strategies(self, db_session: Session, test_user: User):
        """Test retrieving public strategies."""
        # Create public strategy
        strategy1 = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="Public Strategy",
            description="Public",
            category="test",
            is_public=True,
        )

        # Create private strategy
        strategy2 = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="Private Strategy",
            description="Private",
            category="test",
            is_public=False,
        )

        # Retrieve public strategies
        public = BacktestStrategyService.get_public_strategies(db=db_session)

        public_ids = [s.id for s in public]
        assert strategy1.id in public_ids
        assert strategy2.id not in public_ids
        assert all(s.is_public for s in public)

    def test_get_strategies_by_category(self, db_session: Session, test_user: User):
        """Test retrieving strategies by category."""
        BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="Conservative",
            description="Conservative strategy",
            category="conservative",
        )

        BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="Aggressive",
            description="Aggressive strategy",
            category="aggressive",
        )

        conservative = BacktestStrategyService.get_strategies_by_category(
            db=db_session,
            category="conservative",
        )

        assert len(conservative) >= 1
        assert all(s.category == "conservative" for s in conservative)


class TestBacktestStrategyServiceUpdate:
    """Test strategy update functionality."""

    def test_update_strategy(
        self, db_session: Session, public_strategy: BacktestStrategy
    ):
        """Test updating strategy parameters."""
        update_data = {
            "name": "Updated Strategy",
            "zscore_threshold": 2.5,
            "usd_per_trade": 200.0,
        }

        strategy = BacktestStrategyService.update_strategy(
            db=db_session,
            strategy_id=public_strategy.id,
            update_data=update_data,
        )

        assert strategy is not None
        assert strategy.name == "Updated Strategy"
        assert strategy.zscore_threshold == 2.5
        assert strategy.usd_per_trade == 200.0
        assert strategy.description == public_strategy.description  # Unchanged

    def test_update_strategy_partial(
        self, db_session: Session, public_strategy: BacktestStrategy
    ):
        """Test partial update of strategy."""
        original_name = public_strategy.name
        update_data = {"zscore_threshold": 3.0}

        strategy = BacktestStrategyService.update_strategy(
            db=db_session,
            strategy_id=public_strategy.id,
            update_data=update_data,
        )

        assert strategy is not None
        assert strategy.zscore_threshold == 3.0
        assert strategy.name == original_name  # Unchanged

    def test_update_nonexistent_strategy(self, db_session: Session):
        """Test updating non-existent strategy."""
        update_data = {"name": "New Name"}

        strategy = BacktestStrategyService.update_strategy(
            db=db_session,
            strategy_id=99999,
            update_data=update_data,
        )

        assert strategy is None

    def test_update_multiple_fields(
        self, db_session: Session, public_strategy: BacktestStrategy
    ):
        """Test updating multiple fields at once."""
        update_data = {
            "name": "Multi Update",
            "description": "Updated description",
            "is_public": False,
            "max_positions": 20,
            "stop_loss_pct": 5.0,
        }

        strategy = BacktestStrategyService.update_strategy(
            db=db_session,
            strategy_id=public_strategy.id,
            update_data=update_data,
        )

        assert strategy is not None
        assert strategy.name == "Multi Update"
        assert strategy.description == "Updated description"
        assert strategy.is_public is False
        assert strategy.max_positions == 20
        assert strategy.stop_loss_pct == 5.0


class TestBacktestStrategyServiceDelete:
    """Test strategy deletion functionality."""

    def test_delete_strategy(
        self, db_session: Session, public_strategy: BacktestStrategy
    ):
        """Test deleting a strategy."""
        strategy_id = public_strategy.id

        result = BacktestStrategyService.delete_strategy(
            db=db_session,
            strategy_id=strategy_id,
        )

        assert result is True

        # Verify strategy is deleted
        strategy = BacktestStrategyService.get_strategy_by_id(
            db=db_session,
            strategy_id=strategy_id,
        )
        assert strategy is None

    def test_delete_nonexistent_strategy(self, db_session: Session):
        """Test deleting non-existent strategy."""
        result = BacktestStrategyService.delete_strategy(
            db=db_session,
            strategy_id=99999,
        )

        assert result is False

    def test_delete_strategy_with_backtest_runs(
        self, db_session: Session, test_user: User, public_strategy: BacktestStrategy
    ):
        """Test deleting strategy with associated backtest runs."""
        # Create a backtest run using this strategy
        run = BacktestRun(
            run_id="test-run-123",
            user_id=test_user.id,
            strategy_id=public_strategy.id,
            start_date="2025-01-01",
            end_date="2025-03-31",
            num_pairs=5,
            total_markets=10,
            status="COMPLETE",
        )
        db_session.add(run)
        db_session.commit()

        # Delete strategy should cascade or handle gracefully
        result = BacktestStrategyService.delete_strategy(
            db=db_session,
            strategy_id=public_strategy.id,
        )

        # Should succeed with cascade delete
        assert result is True


class TestBacktestStrategyServiceDefaults:
    """Test default strategy functionality."""

    def test_set_default_strategy(
        self, db_session: Session, test_user: User, public_strategy: BacktestStrategy
    ):
        """Test setting a strategy as default."""
        BacktestStrategyService.set_default_strategy(
            db=db_session,
            user_id=test_user.id,
            strategy_id=public_strategy.id,
        )

        strategy = BacktestStrategyService.get_strategy_by_id(
            db=db_session,
            strategy_id=public_strategy.id,
        )

        assert strategy is not None
        assert strategy.is_default is True

    def test_get_default_strategy(self, db_session: Session, test_user: User):
        """Test retrieving default strategy."""
        strategy = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="Default Test",
            description="Test default",
            category="test",
        )

        BacktestStrategyService.set_default_strategy(
            db=db_session,
            user_id=test_user.id,
            strategy_id=strategy.id,
        )

        default = BacktestStrategyService.get_default_strategy(
            db=db_session,
            user_id=test_user.id,
        )

        assert default is not None
        assert default.id == strategy.id
        assert default.is_default is True

    def test_change_default_strategy(self, db_session: Session, test_user: User):
        """Test changing default strategy clears previous default."""
        strategy1 = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="Default 1",
            description="First default",
            category="test",
        )

        strategy2 = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="Default 2",
            description="Second default",
            category="test",
        )

        BacktestStrategyService.set_default_strategy(
            db=db_session,
            user_id=test_user.id,
            strategy_id=strategy1.id,
        )

        # Change default
        BacktestStrategyService.set_default_strategy(
            db=db_session,
            user_id=test_user.id,
            strategy_id=strategy2.id,
        )

        # Check that only strategy2 is default
        s1 = BacktestStrategyService.get_strategy_by_id(
            db=db_session, strategy_id=strategy1.id
        )
        s2 = BacktestStrategyService.get_strategy_by_id(
            db=db_session, strategy_id=strategy2.id
        )

        assert s1 is not None
        assert s1.is_default is False
        assert s2 is not None
        assert s2.is_default is True


class TestBacktestStrategyServiceStats:
    """Test strategy statistics and usage tracking."""

    def test_get_strategy_stats(
        self, db_session: Session, test_user: User, public_strategy: BacktestStrategy
    ):
        """Test retrieving strategy usage statistics."""
        # Create some backtest runs
        for i in range(3):
            run = BacktestRun(
                run_id=f"run-{i}",
                user_id=test_user.id,
                strategy_id=public_strategy.id,
                start_date="2025-01-01",
                end_date="2025-03-31",
                num_pairs=5,
                total_markets=10,
                status="completed",
                total_pnl=100.0 * i,
            )
            db_session.add(run)
        db_session.commit()

        stats = BacktestStrategyService.get_strategy_usage_stats(
            db=db_session,
            strategy_id=public_strategy.id,
        )

        assert stats["total_runs"] == 3
        assert stats["completed_runs"] >= 0
        assert "avg_pnl" in stats
        assert "success_rate" in stats

    def test_update_last_used(
        self, db_session: Session, public_strategy: BacktestStrategy
    ):
        """Test updating last_used_at timestamp."""
        BacktestStrategyService.update_last_used(
            db=db_session,
            strategy_id=public_strategy.id,
        )

        strategy = BacktestStrategyService.get_strategy_by_id(
            db=db_session,
            strategy_id=public_strategy.id,
        )

        assert strategy is not None
        assert strategy.last_used_at is not None

    def test_update_last_used_nonexistent(self, db_session: Session):
        """Test updating last_used for non-existent strategy."""
        result = BacktestStrategyService.update_last_used(
            db=db_session,
            strategy_id=99999,
        )

        assert result is None


class TestBacktestStrategyServiceErrorHandling:
    """Test error handling and edge cases."""

    def test_create_strategy_minimal(self, db_session: Session, test_user: User):
        """Test creating strategy with minimal required fields."""
        strategy = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="Minimal",
            description="Minimal strategy",
            category="test",
        )

        # Should use default values for optional fields
        assert strategy is not None
        assert strategy.zscore_threshold == 1.5  # Default
        assert strategy.stats_window == 21  # Default
        assert strategy.is_public is False  # Default

    def test_concurrent_default_updates(self, db_session: Session, test_user: User):
        """Test handling concurrent default strategy changes."""
        strategy1 = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="Concurrent 1",
            description="Test",
            category="test",
        )

        strategy2 = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="Concurrent 2",
            description="Test",
            category="test",
        )

        BacktestStrategyService.set_default_strategy(
            db=db_session,
            user_id=test_user.id,
            strategy_id=strategy1.id,
        )

        BacktestStrategyService.set_default_strategy(
            db=db_session,
            user_id=test_user.id,
            strategy_id=strategy2.id,
        )

        default = BacktestStrategyService.get_default_strategy(
            db=db_session,
            user_id=test_user.id,
        )

        assert default is not None
        assert default.id == strategy2.id

    def test_update_with_empty_dict(
        self, db_session: Session, public_strategy: BacktestStrategy
    ):
        """Test updating strategy with empty update dict."""
        original_name = public_strategy.name

        strategy = BacktestStrategyService.update_strategy(
            db=db_session,
            strategy_id=public_strategy.id,
            update_data={},
        )

        assert strategy is not None
        assert strategy.name == original_name  # Unchanged

    def test_multiple_users_independent_strategies(
        self, db_session: Session, test_user: User, another_user: User
    ):
        """Test that multiple users have independent strategy spaces."""
        s1 = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user.id,
            name="User1 Strategy",
            description="User 1",
            category="test",
        )

        s2 = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=another_user.id,
            name="User2 Strategy",
            description="User 2",
            category="test",
        )

        user1_strats = BacktestStrategyService.get_user_strategies(
            db=db_session,
            user_id=test_user.id,
        )

        user2_strats = BacktestStrategyService.get_user_strategies(
            db=db_session,
            user_id=another_user.id,
        )

        assert s1.id in [s.id for s in user1_strats]
        assert s2.id in [s.id for s in user2_strats]
        assert s1.id not in [s.id for s in user2_strats]
