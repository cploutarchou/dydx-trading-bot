"""
Repository/CRUD service layer for database operations.
Provides high-level interface for all model operations.
Uses the Database module for connection management.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from database import Database, CRUDBase
from models.sqlmodel_models import (
    User, DYDXKey, DYDXKeySettings,
    BacktestStrategy, BacktestRun, BacktestResult,
    BacktestTrade, BacktestCandle, BacktestLog,
    BacktestPosition, BacktestComparison,
    TradeLog, AuditLog,
    BotSetting, RedisSettings,
    StrategyVersionHistory, StrategyExecutionState
)


# ========== User Repository ==========

class UserRepository(CRUDBase):
    """User account management."""
    
    @staticmethod
    def get_by_username(session: Session, username: str) -> Optional[User]:
        """Get user by username."""
        return session.query(User).filter(User.username == username).first()
    
    @staticmethod
    def get_by_email(session: Session, email: str) -> Optional[User]:
        """Get user by email."""
        return session.query(User).filter(User.email == email).first()
    
    @staticmethod
    def get_active_users(session: Session) -> List[User]:
        """Get all active users."""
        return session.query(User).filter(User.is_active == True).all()
    
    @staticmethod
    def get_admin_users(session: Session) -> List[User]:
        """Get all admin users."""
        return session.query(User).filter(User.is_admin == True).all()


# ========== DYDXKey Repository ==========

class DYDXKeyRepository(CRUDBase):
    """dYdX API key management."""
    
    @staticmethod
    def get_by_user(session: Session, user_id: int) -> List[DYDXKey]:
        """Get all keys for a user."""
        return session.query(DYDXKey).filter(DYDXKey.user_id == user_id).all()
    
    @staticmethod
    def get_by_network(session: Session, user_id: int, network: str) -> Optional[DYDXKey]:
        """Get key for user and network."""
        return session.query(DYDXKey).filter(
            DYDXKey.user_id == user_id,
            DYDXKey.network == network
        ).first()
    
    @staticmethod
    def get_active_keys(session: Session, user_id: int) -> List[DYDXKey]:
        """Get active keys for user."""
        return session.query(DYDXKey).filter(
            DYDXKey.user_id == user_id,
            DYDXKey.is_active == True
        ).all()


# ========== DYDXKeySettings Repository ==========

class DYDXKeySettingsRepository(CRUDBase):
    """dYdX key settings management."""
    
    @staticmethod
    def get_by_user(session: Session, user_id: int) -> Optional[DYDXKeySettings]:
        """Get settings for a user."""
        return session.query(DYDXKeySettings).filter(
            DYDXKeySettings.user_id == user_id
        ).first()
    
    @staticmethod
    def get_or_create(session: Session, user_id: int) -> DYDXKeySettings:
        """Get settings or create default."""
        settings = DYDXKeySettingsRepository.get_by_user(session, user_id)
        if not settings:
            settings = CRUDBase.create(
                session, DYDXKeySettings,
                user_id=user_id,
                default_network="testnet",
                auto_switch_testnet=True
            )
        return settings


# ========== BacktestStrategy Repository ==========

class BacktestStrategyRepository(CRUDBase):
    """Trading strategy management."""
    
    @staticmethod
    def get_by_user(session: Session, user_id: int) -> List[BacktestStrategy]:
        """Get all strategies for a user."""
        return session.query(BacktestStrategy).filter(
            BacktestStrategy.user_id == user_id,
            BacktestStrategy.deleted_at == None
        ).all()
    
    @staticmethod
    def get_public_strategies(session: Session) -> List[BacktestStrategy]:
        """Get all public strategies."""
        return session.query(BacktestStrategy).filter(
            BacktestStrategy.is_public == True,
            BacktestStrategy.deleted_at == None
        ).all()
    
    @staticmethod
    def get_default_strategy(session: Session) -> Optional[BacktestStrategy]:
        """Get default strategy."""
        return session.query(BacktestStrategy).filter(
            BacktestStrategy.is_default == True,
            BacktestStrategy.deleted_at == None
        ).first()
    
    @staticmethod
    def soft_delete(session: Session, strategy_id: int) -> Optional[BacktestStrategy]:
        """Soft delete a strategy."""
        strategy = CRUDBase.get_by_id(session, BacktestStrategy, strategy_id)
        if strategy:
            strategy.deleted_at = datetime.now(timezone.utc)
            session.flush()
        return strategy


# ========== BacktestRun Repository ==========

class BacktestRunRepository(CRUDBase):
    """Backtest run management."""
    
    @staticmethod
    def get_by_run_id(session: Session, run_id: str) -> Optional[BacktestRun]:
        """Get backtest run by run_id."""
        return session.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
    
    @staticmethod
    def get_by_user(session: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[BacktestRun]:
        """Get backtest runs for a user with pagination."""
        return session.query(BacktestRun).filter(
            BacktestRun.user_id == user_id
        ).order_by(BacktestRun.created_at.desc()).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_by_strategy(session: Session, strategy_id: int) -> List[BacktestRun]:
        """Get all runs for a strategy."""
        return session.query(BacktestRun).filter(
            BacktestRun.strategy_id == strategy_id
        ).order_by(BacktestRun.created_at.desc()).all()
    
    @staticmethod
    def get_by_status(session: Session, status: str) -> List[BacktestRun]:
        """Get all runs with specific status."""
        return session.query(BacktestRun).filter(BacktestRun.status == status).all()
    
    @staticmethod
    def count_by_user(session: Session, user_id: int) -> int:
        """Count total runs for a user."""
        return session.query(BacktestRun).filter(BacktestRun.user_id == user_id).count()


# ========== BacktestResult Repository ==========

class BacktestResultRepository(CRUDBase):
    """Backtest result management."""
    
    @staticmethod
    def get_by_run(session: Session, run_id: int) -> List[BacktestResult]:
        """Get all results for a backtest run."""
        return session.query(BacktestResult).filter(
            BacktestResult.run_id_fk == run_id
        ).all()
    
    @staticmethod
    def get_by_market_pair(
        session: Session,
        run_id: int,
        market_1: str,
        market_2: str
    ) -> Optional[BacktestResult]:
        """Get result for specific market pair in a run."""
        return session.query(BacktestResult).filter(
            BacktestResult.run_id_fk == run_id,
            BacktestResult.market_1 == market_1,
            BacktestResult.market_2 == market_2
        ).first()
    
    @staticmethod
    def get_best_results(session: Session, run_id: int, limit: int = 10) -> List[BacktestResult]:
        """Get best results sorted by PnL."""
        return session.query(BacktestResult).filter(
            BacktestResult.run_id_fk == run_id
        ).order_by(BacktestResult.pnl.desc()).limit(limit).all()


# ========== BacktestCandle Repository ==========

class BacktestCandleRepository(CRUDBase):
    """Backtest candle data management."""
    
    @staticmethod
    def get_by_run(session: Session, run_id: int) -> List[BacktestCandle]:
        """Get all candles for a run."""
        return session.query(BacktestCandle).filter(
            BacktestCandle.run_id_fk == run_id
        ).order_by(BacktestCandle.timestamp.asc()).all()
    
    @staticmethod
    def get_by_market(session: Session, run_id: int, market: str) -> List[BacktestCandle]:
        """Get all candles for a market in a run."""
        return session.query(BacktestCandle).filter(
            BacktestCandle.run_id_fk == run_id,
            BacktestCandle.market == market
        ).order_by(BacktestCandle.timestamp.asc()).all()
    
    @staticmethod
    def get_markets_in_run(session: Session, run_id: int) -> List[str]:
        """Get unique markets in a run."""
        markets = session.query(BacktestCandle.market.distinct()).filter(
            BacktestCandle.run_id_fk == run_id
        ).all()
        return [m[0] for m in markets]


# ========== BacktestTrade Repository ==========

class BacktestTradeRepository(CRUDBase):
    """Backtest trade management."""
    
    @staticmethod
    def get_by_run(session: Session, run_id: int) -> List[BacktestTrade]:
        """Get all trades for a run."""
        return session.query(BacktestTrade).filter(
            BacktestTrade.run_id_fk == run_id
        ).order_by(BacktestTrade.entry_timestamp.asc()).all()
    
    @staticmethod
    def get_by_market_pair(
        session: Session,
        run_id: int,
        market_1: str,
        market_2: str
    ) -> List[BacktestTrade]:
        """Get trades for a market pair."""
        return session.query(BacktestTrade).filter(
            BacktestTrade.run_id_fk == run_id,
            BacktestTrade.market_1 == market_1,
            BacktestTrade.market_2 == market_2
        ).all()


# ========== BacktestLog Repository ==========

class BacktestLogRepository(CRUDBase):
    """Backtest log management."""
    
    @staticmethod
    def get_by_run(session: Session, run_id: int) -> List[BacktestLog]:
        """Get all logs for a run."""
        return session.query(BacktestLog).filter(
            BacktestLog.run_id_fk == run_id
        ).order_by(BacktestLog.created_at.asc()).all()
    
    @staticmethod
    def get_errors_in_run(session: Session, run_id: int) -> List[BacktestLog]:
        """Get error logs for a run."""
        return session.query(BacktestLog).filter(
            BacktestLog.run_id_fk == run_id,
            BacktestLog.level == "ERROR"
        ).all()


# ========== BacktestPosition Repository ==========

class BacktestPositionRepository(CRUDBase):
    """Backtest position management."""
    
    @staticmethod
    def get_by_run(session: Session, run_id: int) -> List[BacktestPosition]:
        """Get all positions for a run."""
        return session.query(BacktestPosition).filter(
            BacktestPosition.run_id_fk == run_id
        ).all()
    
    @staticmethod
    def get_open_positions(session: Session, run_id: int) -> List[BacktestPosition]:
        """Get open positions in a run."""
        return session.query(BacktestPosition).filter(
            BacktestPosition.run_id_fk == run_id,
            BacktestPosition.status == "open"
        ).all()
    
    @staticmethod
    def get_closed_positions(session: Session, run_id: int) -> List[BacktestPosition]:
        """Get closed positions in a run."""
        return session.query(BacktestPosition).filter(
            BacktestPosition.run_id_fk == run_id,
            BacktestPosition.status == "closed"
        ).all()


# ========== BacktestComparison Repository ==========

class BacktestComparisonRepository(CRUDBase):
    """Backtest comparison management."""
    
    @staticmethod
    def get_by_user(session: Session, user_id: int) -> List[BacktestComparison]:
        """Get all comparisons for a user."""
        return session.query(BacktestComparison).filter(
            BacktestComparison.user_id == user_id
        ).order_by(BacktestComparison.created_at.desc()).all()
    
    @staticmethod
    def get_by_name(session: Session, user_id: int, name: str) -> Optional[BacktestComparison]:
        """Get comparison by name for a user."""
        return session.query(BacktestComparison).filter(
            BacktestComparison.user_id == user_id,
            BacktestComparison.name == name
        ).first()


# ========== TradeLog Repository ==========

class TradeLogRepository(CRUDBase):
    """Trade log management."""
    
    @staticmethod
    def get_by_result(session: Session, result_id: int) -> List[TradeLog]:
        """Get all trades for a result."""
        return session.query(TradeLog).filter(
            TradeLog.result_id_fk == result_id
        ).order_by(TradeLog.entry_timestamp.asc()).all()


# ========== AuditLog Repository ==========

class AuditLogRepository(CRUDBase):
    """Audit log management."""
    
    @staticmethod
    def get_by_user(session: Session, user_id: int, limit: int = 100) -> List[AuditLog]:
        """Get audit logs for a user."""
        return session.query(AuditLog).filter(
            AuditLog.user_id == user_id
        ).order_by(AuditLog.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def get_by_resource(
        session: Session,
        resource_type: str,
        resource_id: str
    ) -> List[AuditLog]:
        """Get audit logs for a resource."""
        return session.query(AuditLog).filter(
            AuditLog.resource_type == resource_type,
            AuditLog.resource_id == resource_id
        ).order_by(AuditLog.created_at.desc()).all()
    
    @staticmethod
    def log_action(
        session: Session,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: str,
        details: Optional[dict] = None,
        status: str = "success",
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """Create an audit log entry."""
        return CRUDBase.create(
            session, AuditLog,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            status=status,
            ip_address=ip_address
        )


# ========== BotSetting Repository ==========

class BotSettingRepository(CRUDBase):
    """Bot settings management."""
    
    @staticmethod
    def get_by_key(session: Session, section: str, key: str) -> Optional[BotSetting]:
        """Get setting by section and key."""
        return session.query(BotSetting).filter(
            BotSetting.section == section,
            BotSetting.key == key
        ).first()
    
    @staticmethod
    def get_section(session: Session, section: str) -> List[BotSetting]:
        """Get all settings in a section."""
        return session.query(BotSetting).filter(
            BotSetting.section == section,
            BotSetting.is_active == True
        ).all()
    
    @staticmethod
    def set_value(
        session: Session,
        section: str,
        key: str,
        value: str,
        value_type: str = "string",
        updated_by_user_id: Optional[int] = None
    ) -> BotSetting:
        """Set a setting value (create or update)."""
        setting = BotSettingRepository.get_by_key(session, section, key)
        if setting:
            setting.value = value
            setting.updated_by = updated_by_user_id
            session.flush()
            return setting
        else:
            return CRUDBase.create(
                session, BotSetting,
                section=section,
                key=key,
                value=value,
                value_type=value_type,
                updated_by=updated_by_user_id
            )


# ========== RedisSettings Repository ==========

class RedisSettingsRepository(CRUDBase):
    """Redis settings management."""
    
    @staticmethod
    def get_active_settings(session: Session) -> Optional[RedisSettings]:
        """Get active Redis settings."""
        return session.query(RedisSettings).filter(
            RedisSettings.enabled == True
        ).first()


# ========== StrategyVersionHistory Repository ==========

class StrategyVersionHistoryRepository(CRUDBase):
    """Strategy version history management."""
    
    @staticmethod
    def get_by_strategy(session: Session, strategy_id: int) -> List[StrategyVersionHistory]:
        """Get all versions of a strategy."""
        return session.query(StrategyVersionHistory).filter(
            StrategyVersionHistory.strategy_id == strategy_id
        ).order_by(StrategyVersionHistory.version_number.desc()).all()
    
    @staticmethod
    def get_latest_version(session: Session, strategy_id: int) -> Optional[StrategyVersionHistory]:
        """Get latest version of a strategy."""
        return session.query(StrategyVersionHistory).filter(
            StrategyVersionHistory.strategy_id == strategy_id
        ).order_by(StrategyVersionHistory.version_number.desc()).first()


# ========== StrategyExecutionState Repository ==========

class StrategyExecutionStateRepository(CRUDBase):
    """Strategy execution state management."""
    
    @staticmethod
    def get_by_strategy(session: Session, strategy_id: int) -> Optional[StrategyExecutionState]:
        """Get execution state for a strategy."""
        return session.query(StrategyExecutionState).filter(
            StrategyExecutionState.strategy_id == strategy_id
        ).first()
    
    @staticmethod
    def get_enabled_strategies(session: Session) -> List[StrategyExecutionState]:
        """Get all enabled strategies."""
        return session.query(StrategyExecutionState).filter(
            StrategyExecutionState.enabled == True
        ).all()


# ========== Repository Registry ==========

class RepositoryRegistry:
    """Registry of all repositories for easy access."""
    
    users = UserRepository
    dydx_keys = DYDXKeyRepository
    dydx_key_settings = DYDXKeySettingsRepository
    backtest_strategies = BacktestStrategyRepository
    backtest_runs = BacktestRunRepository
    backtest_results = BacktestResultRepository
    backtest_candles = BacktestCandleRepository
    backtest_trades = BacktestTradeRepository
    backtest_logs = BacktestLogRepository
    backtest_positions = BacktestPositionRepository
    backtest_comparisons = BacktestComparisonRepository
    trade_logs = TradeLogRepository
    audit_logs = AuditLogRepository
    bot_settings = BotSettingRepository
    redis_settings = RedisSettingsRepository
    strategy_version_history = StrategyVersionHistoryRepository
    strategy_execution_state = StrategyExecutionStateRepository


__all__ = [
    "UserRepository",
    "DYDXKeyRepository",
    "DYDXKeySettingsRepository",
    "BacktestStrategyRepository",
    "BacktestRunRepository",
    "BacktestResultRepository",
    "BacktestCandleRepository",
    "BacktestTradeRepository",
    "BacktestLogRepository",
    "BacktestPositionRepository",
    "BacktestComparisonRepository",
    "TradeLogRepository",
    "AuditLogRepository",
    "BotSettingRepository",
    "RedisSettingsRepository",
    "StrategyVersionHistoryRepository",
    "StrategyExecutionStateRepository",
    "RepositoryRegistry",
]
