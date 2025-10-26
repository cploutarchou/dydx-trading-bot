"""
SQLModel Database Service Layer
Provides session management and CRUD operations with Pydantic validation.
Uses database configuration from config folder.
"""

from sqlalchemy.orm import Session
from models import (
    User, DYDXKey, DYDXKeySettings, BacktestStrategy, BacktestRun, 
    BacktestResult, BacktestTrade, BacktestCandle, AuditLog, 
    RedisSettings, BotSetting, BacktestLog, BacktestPosition,
    BacktestComparison, TradeLog, StrategyExecutionState
)
import db_init
from typing import Optional, List, Type, TypeVar


# Generic CRUD operations
T = TypeVar('T')


class DatabaseService:
    """SQLModel-based database service with Pydantic validation."""

    @staticmethod
    def create(session: Session, db_model: Type[T], data: dict) -> T:
        """Create a new record with validation."""
        db_obj = db_model(**data)
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    @staticmethod
    def get(session: Session, db_model: Type[T], **filters) -> Optional[T]:
        """Get a single record by filters."""
        query = session.query(db_model)
        for key, value in filters.items():
            query = query.filter(getattr(db_model, key) == value)
        return query.first()

    @staticmethod
    def get_all(session: Session, db_model: Type[T], skip: int = 0, limit: int = 100, **filters) -> List[T]:
        """Get multiple records with pagination."""
        query = session.query(db_model)
        for key, value in filters.items():
            query = query.filter(getattr(db_model, key) == value)
        return query.offset(skip).limit(limit).all()

    @staticmethod
    def update(session: Session, db_model: Type[T], db_id: int, data: dict) -> Optional[T]:
        """Update a record."""
        db_obj = session.query(db_model).filter(db_model.id == db_id).first()
        if not db_obj:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(db_obj, key, value)
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    @staticmethod
    def delete(session: Session, db_model: Type[T], db_id: int) -> bool:
        """Delete a record."""
        db_obj = session.query(db_model).filter(db_model.id == db_id).first()
        if not db_obj:
            return False
        session.delete(db_obj)
        session.commit()
        return True


# Convenience functions for common operations

def create_user(session: Session, user_data: dict) -> User:
    """Create a user."""
    return DatabaseService.create(session, User, user_data)


def get_user(session: Session, **filters) -> Optional[User]:
    """Get a user."""
    return DatabaseService.get(session, User, **filters)


def get_users(session: Session, skip: int = 0, limit: int = 100) -> List[User]:
    """Get all users with pagination."""
    return DatabaseService.get_all(session, User, skip=skip, limit=limit)


def update_user(session: Session, user_id: int, user_data: dict) -> Optional[User]:
    """Update a user."""
    return DatabaseService.update(session, User, user_id, user_data)


def delete_user(session: Session, user_id: int) -> bool:
    """Delete a user."""
    return DatabaseService.delete(session, User, user_id)


def create_dydx_key(session: Session, key_data: dict) -> DYDXKey:
    """Create a DYdX key."""
    return DatabaseService.create(session, DYDXKey, key_data)


def get_dydx_keys_by_user(session: Session, user_id: int) -> List[DYDXKey]:
    """Get all DYdX keys for a user."""
    return session.query(DYDXKey).filter(DYDXKey.user_id == user_id).all()


def get_dydx_key_by_network(session: Session, user_id: int, network: str) -> Optional[DYDXKey]:
    """Get a DYdX key by user and network."""
    return session.query(DYDXKey).filter(
        DYDXKey.user_id == user_id, 
        DYDXKey.network == network
    ).first()


def create_dydx_key_settings(session: Session, settings_data: dict) -> DYDXKeySettings:
    """Create DYdX key settings."""
    return DatabaseService.create(session, DYDXKeySettings, settings_data)


def get_dydx_key_settings(session: Session, user_id: int) -> Optional[DYDXKeySettings]:
    """Get DYdX key settings for a user."""
    return session.query(DYDXKeySettings).filter(DYDXKeySettings.user_id == user_id).first()


def create_backtest_run(session: Session, run_data: dict) -> BacktestRun:
    """Create a backtest run."""
    return DatabaseService.create(session, BacktestRun, run_data)


def get_backtest_run(session: Session, **filters) -> Optional[BacktestRun]:
    """Get a backtest run."""
    return DatabaseService.get(session, BacktestRun, **filters)


def get_backtest_runs_by_user(session: Session, user_id: int) -> List[BacktestRun]:
    """Get all backtest runs for a user."""
    return session.query(BacktestRun).filter(BacktestRun.user_id == user_id).order_by(BacktestRun.created_at.desc()).all()


def create_backtest_result(session: Session, result_data: dict) -> BacktestResult:
    """Create a backtest result."""
    return DatabaseService.create(session, BacktestResult, result_data)


def get_backtest_results_by_run(session: Session, run_id: int) -> List[BacktestResult]:
    """Get all results for a backtest run."""
    return session.query(BacktestResult).filter(BacktestResult.run_id_fk == run_id).all()


def create_backtest_candle(session: Session, candle_data: dict) -> BacktestCandle:
    """Create a backtest candle."""
    return DatabaseService.create(session, BacktestCandle, candle_data)


def get_candles_by_run_id(session: Session, run_id: int) -> List[BacktestCandle]:
    """Get all candles for a run. ⭐"""
    return session.query(BacktestCandle).filter(
        BacktestCandle.run_id_fk == run_id
    ).order_by(BacktestCandle.timestamp).all()


