"""
Repository classes for core bot operations
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from internal.domain.models import Bot, Job, Trade, BotStatusEnum, JobStatusEnum, TradeStatusEnum


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


class JobRepository:
    """Repository for job operations"""

    def __init__(self, session: Session):
        self.session = session

    def create_job(self, bot_id: int, job_type: str, config: Optional[dict] = None) -> Job:
        """Create a new job"""
        job = Job(
            bot_id=bot_id,
            job_type=job_type,
            config=config,
        )
        self.session.add(job)
        self.session.commit()
        return job

    def get_by_id(self, job_id: int) -> Optional[Job]:
        """Get job by ID"""
        return self.session.query(Job).filter(Job.id == job_id).first()

    def get_by_bot_id(self, bot_id: int) -> List[Job]:
        """Get all jobs for a bot"""
        return self.session.query(Job).filter(Job.bot_id == bot_id).all()

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

    def create_trade(self, bot_id: int, position_id: str, pair1: str, pair2: str,
                    side1: str, side2: str, entry_price1: float, entry_price2: float,
                    entry_size1: float, entry_size2: float) -> Trade:
        """Create a new trade"""
        trade = Trade(
            bot_id=bot_id,
            position_id=position_id,
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
        return self.session.query(Trade).filter(Trade.position_id == position_id).first()

    def get_by_bot_id(self, bot_id: int) -> List[Trade]:
        """Get all trades for a bot"""
        return self.session.query(Trade).filter(Trade.bot_id == bot_id).all()

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


class UnitOfWork:
    """Unit of Work for core bot operations"""

    def __init__(self, session: Session):
        self.session = session
        self.bots = BotRepository(session)
        self.jobs = JobRepository(session)
        self.trades = TradeRepository(session)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.session.rollback()
        else:
            self.session.commit()
