"""
Unit tests for SQLAlchemy Core database operations.
Tests use the Database class with raw SQL, no ORM.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from datetime import datetime, timezone
from db_core import Database

class TestUsers:
    """Test user database operations."""

    def test_create_user(self):
        user = Database.create_user(
            username="alice_test",
            email="alice_test@example.com",
            hashed_password="hashed_pwd",
            full_name="Alice Test"
        )
        assert user is not None
        assert user['username'] == "alice_test"
        assert user['email'] == "alice_test@example.com"
        assert user['is_active'] == True

    def test_get_user_by_id(self):
        user = Database.create_user(
            username="bob_test",
            email="bob_test@example.com",
            hashed_password="hashed_pwd"
        )
        retrieved = Database.get_user_by_id(user['id'])
        assert retrieved is not None
        assert retrieved['id'] == user['id']
        assert retrieved['username'] == "bob_test"

    def test_get_user_by_username(self):
        Database.create_user(
            username="charlie_test",
            email="charlie_test@example.com",
            hashed_password="hashed_pwd"
        )
        user = Database.get_user_by_username("charlie_test")
        assert user is not None
        assert user['username'] == "charlie_test"

    def test_get_user_by_email(self):
        Database.create_user(
            username="diana_test",
            email="diana_test@example.com",
            hashed_password="hashed_pwd"
        )
        user = Database.get_user_by_email("diana_test@example.com")
        assert user is not None
        assert user['email'] == "diana_test@example.com"

    def test_update_user(self):
        user = Database.create_user(
            username="eve_test",
            email="eve_test@example.com",
            hashed_password="hashed_pwd"
        )
        updated = Database.update_user(user['id'], full_name="Eve Updated")
        assert updated is not None
        assert updated['full_name'] == "Eve Updated"

    def test_delete_user(self):
        user = Database.create_user(
            username="frank_test",
            email="frank_test@example.com",
            hashed_password="hashed_pwd"
        )
        success = Database.delete_user(user['id'])
        assert success == True
        retrieved = Database.get_user_by_id(user['id'])
        assert retrieved is None


class TestBacktestRuns:
    """Test backtest run database operations."""

    def setup_method(self):
        """Create a user for each test."""
        self.user = Database.create_user(
            username=f"user_{datetime.now().timestamp()}",
            email=f"user_{datetime.now().timestamp()}@example.com",
            hashed_password="hashed"
        )

    def test_create_backtest_run(self):
        run = Database.create_backtest_run(
            run_id="run_001",
            start_date="2025-01-01",
            end_date="2025-01-02",
            num_pairs=5,
            total_markets=10,
            user_id=self.user['id']
        )
        assert run is not None
        assert run['run_id'] == "run_001"
        assert run['status'] == "running"

    def test_get_backtest_run_by_id(self):
        run = Database.create_backtest_run(
            run_id="run_002",
            start_date="2025-01-01",
            end_date="2025-01-02",
            num_pairs=5,
            total_markets=10
        )
        retrieved = Database.get_backtest_run_by_id(run['id'])
        assert retrieved is not None
        assert retrieved['id'] == run['id']

    def test_get_backtest_run_by_run_id(self):
        Database.create_backtest_run(
            run_id="run_unique_003",
            start_date="2025-01-01",
            end_date="2025-01-02",
            num_pairs=5,
            total_markets=10
        )
        run = Database.get_backtest_run_by_run_id("run_unique_003")
        assert run is not None
        assert run['run_id'] == "run_unique_003"

    def test_get_user_backtest_runs(self):
        run1 = Database.create_backtest_run(
            run_id="user_run_001",
            start_date="2025-01-01",
            end_date="2025-01-02",
            num_pairs=5,
            total_markets=10,
            user_id=self.user['id']
        )
        run2 = Database.create_backtest_run(
            run_id="user_run_002",
            start_date="2025-01-02",
            end_date="2025-01-03",
            num_pairs=5,
            total_markets=10,
            user_id=self.user['id']
        )
        runs = Database.get_user_backtest_runs(self.user['id'])
        assert len(runs) >= 2

    def test_update_backtest_run(self):
        run = Database.create_backtest_run(
            run_id="run_update",
            start_date="2025-01-01",
            end_date="2025-01-02",
            num_pairs=5,
            total_markets=10
        )
        updated = Database.update_backtest_run(run['id'], status="completed", total_pnl=100.5)
        assert updated is not None
        assert updated['status'] == "completed"
        assert updated['total_pnl'] == 100.5


class TestBacktestResults:
    """Test backtest result database operations."""

    def setup_method(self):
        """Create a backtest run for each test."""
        self.run = Database.create_backtest_run(
            run_id=f"result_run_{datetime.now().timestamp()}",
            start_date="2025-01-01",
            end_date="2025-01-02",
            num_pairs=5,
            total_markets=10
        )

    def test_create_backtest_result(self):
        result = Database.create_backtest_result(
            run_id_fk=self.run['id'],
            market_1="BTC-USD",
            market_2="ETH-USD",
            total_trades=10,
            pnl=50.0,
            win_rate=0.6
        )
        assert result is not None
        assert result['market_1'] == "BTC-USD"
        assert result['market_2'] == "ETH-USD"
        assert result['pnl'] == 50.0

    def test_get_backtest_result_by_id(self):
        result = Database.create_backtest_result(
            run_id_fk=self.run['id'],
            market_1="BTC-USD",
            market_2="ETH-USD"
        )
        retrieved = Database.get_backtest_result_by_id(result['id'])
        assert retrieved is not None
        assert retrieved['id'] == result['id']

    def test_get_run_results(self):
        Database.create_backtest_result(
            run_id_fk=self.run['id'],
            market_1="BTC-USD",
            market_2="ETH-USD"
        )
        Database.create_backtest_result(
            run_id_fk=self.run['id'],
            market_1="XRP-USD",
            market_2="SOL-USD"
        )
        results = Database.get_run_results(self.run['id'])
        assert len(results) >= 2


class TestBacktestCandles:
    """Test backtest candle database operations."""

    def setup_method(self):
        """Create a backtest run for each test."""
        self.run = Database.create_backtest_run(
            run_id=f"candle_run_{datetime.now().timestamp()}",
            start_date="2025-01-01",
            end_date="2025-01-02",
            num_pairs=5,
            total_markets=10
        )

    def test_create_backtest_candle(self):
        now = datetime.now(timezone.utc)
        candle = Database.create_backtest_candle(
            run_id_fk=self.run['id'],
            market="BTC-USD",
            timestamp=now,
            open_price=100.0,
            high_price=110.0,
            low_price=95.0,
            close_price=105.0,
            volume=1000.0,
            resolution="1HOUR"
        )
        assert candle is not None
        assert candle['market'] == "BTC-USD"
        assert candle['open_price'] == 100.0

    def test_get_candles_by_run_id(self):
        now = datetime.now(timezone.utc)
        Database.create_backtest_candle(
            run_id_fk=self.run['id'],
            market="BTC-USD",
            timestamp=now,
            open_price=100.0,
            high_price=110.0,
            low_price=95.0,
            close_price=105.0,
            volume=1000.0
        )
        candles = Database.get_candles_by_run_id(self.run['id'])
        assert len(candles) >= 1
        assert candles[0]['market'] == "BTC-USD"

    def test_get_markets_by_run_id(self):
        now = datetime.now(timezone.utc)
        Database.create_backtest_candle(
            run_id_fk=self.run['id'],
            market="BTC-USD",
            timestamp=now,
            open_price=100.0,
            high_price=110.0,
            low_price=95.0,
            close_price=105.0,
            volume=1000.0
        )
        Database.create_backtest_candle(
            run_id_fk=self.run['id'],
            market="ETH-USD",
            timestamp=now,
            open_price=100.0,
            high_price=110.0,
            low_price=95.0,
            close_price=105.0,
            volume=1000.0
        )
        markets = Database.get_markets_by_run_id(self.run['id'])
        assert len(markets) >= 2
        assert "BTC-USD" in markets
        assert "ETH-USD" in markets


class TestStrategies:
    """Test strategy database operations."""

    def setup_method(self):
        """Create a user for each test."""
        self.user = Database.create_user(
            username=f"strat_user_{datetime.now().timestamp()}",
            email=f"strat_user_{datetime.now().timestamp()}@example.com",
            hashed_password="hashed"
        )

    def test_create_strategy(self):
        strategy = Database.create_strategy(
            name="Test Strategy",
            user_id=self.user['id'],
            zscore_threshold=2.0,
            category="balanced"
        )
        assert strategy is not None
        assert strategy['name'] == "Test Strategy"
        assert strategy['user_id'] == self.user['id']

    def test_get_strategy_by_id(self):
        strategy = Database.create_strategy(
            name="Get Test Strategy",
            user_id=self.user['id']
        )
        retrieved = Database.get_strategy_by_id(strategy['id'])
        assert retrieved is not None
        assert retrieved['id'] == strategy['id']

    def test_get_user_strategies(self):
        Database.create_strategy(
            name="Strategy 1",
            user_id=self.user['id']
        )
        Database.create_strategy(
            name="Strategy 2",
            user_id=self.user['id']
        )
        strategies = Database.get_user_strategies(self.user['id'])
        assert len(strategies) >= 2

    def test_update_strategy(self):
        strategy = Database.create_strategy(
            name="Update Strategy",
            user_id=self.user['id']
        )
        updated = Database.update_strategy(strategy['id'], name="Updated Strategy")
        assert updated is not None
        assert updated['name'] == "Updated Strategy"


class TestAuditLogs:
    """Test audit log database operations."""

    def setup_method(self):
        """Create a user for each test."""
        self.user = Database.create_user(
            username=f"audit_user_{datetime.now().timestamp()}",
            email=f"audit_user_{datetime.now().timestamp()}@example.com",
            hashed_password="hashed"
        )

    def test_create_audit_log(self):
        log = Database.create_audit_log(
            action="login",
            resource_type="user",
            user_id=self.user['id'],
            ip_address="192.168.1.1"
        )
        assert log is not None
        assert log['action'] == "login"
        assert log['resource_type'] == "user"

    def test_get_audit_log_by_id(self):
        log = Database.create_audit_log(
            action="update",
            resource_type="strategy",
            user_id=self.user['id']
        )
        retrieved = Database.get_audit_log_by_id(log['id'])
        assert retrieved is not None
        assert retrieved['id'] == log['id']

    def test_get_user_audit_logs(self):
        Database.create_audit_log(
            action="login",
            resource_type="user",
            user_id=self.user['id']
        )
        Database.create_audit_log(
            action="logout",
            resource_type="user",
            user_id=self.user['id']
        )
        logs = Database.get_user_audit_logs(self.user['id'])
        assert len(logs) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