def get_markets_by_run_id(session: Session, run_id: int) -> List[str]:
    """Get unique markets for a run. ⭐"""
    markets = session.query(BacktestCandle.market.distinct()).filter(
        BacktestCandle.run_id_fk == run_id
    ).all()
    return [market[0] for market in markets]


def create_backtest_trade(session: Session, trade_data: dict) -> BacktestTrade:
    """Create a backtest trade."""
    return DatabaseService.create(session, BacktestTrade, trade_data)


def get_backtest_trades_by_run(session: Session, run_id: int) -> List[BacktestTrade]:
    """Get all trades for a run."""
    return session.query(BacktestTrade).filter(BacktestTrade.run_id_fk == run_id).all()


def create_backtest_strategy(session: Session, strategy_data: dict) -> BacktestStrategy:
    """Create a backtest strategy."""
    return DatabaseService.create(session, BacktestStrategy, strategy_data)


def get_backtest_strategy(session: Session, **filters) -> Optional[BacktestStrategy]:
    """Get a backtest strategy."""
    return DatabaseService.get(session, BacktestStrategy, **filters)


def get_user_strategies(session: Session, user_id: int) -> List[BacktestStrategy]:
    """Get all strategies for a user."""
    return session.query(BacktestStrategy).filter(BacktestStrategy.user_id == user_id).all()


def create_audit_log(session: Session, log_data: dict) -> AuditLog:
    """Create an audit log."""
    return DatabaseService.create(session, AuditLog, log_data)


def get_audit_logs_by_user(session: Session, user_id: int, limit: int = 100) -> List[AuditLog]:
    """Get audit logs for a user."""
    return session.query(AuditLog).filter(AuditLog.user_id == user_id).order_by(AuditLog.created_at.desc()).limit(limit).all()


def create_backtest_log(session: Session, log_data: dict) -> BacktestLog:
    """Create a backtest log."""
    return DatabaseService.create(session, BacktestLog, log_data)


def get_backtest_logs_by_run(session: Session, run_id: int) -> List[BacktestLog]:
    """Get all logs for a backtest run."""
    return session.query(BacktestLog).filter(BacktestLog.run_id_fk == run_id).order_by(BacktestLog.created_at).all()


def create_backtest_position(session: Session, position_data: dict) -> BacktestPosition:
    """Create a backtest position."""
    return DatabaseService.create(session, BacktestPosition, position_data)


def get_backtest_positions_by_run(session: Session, run_id: int) -> List[BacktestPosition]:
    """Get all positions for a backtest run."""
    return session.query(BacktestPosition).filter(BacktestPosition.run_id_fk == run_id).all()


def get_backtest_positions_by_status(session: Session, run_id: int, status: str) -> List[BacktestPosition]:
    """Get positions by status for a run."""
    return session.query(BacktestPosition).filter(
        BacktestPosition.run_id_fk == run_id,
        BacktestPosition.status == status
    ).all()


def create_backtest_comparison(session: Session, comparison_data: dict) -> BacktestComparison:
    """Create a backtest comparison."""
    return DatabaseService.create(session, BacktestComparison, comparison_data)


def get_backtest_comparisons_by_user(session: Session, user_id: int) -> List[BacktestComparison]:
    """Get all backtest comparisons for a user."""
    return session.query(BacktestComparison).filter(BacktestComparison.user_id == user_id).all()


def get_backtest_comparison(session: Session, comparison_id: int) -> Optional[BacktestComparison]:
    """Get a backtest comparison by ID."""
    return session.query(BacktestComparison).filter(BacktestComparison.id == comparison_id).first()


def create_trade_log(session: Session, trade_log_data: dict) -> TradeLog:
    """Create a trade log."""
    return DatabaseService.create(session, TradeLog, trade_log_data)


def get_trade_logs_by_result(session: Session, result_id: int) -> List[TradeLog]:
    """Get all trade logs for a backtest result."""
    return session.query(TradeLog).filter(TradeLog.result_id_fk == result_id).order_by(TradeLog.entry_timestamp).all()


def create_strategy_execution_state(session: Session, state_data: dict) -> StrategyExecutionState:
    """Create a strategy execution state."""
    return DatabaseService.create(session, StrategyExecutionState, state_data)


def get_strategy_execution_state(session: Session, strategy_id: int) -> Optional[StrategyExecutionState]:
    """Get strategy execution state by strategy ID."""
    return session.query(StrategyExecutionState).filter(StrategyExecutionState.strategy_id == strategy_id).first()


def update_strategy_execution_state(session: Session, strategy_id: int, state_data: dict) -> Optional[StrategyExecutionState]:
    """Update strategy execution state."""
    state = session.query(StrategyExecutionState).filter(StrategyExecutionState.strategy_id == strategy_id).first()
    if not state:
        state_data['strategy_id'] = strategy_id
        return create_strategy_execution_state(session, state_data)
    for key, value in state_data.items():
        if value is not None:
            setattr(state, key, value)
    session.add(state)
    session.commit()
    session.refresh(state)
    return state


# Re-export from db_init for convenience
DatabaseSession = db_init.DatabaseSession
get_session = db_init.get_session
init_db = db_init.init_db
close_db = db_init.close_db
get_database_config = db_init.get_database_config
