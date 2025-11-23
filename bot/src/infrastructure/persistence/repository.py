"""
Repository classes for core bot operations
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from internal.domain.models import Bot, Job, Trade, Event, BotStatusEnum, JobStatusEnum, TradeStatusEnum


class BotRepository:
    """Repository for bot operations"""

    def __init__(self, session: Session):
        self.session = session

    def create_bot(self, instance_id: str, network: str, strategy: str, config: dict) -> Bot:
        """Create a new bot"""
        bot = Bot(
            instance_id=instance_id,
            network=network,
            strategy=strategy,
            config=config,
        )
        self.session.add(bot)
        self.session.commit()
        return bot

    def get_by_instance_id(self, instance_id: str) -> Optional[Bot]:
        """Get bot by instance ID"""
        return self.session.query(Bot).filter(Bot.instance_id == instance_id).first()

    def get_all(self) -> List[Bot]:
        """Get all bots"""
        return self.session.query(Bot).all()

    def update_status(self, instance_id: str, status: BotStatusEnum, process_id: Optional[int] = None):
        """Update bot status"""
        bot = self.get_by_instance_id(instance_id)
        if bot:
            bot.status = status
            if process_id is not None:
                bot.process_id = process_id
            self.session.commit()

    def delete_bot(self, instance_id: str):
        """Delete a bot"""
        bot = self.get_by_instance_id(instance_id)
        if bot:
            self.session.delete(bot)
            self.session.commit()

    def get_statistics(self, instance_id: str) -> dict:
        """Get statistics for a bot"""
        bot = self.get_by_instance_id(instance_id)
        if not bot:
            return {}

        trades = self.session.query(Trade).filter(Trade.bot_id == bot.id).all()
        total_trades = len(trades)
        successful_trades = len([t for t in trades if t.status == TradeStatusEnum.CLOSED and t.realized_pnl > 0])
        failed_trades = len([t for t in trades if t.status == TradeStatusEnum.CLOSED and t.realized_pnl <= 0])
        total_pnl = sum(t.realized_pnl for t in trades if t.realized_pnl)

        return {
            "total_trades": total_trades,
            "successful_trades": successful_trades,
            "failed_trades": failed_trades,
            "total_profit_loss": total_pnl,
            "win_rate": (successful_trades / total_trades * 100) if total_trades > 0 else 0,
        }


class JobRepository:
    """Repository for job operations"""

    def __init__(self, session: Session):
        self.session = session

    def create_job(self, job_id: str, bot_id: int, job_type: str, parameters: Optional[dict] = None) -> Job:
        """Create a new job"""
        job = Job(
            job_id=job_id,
            bot_id=bot_id,
            job_type=job_type,
            config=parameters,
        )
        self.session.add(job)
        self.session.commit()
        return job

    def get_by_job_id(self, job_id: str) -> Optional[Job]:
        """Get job by job ID"""
        return self.session.query(Job).filter(Job.job_id == job_id).first()

    def get_by_id(self, job_id: int) -> Optional[Job]:
        """Get job by ID"""
        return self.session.query(Job).filter(Job.id == job_id).first()

    def get_by_bot_id(self, bot_id: int) -> List[Job]:
        """Get all jobs for a bot"""
        return self.session.query(Job).filter(Job.bot_id == bot_id).all()

    def start_job(self, job_id: str, process_id: Optional[int] = None):
        """Start a job"""
        from datetime import datetime
        job = self.get_by_job_id(job_id)
        if job:
            job.status = JobStatusEnum.RUNNING
            job.started_at = datetime.utcnow()
            if process_id is not None:
                # Assuming Job has process_id, but it doesn't. Maybe add it.
                pass
            self.session.commit()

    def complete_job(self, job_id: str, result: Optional[dict] = None, execution_time_ms: Optional[int] = None):
        """Complete a job"""
        from datetime import datetime
        job = self.get_by_job_id(job_id)
        if job:
            job.status = JobStatusEnum.COMPLETED
            job.result = result
            job.completed_at = datetime.utcnow()
            self.session.commit()

    def fail_job(self, job_id: str, error_message: str, error_traceback: Optional[str] = None):
        """Fail a job"""
        from datetime import datetime
        job = self.get_by_job_id(job_id)
        if job:
            job.status = JobStatusEnum.FAILED
            job.error_message = error_message
            job.completed_at = datetime.utcnow()
            self.session.commit()

    def get_job_history(self, bot_id: int, days: int = 7) -> List[Job]:
        """Get job history for a bot within the last N days"""
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return self.session.query(Job).filter(
            Job.bot_id == bot_id,
            Job.created_at >= cutoff_date
        ).order_by(Job.created_at.desc()).all()

    def update_status(self, job_id: int, status: JobStatusEnum, result: Optional[dict] = None,
                     error_message: Optional[str] = None):
        """Update job status"""
        from datetime import datetime
        job = self.get_by_id(job_id)
        if job:
            job.status = status
            if result is not None:
                job.result = result
            if error_message is not None:
                job.error_message = error_message
            if status == JobStatusEnum.RUNNING and not job.started_at:
                job.started_at = datetime.utcnow()
            elif status in [JobStatusEnum.COMPLETED, JobStatusEnum.FAILED, JobStatusEnum.CANCELLED]:
                job.completed_at = datetime.utcnow()
            self.session.commit()


class TradeRepository:
    """Repository for trade operations"""

    def __init__(self, session: Session):
        self.session = session

    def create_trade(self, trade_id: str, bot_id: int, pair1: str, pair2: str,
                    entry_price1: float, entry_price2: float, entry_size1: float, entry_size2: float,
                    side1: str = "BUY", side2: str = "SELL") -> Trade:
        """Create a new trade"""
        trade = Trade(
            bot_id=bot_id,
            trade_id=trade_id,
            pair1=pair1,
            pair2=pair2,
            side1=side1,
            side2=side2,
            entry_price1=entry_price1,
            entry_price2=entry_price2,
            entry_size1=entry_size1,
            entry_size2=entry_size2,
        )
        self.session.add(trade)
        self.session.commit()
        return trade

    def get_by_position_id(self, position_id: str) -> Optional[Trade]:
        """Get trade by position ID"""
        return self.session.query(Trade).filter(Trade.trade_id == position_id).first()

    def get_by_bot_id(self, bot_id: int) -> List[Trade]:
        """Get all trades for a bot"""
        return self.session.query(Trade).filter(Trade.bot_id == bot_id).all()

    def get_bot_trades(self, bot_id: int) -> List[Trade]:
        """Alias for get_by_bot_id"""
        return self.get_by_bot_id(bot_id)

    def close_trade(self, trade_id: str, exit_price1: Optional[float] = None,
                   exit_price2: Optional[float] = None, exit_size1: Optional[float] = None,
                   exit_size2: Optional[float] = None):
        """Close a trade"""
        from datetime import datetime
        trade = self.get_by_position_id(trade_id)
        if trade:
            if exit_price1 is not None:
                trade.exit_price1 = exit_price1
            if exit_price2 is not None:
                trade.exit_price2 = exit_price2
            if exit_size1 is not None:
                trade.exit_size1 = exit_size1
            if exit_size2 is not None:
                trade.exit_size2 = exit_size2
            # Calculate P&L
            if exit_price1 and exit_price2 and trade.entry_price1 and trade.entry_price2:
                # Simple P&L calculation
                pnl1 = (exit_price1 - trade.entry_price1) * trade.entry_size1
                pnl2 = (trade.entry_price2 - exit_price2) * trade.entry_size2
                trade.profit_loss = pnl1 + pnl2
                trade.profit_loss_percentage = (trade.profit_loss / (trade.entry_price1 * trade.entry_size1 + trade.entry_price2 * trade.entry_size2)) * 100
            trade.status = TradeStatusEnum.CLOSED
            trade.closed_at = datetime.utcnow()
            self.session.commit()

    def get_trade_statistics(self, bot_id: int) -> dict:
        """Get trade statistics for a bot"""
        trades = self.get_by_bot_id(bot_id)
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.status == TradeStatusEnum.CLOSED and t.profit_loss > 0])
        losing_trades = len([t for t in trades if t.status == TradeStatusEnum.CLOSED and t.profit_loss <= 0])
        total_profit_loss = sum(t.profit_loss for t in trades if t.profit_loss)
        average_trade_pnl = total_profit_loss / total_trades if total_trades > 0 else 0
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "total_profit_loss": total_profit_loss,
            "average_trade_pnl": average_trade_pnl,
            "win_rate": win_rate,
        }

    def update_trade_exit(self, position_id: str, exit_price1: Optional[float] = None,
                         exit_price2: Optional[float] = None, exit_size1: Optional[float] = None,
                         exit_size2: Optional[float] = None, realized_pnl: float = 0.0,
                         realized_pnl_pct: float = 0.0):
        """Update trade exit information"""
        from datetime import datetime
        trade = self.get_by_position_id(position_id)
        if trade:
            if exit_price1 is not None:
                trade.exit_price1 = exit_price1
            if exit_price2 is not None:
                trade.exit_price2 = exit_price2
            if exit_size1 is not None:
                trade.exit_size1 = exit_size1
            if exit_size2 is not None:
                trade.exit_size2 = exit_size2
            trade.realized_pnl = realized_pnl
            trade.realized_pnl_pct = realized_pnl_pct
            trade.status = TradeStatusEnum.CLOSED
            trade.closed_at = datetime.utcnow()
            self.session.commit()


class EventRepository:
    """Repository for event logging operations"""

    def __init__(self, session: Session):
        self.session = session

    def log_event(self, bot_instance_id: int, event_type: str, severity: str, message: str,
                  details: Optional[dict] = None, user_id: Optional[str] = None,
                  related_job_id: Optional[str] = None, related_trade_id: Optional[str] = None) -> Event:
        """Log an event"""
        event = Event(
            bot_instance_id=bot_instance_id,
            event_type=event_type,
            severity=severity,
            message=message,
            details=details,
            user_id=user_id,
            related_job_id=related_job_id,
            related_trade_id=related_trade_id,
        )
        self.session.add(event)
        self.session.commit()
        return event

    def get_bot_events(self, bot_instance_id: int, days: int = 7) -> List[Event]:
        """Get events for a bot within the last N days"""
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return self.session.query(Event).filter(
            Event.bot_instance_id == bot_instance_id,
            Event.created_at >= cutoff_date
        ).order_by(Event.created_at.desc()).all()

    def get_all_events(self, days: int = 7) -> List[Event]:
        """Get all events within the last N days"""
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return self.session.query(Event).filter(
            Event.created_at >= cutoff_date
        ).order_by(Event.created_at.desc()).all()


class UnitOfWork:
    """Unit of Work for core bot operations"""

    def __init__(self, session: Session):
        self.session = session
        self.bots = BotRepository(session)
        self.jobs = JobRepository(session)
        self.trades = TradeRepository(session)
        self.events = EventRepository(session)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.session.rollback()
        else:
            self.session.commit()
