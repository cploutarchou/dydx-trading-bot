"""
Database service layer for backtest operations.
Handles CRUD operations and complex queries.
"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from backend.auth import hash_password, verify_password
from backend.database import AuditLog, BacktestResult, BacktestRun, TradeLog, User

logger = logging.getLogger(__name__)


class UserService:
    """Service for user management."""

    @staticmethod
    def create_user(
        db: Session, username: str, email: str, password: str
    ) -> User:
        """Create new user account."""
        # Check if user already exists
        existing = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing:
            raise ValueError(f"User {username} already exists")

        hashed_pwd = hash_password(password)
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_pwd,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"User created: {username}")
        return user

    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        """Get user by username."""
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def authenticate_user(
        db: Session, username: str, password: str
    ) -> Optional[User]:
        """Authenticate user with credentials."""
        user = UserService.get_user_by_username(db, username)
        if not user or not verify_password(password, user.hashed_password):
            return None

        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        return user

    @staticmethod
    def deactivate_user(db: Session, user_id: int) -> bool:
        """Deactivate user account."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        user.is_active = False
        db.commit()
        logger.info(f"User deactivated: {user.username}")
        return True


class BacktestRunService:
    """Service for backtest run management."""

    @staticmethod
    def create_run(
        db: Session,
        run_id: str,
        start_date: str,
        end_date: str,
        num_pairs: int,
        total_markets: int,
        user_id: Optional[int] = None,
        config: Optional[dict] = None
    ) -> BacktestRun:
        """Create new backtest run."""
        run = BacktestRun(
            run_id=run_id,
            status="running",
            start_date=start_date,
            end_date=end_date,
            num_pairs=num_pairs,
            total_markets=total_markets,
            user_id=user_id,
            config=config,
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow()
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        logger.info(f"Backtest run created: {run_id}")
        return run

    @staticmethod
    def get_run_by_id(db: Session, run_id_pk: int) -> Optional[BacktestRun]:
        """Get backtest run by ID."""
        return db.query(BacktestRun).filter(
            BacktestRun.id == run_id_pk
        ).first()

    @staticmethod
    def get_run_by_run_id(db: Session, run_id: str) -> Optional[BacktestRun]:
        """Get backtest run by run_id string."""
        return db.query(BacktestRun).filter(
            BacktestRun.run_id == run_id
        ).first()

    @staticmethod
    def get_user_runs(
        db: Session, user_id: int, skip: int = 0, limit: int = 50
    ) -> List[BacktestRun]:
        """Get all backtest runs for a user."""
        return db.query(BacktestRun).filter(
            BacktestRun.user_id == user_id
        ).order_by(
            desc(BacktestRun.created_at)
        ).offset(skip).limit(limit).all()

    @staticmethod
    def update_run_status(
        db: Session, run_id_pk: int, status: str
    ) -> Optional[BacktestRun]:
        """Update backtest run status."""
        run = db.query(BacktestRun).filter(
            BacktestRun.id == run_id_pk
        ).first()
        if not run:
            return None

        run.status = status
        if status == "completed":
            run.completed_at = datetime.utcnow()
            if run.started_at:
                duration = (run.completed_at - run.started_at).total_seconds()
                run.duration_seconds = duration

        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def update_run_metrics(
        db: Session, run_id_pk: int, metrics: dict
    ) -> Optional[BacktestRun]:
        """Update backtest run with metrics."""
        run = db.query(BacktestRun).filter(
            BacktestRun.id == run_id_pk
        ).first()
        if not run:
            return None

        # Update metrics from dict
        for key, value in metrics.items():
            if hasattr(run, key):
                setattr(run, key, value)

        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def get_latest_runs(db: Session, limit: int = 10) -> List[BacktestRun]:
        """Get latest backtest runs."""
        return db.query(BacktestRun).order_by(
            desc(BacktestRun.created_at)
        ).limit(limit).all()

    @staticmethod
    def get_run_stats(db: Session) -> dict:
        """Get aggregate statistics for backtest runs."""
        total_runs = db.query(func.count(BacktestRun.id)).scalar()
        completed_runs = db.query(func.count(BacktestRun.id)).filter(
            BacktestRun.status == "completed"
        ).scalar()
        avg_pnl = db.query(func.avg(BacktestRun.total_pnl)).filter(
            BacktestRun.status == "completed"
        ).scalar()

        return {
            "total_runs": total_runs or 0,
            "completed_runs": completed_runs or 0,
            "failed_runs": db.query(func.count(BacktestRun.id)).filter(
                BacktestRun.status == "failed"
            ).scalar() or 0,
            "avg_pnl": float(avg_pnl) if avg_pnl else 0.0
        }


class BacktestResultService:
    """Service for individual backtest results."""

    @staticmethod
    def create_result(
        db: Session, run_id_fk: int, market_1: str, market_2: str,
        metrics: dict
    ) -> BacktestResult:
        """Create backtest result for a pair."""
        result = BacktestResult(
            run_id_fk=run_id_fk,
            market_1=market_1,
            market_2=market_2,
            **metrics
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        return result

    @staticmethod
    def get_run_results(
        db: Session, run_id_fk: int, skip: int = 0, limit: int = 1000
    ) -> List[BacktestResult]:
        """Get all results for a backtest run."""
        return db.query(BacktestResult).filter(
            BacktestResult.run_id_fk == run_id_fk
        ).offset(skip).limit(limit).all()

    @staticmethod
    def get_profitable_pairs(
        db: Session, run_id_fk: int
    ) -> List[BacktestResult]:
        """Get profitable trading pairs from a run."""
        return db.query(BacktestResult).filter(
            and_(
                BacktestResult.run_id_fk == run_id_fk,
                BacktestResult.pnl > 0
            )
        ).order_by(desc(BacktestResult.pnl)).all()

    @staticmethod
    def get_top_pairs(
        db: Session, limit: int = 10, metric: str = "pnl"
    ) -> List[BacktestResult]:
        """Get top trading pairs across all runs."""
        column = getattr(BacktestResult, metric, BacktestResult.pnl)
        return db.query(BacktestResult).order_by(
            desc(column)
        ).limit(limit).all()


class TradeLogService:
    """Service for trade logs."""

    @staticmethod
    def create_trade(
        db: Session, result_id_fk: int, trade_number: int,
        trade_data: dict
    ) -> TradeLog:
        """Create trade log entry."""
        trade = TradeLog(
            result_id_fk=result_id_fk,
            trade_number=trade_number,
            **trade_data
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)
        return trade

    @staticmethod
    def get_result_trades(
        db: Session, result_id_fk: int
    ) -> List[TradeLog]:
        """Get all trades for a backtest result."""
        return db.query(TradeLog).filter(
            TradeLog.result_id_fk == result_id_fk
        ).all()


class AuditLogService:
    """Service for audit logging."""

    @staticmethod
    def log_action(
        db: Session, action: str, resource_type: str,
        user_id: Optional[int] = None, resource_id: Optional[str] = None,
        details: Optional[dict] = None, status: str = "success",
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """Log an action to audit trail."""
        audit = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            status=status,
            ip_address=ip_address,
            created_at=datetime.utcnow()
        )
        db.add(audit)
        db.commit()
        logger.info(f"Audit: {action} on {resource_type} by user {user_id}")
        return audit

    @staticmethod
    def get_user_actions(
        db: Session, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[AuditLog]:
        """Get user action history."""
        return db.query(AuditLog).filter(
            AuditLog.user_id == user_id
        ).order_by(
            desc(AuditLog.created_at)
        ).offset(skip).limit(limit).all()
