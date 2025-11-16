"""
Data Access Layer (Repository pattern) for database operations
Provides clean interface for bot, job, and trade management
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from internal.domain import (
    BotInstance,
    BotStatusEnum,
    EventLog,
    Job,
    JobStatusEnum,
    Trade,
    TradeStatusEnum,
)

logger = logging.getLogger(__name__)


class BotRepository:
    """Repository for bot instance operations"""

    def __init__(self, session: Session):
        self.session = session

    def create_bot(
        self, instance_id: str, network: str, strategy: str, config: Dict
    ) -> BotInstance:
        """Create new bot instance"""
        bot = BotInstance(
            instance_id=instance_id,
            network=network,
            strategy=strategy,
            config_json=config,
            status=BotStatusEnum.CREATED,
        )
        self.session.add(bot)
        self.session.commit()
        logger.info(f"Created bot instance: {instance_id}")
        return bot

    def get_by_instance_id(self, instance_id: str) -> Optional[BotInstance]:
        """Get bot by instance ID"""
        return (
            self.session.query(BotInstance)
            .filter(BotInstance.instance_id == instance_id)
            .first()
        )

    def get_by_id(self, bot_id: int) -> Optional[BotInstance]:
        """Get bot by database ID"""
        return self.session.query(BotInstance).filter(BotInstance.id == bot_id).first()

    def get_all(self, status: Optional[BotStatusEnum] = None) -> List[BotInstance]:
        """Get all bots, optionally filtered by status"""
        query = self.session.query(BotInstance)
        if status:
            query = query.filter(BotInstance.status == status)
        return query.order_by(desc(BotInstance.created_at)).all()

    def get_running(self) -> List[BotInstance]:
        """Get all running bots"""
        return self.get_all(status=BotStatusEnum.RUNNING)

    def update_status(
        self, instance_id: str, status: BotStatusEnum, process_id: Optional[int] = None
    ):
        """Update bot status"""
        bot = self.get_by_instance_id(instance_id)
        if not bot:
            raise ValueError(f"Bot {instance_id} not found")

        bot.status = status
        if status == BotStatusEnum.RUNNING and process_id:
            bot.process_id = process_id
            bot.started_at = datetime.utcnow()
            bot.process_started_at = datetime.utcnow()
        elif status == BotStatusEnum.STOPPED:
            bot.stopped_at = datetime.utcnow()
            bot.process_ended_at = datetime.utcnow()

        self.session.commit()
        logger.info(f"Updated bot {instance_id} status to {status}")

    def update_heartbeat(self, instance_id: str):
        """Update bot last heartbeat"""
        bot = self.get_by_instance_id(instance_id)
        if bot:
            bot.last_heartbeat = datetime.utcnow()
            self.session.commit()

    def update_statistics(
        self,
        instance_id: str,
        total_trades: int = None,
        successful_trades: int = None,
        failed_trades: int = None,
        profit_loss: float = None,
    ):
        """Update bot trading statistics"""
        bot = self.get_by_instance_id(instance_id)
        if not bot:
            raise ValueError(f"Bot {instance_id} not found")

        if total_trades is not None:
            bot.total_trades = total_trades
        if successful_trades is not None:
            bot.successful_trades = successful_trades
        if failed_trades is not None:
            bot.failed_trades = failed_trades
        if profit_loss is not None:
            bot.total_profit_loss = profit_loss

        self.session.commit()
        logger.info(f"Updated bot {instance_id} statistics")

    def update_trading_params(
        self,
        instance_id: str,
        usd_per_trade: float = None,
        zscore_threshold: float = None,
    ):
        """Update bot trading parameters"""
        bot = self.get_by_instance_id(instance_id)
        if not bot:
            raise ValueError(f"Bot {instance_id} not found")

        if usd_per_trade is not None:
            bot.usd_per_trade = usd_per_trade
        if zscore_threshold is not None:
            bot.zscore_threshold = zscore_threshold

        self.session.commit()

    def delete_bot(self, instance_id: str):
        """Delete bot and all related data"""
        bot = self.get_by_instance_id(instance_id)
        if not bot:
            raise ValueError(f"Bot {instance_id} not found")

        self.session.delete(bot)
        self.session.commit()
        logger.info(f"Deleted bot {instance_id}")

    def get_statistics(self, instance_id: str) -> Dict[str, Any]:
        """Get bot statistics summary"""
        bot = self.get_by_instance_id(instance_id)
        if not bot:
            return {}

        return {
            "total_trades": bot.total_trades,
            "successful_trades": bot.successful_trades,
            "failed_trades": bot.failed_trades,
            "win_rate": (bot.successful_trades / bot.total_trades * 100)
            if bot.total_trades > 0
            else 0,
            "total_profit_loss": bot.total_profit_loss,
            "uptime_seconds": int((datetime.utcnow() - bot.started_at).total_seconds())
            if bot.started_at
            else 0,
        }


class JobRepository:
    """Repository for job operations"""

    def __init__(self, session: Session):
        self.session = session

    def create_job(
        self, job_id: str, bot_id: int, job_type: str, parameters: Dict = None
    ) -> Job:
        """Create new job"""
        job = Job(
            job_id=job_id,
            bot_instance_id=bot_id,
            job_type=job_type,
            parameters=parameters,
            status=JobStatusEnum.QUEUED,
        )
        self.session.add(job)
        self.session.commit()
        logger.info(f"Created job {job_id} - {job_type}")
        return job

    def get_by_job_id(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        return self.session.query(Job).filter(Job.job_id == job_id).first()

    def get_by_process_id(self, process_id: int) -> Optional[Job]:
        """Get job by OS process ID"""
        return self.session.query(Job).filter(Job.process_id == process_id).first()

    def get_bot_jobs(
        self, bot_id: int, status: Optional[JobStatusEnum] = None
    ) -> List[Job]:
        """Get jobs for a bot"""
        query = self.session.query(Job).filter(Job.bot_instance_id == bot_id)
        if status:
            query = query.filter(Job.status == status)
        return query.order_by(desc(Job.created_at)).all()

    def get_pending_jobs(self) -> List[Job]:
        """Get all pending jobs"""
        return (
            self.session.query(Job)
            .filter(Job.status == JobStatusEnum.QUEUED)
            .order_by(Job.created_at)
            .all()
        )

    def get_running_jobs(self) -> List[Job]:
        """Get all running jobs"""
        return self.session.query(Job).filter(Job.status == JobStatusEnum.RUNNING).all()

    def start_job(self, job_id: str, process_id: int):
        """Mark job as started"""
        job = self.get_by_job_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = JobStatusEnum.RUNNING
        job.process_id = process_id
        job.started_at = datetime.utcnow()
        self.session.commit()
        logger.info(f"Started job {job_id} with PID {process_id}")

    def complete_job(
        self, job_id: str, result: Dict = None, execution_time_ms: int = None
    ):
        """Mark job as completed"""
        job = self.get_by_job_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = JobStatusEnum.COMPLETED
        job.result = result
        job.completed_at = datetime.utcnow()
        if execution_time_ms:
            job.execution_time_ms = execution_time_ms

        self.session.commit()
        logger.info(f"Completed job {job_id}")

    def fail_job(self, job_id: str, error_message: str, error_traceback: str = None):
        """Mark job as failed"""
        job = self.get_by_job_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = JobStatusEnum.FAILED
        job.error_message = error_message
        job.error_traceback = error_traceback
        job.completed_at = datetime.utcnow()

        # Check if retry is possible
        if job.retry_count < job.max_retries:
            job.retry_count += 1
            job.status = JobStatusEnum.RETRY
            logger.info(f"Job {job_id} will be retried (attempt {job.retry_count})")
        else:
            logger.error(f"Job {job_id} failed permanently: {error_message}")

        self.session.commit()

    def get_job_history(self, bot_id: int, days: int = 7) -> List[Job]:
        """Get job history for a bot"""
        start_date = datetime.utcnow() - timedelta(days=days)
        return (
            self.session.query(Job)
            .filter(and_(Job.bot_instance_id == bot_id, Job.created_at >= start_date))
            .order_by(desc(Job.created_at))
            .all()
        )


class TradeRepository:
    """Repository for trade operations"""

    def __init__(self, session: Session):
        self.session = session

    def create_trade(
        self,
        trade_id: str,
        bot_id: int,
        pair1: str,
        pair2: str,
        entry_price1: float,
        entry_price2: float,
        entry_size1: float,
        entry_size2: float,
    ) -> Trade:
        """Create new trade"""
        trade = Trade(
            trade_id=trade_id,
            bot_instance_id=bot_id,
            pair1=pair1,
            pair2=pair2,
            entry_price1=entry_price1,
            entry_price2=entry_price2,
            entry_size1=entry_size1,
            entry_size2=entry_size2,
            status=TradeStatusEnum.OPENED,
        )
        self.session.add(trade)
        self.session.commit()
        logger.info(f"Created trade {trade_id}: {pair1}/{pair2}")
        return trade

    def get_by_trade_id(self, trade_id: str) -> Optional[Trade]:
        """Get trade by ID"""
        return self.session.query(Trade).filter(Trade.trade_id == trade_id).first()

    def get_bot_trades(
        self, bot_id: int, status: Optional[TradeStatusEnum] = None
    ) -> List[Trade]:
        """Get trades for a bot"""
        query = self.session.query(Trade).filter(Trade.bot_instance_id == bot_id)
        if status:
            query = query.filter(Trade.status == status)
        return query.order_by(desc(Trade.opened_at)).all()

    def get_open_trades(self, bot_id: int) -> List[Trade]:
        """Get open trades for a bot"""
        return (
            self.session.query(Trade)
            .filter(
                and_(
                    Trade.bot_instance_id == bot_id,
                    Trade.status.in_(
                        [TradeStatusEnum.OPENED, TradeStatusEnum.PARTIALLY_CLOSED]
                    ),
                )
            )
            .all()
        )

    def close_trade(
        self,
        trade_id: str,
        exit_price1: float,
        exit_price2: float,
        exit_size1: float,
        exit_size2: float,
        exit_tx_hash: str = None,
    ):
        """Close a trade"""
        trade = self.get_by_trade_id(trade_id)
        if not trade:
            raise ValueError(f"Trade {trade_id} not found")

        trade.exit_price1 = exit_price1
        trade.exit_price2 = exit_price2
        trade.exit_size1 = exit_size1
        trade.exit_size2 = exit_size2
        trade.exit_tx_hash = exit_tx_hash
        trade.closed_at = datetime.utcnow()
        trade.status = TradeStatusEnum.CLOSED

        # Calculate P&L
        entry_cost = (trade.entry_price1 * trade.entry_size1) + (
            trade.entry_price2 * trade.entry_size2
        )
        exit_proceeds = (exit_price1 * exit_size1) + (exit_price2 * exit_size2)
        trade.entry_cost = entry_cost
        trade.exit_proceeds = exit_proceeds
        trade.profit_loss = (
            exit_proceeds - entry_cost - (trade.entry_fees + trade.exit_fees)
        )
        trade.profit_loss_percentage = (
            (trade.profit_loss / entry_cost * 100) if entry_cost != 0 else 0
        )

        trade.calculate_duration()
        self.session.commit()
        logger.info(f"Closed trade {trade_id}, P&L: {trade.profit_loss}")

    def get_trade_statistics(self, bot_id: int) -> Dict[str, Any]:
        """Get trade statistics for a bot"""
        trades = self.get_bot_trades(bot_id)
        closed_trades = [t for t in trades if t.status == TradeStatusEnum.CLOSED]

        total_profit = sum(t.profit_loss for t in closed_trades if t.profit_loss)
        winning_trades = sum(
            1 for t in closed_trades if t.profit_loss and t.profit_loss > 0
        )
        losing_trades = sum(
            1 for t in closed_trades if t.profit_loss and t.profit_loss < 0
        )

        return {
            "total_trades": len(closed_trades),
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": (winning_trades / len(closed_trades) * 100)
            if closed_trades
            else 0,
            "total_profit_loss": total_profit,
            "average_trade_pnl": (total_profit / len(closed_trades))
            if closed_trades
            else 0,
        }


class EventLogRepository:
    """Repository for event logging"""

    def __init__(self, session: Session):
        self.session = session

    def log_event(
        self,
        bot_id: int,
        event_type: str,
        severity: str,
        message: str,
        details: Dict = None,
        related_job_id: str = None,
        related_trade_id: str = None,
    ) -> EventLog:
        """Log an event"""
        event = EventLog(
            bot_instance_id=bot_id,
            event_type=event_type,
            severity=severity,
            message=message,
            details=details,
            related_job_id=related_job_id,
            related_trade_id=related_trade_id,
        )
        self.session.add(event)
        self.session.commit()
        logger.info(f"Logged event: {event_type} - {severity}")
        return event

    def get_bot_events(
        self, bot_id: int, event_type: str = None, days: int = 7
    ) -> List[EventLog]:
        """Get events for a bot"""
        start_date = datetime.utcnow() - timedelta(days=days)
        query = self.session.query(EventLog).filter(
            and_(EventLog.bot_instance_id == bot_id, EventLog.created_at >= start_date)
        )
        if event_type:
            query = query.filter(EventLog.event_type == event_type)
        return query.order_by(desc(EventLog.created_at)).all()

    def get_errors(self, bot_id: int, days: int = 7) -> List[EventLog]:
        """Get error events for a bot"""
        return (
            self.session.query(EventLog)
            .filter(
                and_(
                    EventLog.bot_instance_id == bot_id,
                    EventLog.severity.in_(["error", "critical"]),
                    EventLog.created_at >= datetime.utcnow() - timedelta(days=days),
                )
            )
            .order_by(desc(EventLog.created_at))
            .all()
        )


class UnitOfWork:
    """Unit of Work pattern for transaction management"""

    def __init__(self, session: Session):
        self.session = session
        self.bots = BotRepository(session)
        self.jobs = JobRepository(session)
        self.trades = TradeRepository(session)
        self.events = EventLogRepository(session)

    def commit(self):
        """Commit transaction"""
        self.session.commit()

    def rollback(self):
        """Rollback transaction"""
        self.session.rollback()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.session.close()


def get_uow(session: Session) -> UnitOfWork:
    """Get Unit of Work instance for dependency injection"""
    return UnitOfWork(session)
