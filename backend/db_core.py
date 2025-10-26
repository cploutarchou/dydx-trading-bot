"""
Database service layer using SQLAlchemy Core (raw SQL).
No ORM classes - just raw SQL queries with Table objects.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from sqlalchemy import create_engine, select, insert, update, delete, text
from sqlalchemy.pool import StaticPool

import config.config
from schemas import (
    metadata,
    users, audit_logs, backtest_runs, backtest_results, backtest_logs,
    backtest_trades, backtest_positions, backtest_candles, trade_logs,
    bot_settings, redis_settings, backtest_strategies, strategy_version_history,
    strategy_execution_states, backtest_comparisons, dydx_keys, dydx_key_settings
)

# Database URL (can be configured via environment variable)
DATABASE_URL = config.config.DatabaseSettings().dsn

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL logging
    pool_pre_ping=True,
)

class Database:
    """Core database operations using SQLAlchemy Core (raw SQL)."""

    @staticmethod
    def get_connection():
        """Get a database connection."""
        return engine.connect()

    @staticmethod
    def get_session():
        """Get a database session (connection with transaction support)."""
        return engine.begin()

    # ========== Users ==========

    @staticmethod
    def create_user(username: str, email: str, hashed_password: str, full_name: Optional[str] = None, is_active: bool = True) -> Dict:
        """Create a new user."""
        with Database.get_connection() as conn:
            stmt = insert(users).values(
                username=username,
                email=email,
                hashed_password=hashed_password,
                full_name=full_name,
                is_active=is_active,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            result = conn.execute(stmt)
            conn.commit()
            user_id = result.inserted_primary_key[0]
            return Database.get_user_by_id(user_id)

    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[Dict]:
        """Get a user by ID."""
        with Database.get_connection() as conn:
            stmt = select(users).where(users.c.id == user_id)
            result = conn.execute(stmt).fetchone()
            return dict(result._mapping) if result else None

    @staticmethod
    def get_user_by_username(username: str) -> Optional[Dict]:
        """Get a user by username."""
        with Database.get_connection() as conn:
            stmt = select(users).where(users.c.username == username)
            result = conn.execute(stmt).fetchone()
            return dict(result._mapping) if result else None

    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict]:
        """Get a user by email."""
        with Database.get_connection() as conn:
            stmt = select(users).where(users.c.email == email)
            result = conn.execute(stmt).fetchone()
            return dict(result._mapping) if result else None

    @staticmethod
    def update_user(user_id: int, **kwargs) -> Optional[Dict]:
        """Update a user."""
        with Database.get_connection() as conn:
            kwargs['updated_at'] = datetime.now(timezone.utc)
            stmt = update(users).where(users.c.id == user_id).values(**kwargs)
            conn.execute(stmt)
            conn.commit()
            return Database.get_user_by_id(user_id)

    @staticmethod
    def delete_user(user_id: int) -> bool:
        """Delete a user."""
        with Database.get_connection() as conn:
            stmt = delete(users).where(users.c.id == user_id)
            result = conn.execute(stmt)
            conn.commit()
            return result.rowcount > 0

    # ========== Backtest Runs ==========

    @staticmethod
    def create_backtest_run(run_id: str, start_date: str, end_date: str, num_pairs: int, total_markets: int, user_id: Optional[int] = None, **kwargs) -> Dict:
        """Create a new backtest run."""
        with Database.get_connection() as conn:
            stmt = insert(backtest_runs).values(
                run_id=run_id,
                start_date=start_date,
                end_date=end_date,
                num_pairs=num_pairs,
                total_markets=total_markets,
                user_id=user_id,
                created_at=datetime.now(timezone.utc),
                **kwargs
            )
            result = conn.execute(stmt)
            conn.commit()
            run_pk = result.inserted_primary_key[0]
            return Database.get_backtest_run_by_id(run_pk)

    @staticmethod
    def get_backtest_run_by_id(run_id: int) -> Optional[Dict]:
        """Get a backtest run by primary key."""
        with Database.get_connection() as conn:
            stmt = select(backtest_runs).where(backtest_runs.c.id == run_id)
            result = conn.execute(stmt).fetchone()
            return dict(result._mapping) if result else None

    @staticmethod
    def get_backtest_run_by_run_id(run_id: str) -> Optional[Dict]:
        """Get a backtest run by run_id string."""
        with Database.get_connection() as conn:
            stmt = select(backtest_runs).where(backtest_runs.c.run_id == run_id)
            result = conn.execute(stmt).fetchone()
            return dict(result._mapping) if result else None

    @staticmethod
    def get_user_backtest_runs(user_id: int, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get all backtest runs for a user."""
        with Database.get_connection() as conn:
            stmt = select(backtest_runs).where(backtest_runs.c.user_id == user_id).limit(limit).offset(offset).order_by(backtest_runs.c.created_at.desc())
            results = conn.execute(stmt).fetchall()
            return [dict(row._mapping) for row in results]

    @staticmethod
    def update_backtest_run(run_id: int, **kwargs) -> Optional[Dict]:
        """Update a backtest run."""
        with Database.get_connection() as conn:
            if 'updated_at' not in kwargs:
                kwargs['updated_at'] = datetime.now(timezone.utc)
            stmt = update(backtest_runs).where(backtest_runs.c.id == run_id).values(**kwargs)
            conn.execute(stmt)
            conn.commit()
            return Database.get_backtest_run_by_id(run_id)

    # ========== Backtest Results ==========

    @staticmethod
    def create_backtest_result(run_id_fk: int, market_1: str, market_2: str, **kwargs) -> Dict:
        """Create a backtest result."""
        with Database.get_connection() as conn:
            stmt = insert(backtest_results).values(
                run_id_fk=run_id_fk,
                market_1=market_1,
                market_2=market_2,
                created_at=datetime.now(timezone.utc),
                **kwargs
            )
            result = conn.execute(stmt)
            conn.commit()
            result_id = result.inserted_primary_key[0]
            return Database.get_backtest_result_by_id(result_id)

    @staticmethod
    def get_backtest_result_by_id(result_id: int) -> Optional[Dict]:
        """Get a backtest result by ID."""
        with Database.get_connection() as conn:
            stmt = select(backtest_results).where(backtest_results.c.id == result_id)
            result = conn.execute(stmt).fetchone()
            return dict(result._mapping) if result else None

    @staticmethod
    def get_run_results(run_id: int, limit: int = 1000, offset: int = 0) -> List[Dict]:
        """Get all results for a backtest run."""
        with Database.get_connection() as conn:
            stmt = select(backtest_results).where(backtest_results.c.run_id_fk == run_id).limit(limit).offset(offset)
            results = conn.execute(stmt).fetchall()
            return [dict(row._mapping) for row in results]

    # ========== Backtest Trades ==========

    @staticmethod
    def create_backtest_trade(run_id_fk: int, trade_id: str, market_1: str, market_2: str, entry_timestamp: datetime, **kwargs) -> Dict:
        """Create a backtest trade."""
        with Database.get_connection() as conn:
            stmt = insert(backtest_trades).values(
                run_id_fk=run_id_fk,
                trade_id=trade_id,
                market_1=market_1,
                market_2=market_2,
                entry_timestamp=entry_timestamp,
                **kwargs
            )
            result = conn.execute(stmt)
            conn.commit()
            trade_pk = result.inserted_primary_key[0]
            return Database.get_backtest_trade_by_id(trade_pk)

    @staticmethod
    def get_backtest_trade_by_id(trade_id: int) -> Optional[Dict]:
        """Get a backtest trade by ID."""
        with Database.get_connection() as conn:
            stmt = select(backtest_trades).where(backtest_trades.c.id == trade_id)
            result = conn.execute(stmt).fetchone()
            return dict(result._mapping) if result else None

    @staticmethod
    def get_run_trades(run_id: int, limit: int = 10000) -> List[Dict]:
        """Get all trades for a backtest run."""
        with Database.get_connection() as conn:
            stmt = select(backtest_trades).where(backtest_trades.c.run_id_fk == run_id).limit(limit)
            results = conn.execute(stmt).fetchall()
            return [dict(row._mapping) for row in results]

    # ========== Backtest Candles ==========

    @staticmethod
    def create_backtest_candle(run_id_fk: int, market: str, timestamp: datetime, open_price: float, high_price: float, low_price: float, close_price: float, volume: float, **kwargs) -> Dict:
        """Create a backtest candle."""
        with Database.get_connection() as conn:
            stmt = insert(backtest_candles).values(
                run_id_fk=run_id_fk,
                market=market,
                timestamp=timestamp,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                volume=volume,
                created_at=datetime.now(timezone.utc),
                **kwargs
            )
            result = conn.execute(stmt)
            conn.commit()
            candle_id = result.inserted_primary_key[0]
            return Database.get_backtest_candle_by_id(candle_id)

    @staticmethod
    def get_backtest_candle_by_id(candle_id: int) -> Optional[Dict]:
        """Get a candle by ID."""
        with Database.get_connection() as conn:
            stmt = select(backtest_candles).where(backtest_candles.c.id == candle_id)
            result = conn.execute(stmt).fetchone()
            return dict(result._mapping) if result else None

    @staticmethod
    def get_candles_by_run_id(run_id: int) -> List[Dict]:
        """Get all candles for a run."""
        with Database.get_connection() as conn:
            stmt = select(backtest_candles).where(backtest_candles.c.run_id_fk == run_id).order_by(backtest_candles.c.timestamp)
            results = conn.execute(stmt).fetchall()
            return [dict(row._mapping) for row in results]

    @staticmethod
    def get_markets_by_run_id(run_id: int) -> List[str]:
        """Get unique markets for a run."""
        with Database.get_connection() as conn:
            stmt = select(backtest_candles.c.market.distinct()).where(backtest_candles.c.run_id_fk == run_id)
            results = conn.execute(stmt).fetchall()
            return [row[0] for row in results]

    # ========== Strategies ==========

    @staticmethod
    def create_strategy(name: str, user_id: int, **kwargs) -> Dict:
        """Create a backtest strategy."""
        with Database.get_connection() as conn:
            stmt = insert(backtest_strategies).values(
                name=name,
                user_id=user_id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                **kwargs
            )
            result = conn.execute(stmt)
            conn.commit()
            strategy_id = result.inserted_primary_key[0]
            return Database.get_strategy_by_id(strategy_id)

    @staticmethod
    def get_strategy_by_id(strategy_id: int) -> Optional[Dict]:
        """Get a strategy by ID."""
        with Database.get_connection() as conn:
            stmt = select(backtest_strategies).where(backtest_strategies.c.id == strategy_id)
            result = conn.execute(stmt).fetchone()
            return dict(result._mapping) if result else None

    @staticmethod
    def get_user_strategies(user_id: int) -> List[Dict]:
        """Get all strategies for a user."""
        with Database.get_connection() as conn:
            stmt = select(backtest_strategies).where(backtest_strategies.c.user_id == user_id).order_by(backtest_strategies.c.created_at.desc())
            results = conn.execute(stmt).fetchall()
            return [dict(row._mapping) for row in results]

    @staticmethod
    def update_strategy(strategy_id: int, **kwargs) -> Optional[Dict]:
        """Update a strategy."""
        with Database.get_connection() as conn:
            kwargs['updated_at'] = datetime.now(timezone.utc)
            stmt = update(backtest_strategies).where(backtest_strategies.c.id == strategy_id).values(**kwargs)
            conn.execute(stmt)
            conn.commit()
            return Database.get_strategy_by_id(strategy_id)

    # ========== Audit Logs ==========

    @staticmethod
    def create_audit_log(action: str, resource_type: str, user_id: Optional[int] = None, resource_id: Optional[str] = None, details: Optional[Dict] = None, status: str = "success", ip_address: Optional[str] = None) -> Dict:
        """Create an audit log entry."""
        with Database.get_connection() as conn:
            stmt = insert(audit_logs).values(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                status=status,
                ip_address=ip_address,
                created_at=datetime.now(timezone.utc),
            )
            result = conn.execute(stmt)
            conn.commit()
            log_id = result.inserted_primary_key[0]
            return Database.get_audit_log_by_id(log_id)

    @staticmethod
    def get_audit_log_by_id(log_id: int) -> Optional[Dict]:
        """Get an audit log by ID."""
        with Database.get_connection() as conn:
            stmt = select(audit_logs).where(audit_logs.c.id == log_id)
            result = conn.execute(stmt).fetchone()
            return dict(result._mapping) if result else None

    @staticmethod
    def get_user_audit_logs(user_id: int, limit: int = 100) -> List[Dict]:
        """Get audit logs for a user."""
        with Database.get_connection() as conn:
            stmt = select(audit_logs).where(audit_logs.c.user_id == user_id).order_by(audit_logs.c.created_at.desc()).limit(limit)
            results = conn.execute(stmt).fetchall()
            return [dict(row._mapping) for row in results]

    # ========== DYdX Keys ==========

    @staticmethod
    def create_dydx_key(user_id: int, network: str, chain_address: str, encrypted_secret: str, is_active: bool = True, **kwargs) -> Dict:
        """Create a DYdX key for a user."""
        with Database.get_connection() as conn:
            stmt = insert(dydx_keys).values(
                user_id=user_id,
                network=network,
                chain_address=chain_address,
                encrypted_secret=encrypted_secret,
                is_active=is_active,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                **kwargs
            )
            result = conn.execute(stmt)
            conn.commit()
            key_id = result.inserted_primary_key[0]
            return Database.get_dydx_key_by_id(key_id)

    @staticmethod
    def get_dydx_key_by_id(key_id: int) -> Optional[Dict]:
        """Get a DYdX key by ID."""
        with Database.get_connection() as conn:
            stmt = select(dydx_keys).where(dydx_keys.c.id == key_id)
            result = conn.execute(stmt).fetchone()
            return dict(result._mapping) if result else None

    @staticmethod
    def get_dydx_keys_by_user(user_id: int) -> List[Dict]:
        """Get all DYdX keys for a user."""
        with Database.get_connection() as conn:
            stmt = select(dydx_keys).where(dydx_keys.c.user_id == user_id).order_by(dydx_keys.c.created_at.desc())
            results = conn.execute(stmt).fetchall()
            return [dict(row._mapping) for row in results]

    @staticmethod
    def get_dydx_key_by_network(user_id: int, network: str) -> Optional[Dict]:
        """Get a DYdX key by user and network."""
        with Database.get_connection() as conn:
            stmt = select(dydx_keys).where((dydx_keys.c.user_id == user_id) & (dydx_keys.c.network == network))
            result = conn.execute(stmt).fetchone()
            return dict(result._mapping) if result else None

    @staticmethod
    def update_dydx_key(key_id: int, **kwargs) -> Optional[Dict]:
        """Update a DYdX key."""
        with Database.get_connection() as conn:
            kwargs['updated_at'] = datetime.now(timezone.utc)
            stmt = update(dydx_keys).where(dydx_keys.c.id == key_id).values(**kwargs)
            conn.execute(stmt)
            conn.commit()
            return Database.get_dydx_key_by_id(key_id)

    @staticmethod
    def delete_dydx_key(key_id: int) -> bool:
        """Delete a DYdX key."""
        with Database.get_connection() as conn:
            stmt = delete(dydx_keys).where(dydx_keys.c.id == key_id)
            result = conn.execute(stmt)
            conn.commit()
            return result.rowcount > 0

    # ========== DYdX Key Settings ==========

    @staticmethod
    def create_dydx_key_settings(user_id: int, default_network: Optional[str] = None, auto_switch_testnet: bool = True, **kwargs) -> Dict:
        """Create DYdX key settings for a user."""
        with Database.get_connection() as conn:
            stmt = insert(dydx_key_settings).values(
                user_id=user_id,
                default_network=default_network,
                auto_switch_testnet=auto_switch_testnet,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                **kwargs
            )
            result = conn.execute(stmt)
            conn.commit()
            settings_id = result.inserted_primary_key[0]
            return Database.get_dydx_key_settings_by_id(settings_id)

    @staticmethod
    def get_dydx_key_settings_by_id(settings_id: int) -> Optional[Dict]:
        """Get DYdX key settings by ID."""
        with Database.get_connection() as conn:
            stmt = select(dydx_key_settings).where(dydx_key_settings.c.id == settings_id)
            result = conn.execute(stmt).fetchone()
            return dict(result._mapping) if result else None

    @staticmethod
    def get_dydx_key_settings_by_user(user_id: int) -> Optional[Dict]:
        """Get DYdX key settings for a user."""
        with Database.get_connection() as conn:
            stmt = select(dydx_key_settings).where(dydx_key_settings.c.user_id == user_id)
            result = conn.execute(stmt).fetchone()
            return dict(result._mapping) if result else None

    @staticmethod
    def update_dydx_key_settings(settings_id: int, **kwargs) -> Optional[Dict]:
        """Update DYdX key settings."""
        with Database.get_connection() as conn:
            kwargs['updated_at'] = datetime.now(timezone.utc)
            stmt = update(dydx_key_settings).where(dydx_key_settings.c.id == settings_id).values(**kwargs)
            conn.execute(stmt)
            conn.commit()
            return Database.get_dydx_key_settings_by_id(settings_id)

    @staticmethod
    def delete_dydx_key_settings(settings_id: int) -> bool:
        """Delete DYdX key settings."""
        with Database.get_connection() as conn:
            stmt = delete(dydx_key_settings).where(dydx_key_settings.c.id == settings_id)
            result = conn.execute(stmt)
            conn.commit()
            return result.rowcount > 0

    # ========== Raw SQL ==========

    @staticmethod
    def execute_raw(query: str, params: Optional[Dict] = None):
        """Execute a raw SQL query."""
        with Database.get_connection() as conn:
            stmt = text(query)
            result = conn.execute(stmt, params or {})
            conn.commit()
            return result

    @staticmethod
    def execute_raw_select(query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute a raw SQL SELECT query and return results."""
        with Database.get_connection() as conn:
            stmt = text(query)
            results = conn.execute(stmt, params or {}).fetchall()
            return [dict(row._mapping) for row in results]
