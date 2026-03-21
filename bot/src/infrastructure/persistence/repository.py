"""
Repository classes for core bot operations
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from internal.domain.models import (
    Bot,
    Event,
    Job,
    Trade,
    Strategy,
    StrategyVersion,
    BotStatusEnum,
    JobStatusEnum,
    TradeStatusEnum,
)


class BotRepository:
    """Repository for bot operations"""

    def __init__(self, session: Session):
        self.session = session

    def create_bot(
        self, instance_id: str, network: str, strategy: str, config: dict
    ) -> Bot:
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

    def update_status(
        self, instance_id: str, status: BotStatusEnum, process_id: Optional[int] = None
    ):
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
        successful_trades = len(
            [
                t
                for t in trades
                if t.status == TradeStatusEnum.CLOSED and t.realized_pnl > 0
            ]
        )
        failed_trades = len(
            [
                t
                for t in trades
                if t.status == TradeStatusEnum.CLOSED and t.realized_pnl <= 0
            ]
        )
        total_pnl = sum(t.realized_pnl for t in trades if t.realized_pnl)

        return {
            "total_trades": total_trades,
            "successful_trades": successful_trades,
            "failed_trades": failed_trades,
            "total_profit_loss": total_pnl,
            "win_rate": (
                (successful_trades / total_trades * 100) if total_trades > 0 else 0
            ),
        }


class JobRepository:
    """Repository for job operations"""

    def __init__(self, session: Session):
        self.session = session

    def create_job(
        self, job_id: str, bot_id: int, job_type: str, parameters: Optional[dict] = None
    ) -> Job:
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

    def complete_job(
        self,
        job_id: str,
        result: Optional[dict] = None,
        execution_time_ms: Optional[int] = None,
    ):
        """Complete a job"""
        from datetime import datetime

        job = self.get_by_job_id(job_id)
        if job:
            job.status = JobStatusEnum.COMPLETED
            job.result = result
            job.completed_at = datetime.utcnow()
            self.session.commit()

    def fail_job(
        self, job_id: str, error_message: str, error_traceback: Optional[str] = None
    ):
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
        return (
            self.session.query(Job)
            .filter(Job.bot_id == bot_id, Job.created_at >= cutoff_date)
            .order_by(Job.created_at.desc())
            .all()
        )

    def update_status(
        self,
        job_id: int,
        status: JobStatusEnum,
        result: Optional[dict] = None,
        error_message: Optional[str] = None,
    ):
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
            elif status in [
                JobStatusEnum.COMPLETED,
                JobStatusEnum.FAILED,
                JobStatusEnum.CANCELLED,
            ]:
                job.completed_at = datetime.utcnow()
            self.session.commit()


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
        side1: str = "BUY",
        side2: str = "SELL",
    ) -> Trade:
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

    def close_trade(
        self,
        trade_id: str,
        exit_price1: Optional[float] = None,
        exit_price2: Optional[float] = None,
        exit_size1: Optional[float] = None,
        exit_size2: Optional[float] = None,
    ):
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
            if (
                exit_price1
                and exit_price2
                and trade.entry_price1
                and trade.entry_price2
            ):
                # Simple P&L calculation
                pnl1 = (exit_price1 - trade.entry_price1) * trade.entry_size1
                pnl2 = (trade.entry_price2 - exit_price2) * trade.entry_size2
                trade.profit_loss = pnl1 + pnl2
                trade.profit_loss_percentage = (
                    trade.profit_loss
                    / (
                        trade.entry_price1 * trade.entry_size1
                        + trade.entry_price2 * trade.entry_size2
                    )
                ) * 100
            trade.status = TradeStatusEnum.CLOSED
            trade.closed_at = datetime.utcnow()
            self.session.commit()

    def get_trade_statistics(self, bot_id: int) -> dict:
        """Get trade statistics for a bot"""
        trades = self.get_by_bot_id(bot_id)
        total_trades = len(trades)
        winning_trades = len(
            [
                t
                for t in trades
                if t.status == TradeStatusEnum.CLOSED and t.profit_loss > 0
            ]
        )
        losing_trades = len(
            [
                t
                for t in trades
                if t.status == TradeStatusEnum.CLOSED and t.profit_loss <= 0
            ]
        )
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

    def update_trade_exit(
        self,
        position_id: str,
        exit_price1: Optional[float] = None,
        exit_price2: Optional[float] = None,
        exit_size1: Optional[float] = None,
        exit_size2: Optional[float] = None,
        realized_pnl: float = 0.0,
        realized_pnl_pct: float = 0.0,
    ):
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

    def log_event(
        self,
        bot_instance_id: int,
        event_type: str,
        severity: str,
        message: str,
        details: Optional[dict] = None,
        user_id: Optional[str] = None,
        related_job_id: Optional[str] = None,
        related_trade_id: Optional[str] = None,
    ) -> Event:
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
        return (
            self.session.query(Event)
            .filter(
                Event.bot_instance_id == bot_instance_id,
                Event.created_at >= cutoff_date,
            )
            .order_by(Event.created_at.desc())
            .all()
        )

    def get_all_events(self, days: int = 7) -> List[Event]:
        """Get all events within the last N days"""
        from datetime import datetime, timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return (
            self.session.query(Event)
            .filter(Event.created_at >= cutoff_date)
            .order_by(Event.created_at.desc())
            .all()
        )


class StrategyRepository:
    """Repository for persistent strategy operations"""

    def __init__(self, session: Session):
        self.session = session

    def _to_dict(self, strategy: Strategy) -> dict:
        return {
            "id": strategy.id,
            "name": strategy.name,
            "category": strategy.category,
            "description": strategy.description,
            "is_public": strategy.is_public,
            "is_default": strategy.is_default,
            "user_id": strategy.user_id,
            "resolution": strategy.candle_resolution,
            "zscore_threshold": float(strategy.zscore_threshold),
            "stats_window": int(strategy.stats_window),
            "max_half_life": float(strategy.max_half_life),
            "usd_per_trade": float(strategy.usd_per_trade),
            "usd_min_collateral": float(strategy.usd_min_collateral),
            "close_at_zscore_cross": strategy.close_at_zscore_cross,
            "find_cointegrated_pairs": strategy.find_cointegrated_pairs,
            "manage_exits": strategy.manage_exits,
            "place_trades": strategy.place_trades,
            "abort_all_positions": strategy.abort_all_positions,
            "max_positions": int(strategy.max_positions),
            "max_drawdown_pct": float(strategy.max_drawdown_pct),
            "stop_loss_pct": float(strategy.stop_loss_pct),
            "take_profit_pct": float(strategy.take_profit_pct),
            "trailing_stop_pct": float(strategy.trailing_stop_pct),
            "rebalance_interval_hours": int(strategy.rebalance_interval_hours),
            "position_timeout_hours": int(strategy.position_timeout_hours),
            "transaction_fee": float(strategy.transaction_fee),
            "slippage": float(strategy.slippage),
            "starting_balance": float(strategy.starting_balance),
            "candle_resolution": strategy.candle_resolution,
            "max_history_days": int(strategy.max_history_days),
            "benchmark_symbol": strategy.benchmark_symbol,
            "risk_free_rate": float(strategy.risk_free_rate),
            "initial_amount": float(strategy.initial_amount),
            "usage_count": int(strategy.usage_count or 0),
            "last_used_at": (
                strategy.last_used_at.isoformat() if strategy.last_used_at else None
            ),
            "created_at": (
                strategy.created_at.isoformat() if strategy.created_at else None
            ),
            "updated_at": (
                strategy.updated_at.isoformat() if strategy.updated_at else None
            ),
            "deleted_at": (
                strategy.deleted_at.isoformat() if strategy.deleted_at else None
            ),
        }

    def list(self, skip: int = 0, limit: int = 50) -> dict:
        query = (
            self.session.query(Strategy)
            .filter(Strategy.deleted_at.is_(None))
            .order_by(Strategy.id.desc())
        )
        total = query.count()
        rows = query.offset(skip).limit(limit).all()
        return {"strategies": [self._to_dict(s) for s in rows], "total": total}

    def list_public(self) -> dict:
        rows = (
            self.session.query(Strategy)
            .filter(Strategy.is_public.is_(True), Strategy.deleted_at.is_(None))
            .order_by(Strategy.id.desc())
            .all()
        )
        return {"strategies": [self._to_dict(s) for s in rows], "total": len(rows)}

    def get(self, strategy_id: int) -> Optional[dict]:
        row = (
            self.session.query(Strategy)
            .filter(Strategy.id == strategy_id, Strategy.deleted_at.is_(None))
            .first()
        )
        return self._to_dict(row) if row else None

    def create(self, payload: dict, note: str = "Initial version") -> dict:
        strategy = Strategy(
            name=payload.get("name", "Untitled Strategy"),
            category=payload.get("category", "custom"),
            description=payload.get("description", ""),
            is_public=bool(payload.get("is_public", False)),
            is_default=bool(payload.get("is_default", False)),
            user_id=int(payload.get("user_id", 1)),
            zscore_threshold=float(payload.get("zscore_threshold", 1.5)),
            stats_window=int(payload.get("stats_window", 21)),
            max_half_life=float(payload.get("max_half_life", 24.0)),
            usd_per_trade=float(payload.get("usd_per_trade", 10.0)),
            usd_min_collateral=float(payload.get("usd_min_collateral", 100.0)),
            close_at_zscore_cross=bool(payload.get("close_at_zscore_cross", True)),
            find_cointegrated_pairs=bool(payload.get("find_cointegrated_pairs", True)),
            manage_exits=bool(payload.get("manage_exits", True)),
            place_trades=bool(payload.get("place_trades", True)),
            abort_all_positions=bool(payload.get("abort_all_positions", False)),
            max_positions=int(payload.get("max_positions", 5)),
            max_drawdown_pct=float(payload.get("max_drawdown_pct", 15.0)),
            stop_loss_pct=float(payload.get("stop_loss_pct", 3.0)),
            take_profit_pct=float(payload.get("take_profit_pct", 8.0)),
            trailing_stop_pct=float(payload.get("trailing_stop_pct", 2.0)),
            rebalance_interval_hours=int(payload.get("rebalance_interval_hours", 24)),
            position_timeout_hours=int(payload.get("position_timeout_hours", 72)),
            transaction_fee=float(payload.get("transaction_fee", 0.0005)),
            slippage=float(payload.get("slippage", 0.001)),
            starting_balance=float(payload.get("starting_balance", 1000.0)),
            candle_resolution=payload.get(
                "candle_resolution",
                payload.get("resolution", "1HOUR"),
            ),
            max_history_days=int(payload.get("max_history_days", 90)),
            benchmark_symbol=payload.get("benchmark_symbol", "BTC-USD"),
            risk_free_rate=float(payload.get("risk_free_rate", 0.02)),
            initial_amount=float(
                payload.get("initial_amount", payload.get("starting_balance", 1000.0))
            ),
        )
        self.session.add(strategy)
        self.session.flush()

        latest_version = (
            self.session.query(StrategyVersion)
            .filter(StrategyVersion.strategy_id == strategy.id)
            .order_by(StrategyVersion.version_number.desc())
            .first()
        )
        next_version = (latest_version.version_number + 1) if latest_version else 1

        version = StrategyVersion(
            strategy_id=strategy.id,
            version_number=next_version,
            change_description=note,
            config_snapshot=self._to_dict(strategy),
            changes={},
            created_by_user_id=int(payload.get("user_id", 1)),
        )
        self.session.add(version)
        self.session.commit()
        self.session.refresh(strategy)
        return self._to_dict(strategy)

    def update(
        self, strategy_id: int, payload: dict, note: str = "Updated strategy"
    ) -> Optional[dict]:
        strategy = (
            self.session.query(Strategy)
            .filter(Strategy.id == strategy_id, Strategy.deleted_at.is_(None))
            .first()
        )
        if not strategy:
            return None

        current = self._to_dict(strategy)
        merged = {**current, **payload}

        strategy.name = merged.get("name", strategy.name)
        strategy.category = merged.get("category", strategy.category)
        strategy.description = merged.get("description", strategy.description)
        strategy.is_public = bool(merged.get("is_public", strategy.is_public))
        strategy.is_default = bool(merged.get("is_default", strategy.is_default))
        strategy.user_id = int(merged.get("user_id", strategy.user_id))
        strategy.zscore_threshold = float(
            merged.get("zscore_threshold", strategy.zscore_threshold)
        )
        strategy.stats_window = int(merged.get("stats_window", strategy.stats_window))
        strategy.max_half_life = float(
            merged.get("max_half_life", strategy.max_half_life)
        )
        strategy.usd_per_trade = float(
            merged.get("usd_per_trade", strategy.usd_per_trade)
        )
        strategy.usd_min_collateral = float(
            merged.get("usd_min_collateral", strategy.usd_min_collateral)
        )
        strategy.close_at_zscore_cross = bool(
            merged.get("close_at_zscore_cross", strategy.close_at_zscore_cross)
        )
        strategy.find_cointegrated_pairs = bool(
            merged.get("find_cointegrated_pairs", strategy.find_cointegrated_pairs)
        )
        strategy.manage_exits = bool(merged.get("manage_exits", strategy.manage_exits))
        strategy.place_trades = bool(merged.get("place_trades", strategy.place_trades))
        strategy.abort_all_positions = bool(
            merged.get("abort_all_positions", strategy.abort_all_positions)
        )
        strategy.max_positions = int(
            merged.get("max_positions", strategy.max_positions)
        )
        strategy.max_drawdown_pct = float(
            merged.get("max_drawdown_pct", strategy.max_drawdown_pct)
        )
        strategy.stop_loss_pct = float(
            merged.get("stop_loss_pct", strategy.stop_loss_pct)
        )
        strategy.take_profit_pct = float(
            merged.get("take_profit_pct", strategy.take_profit_pct)
        )
        strategy.trailing_stop_pct = float(
            merged.get("trailing_stop_pct", strategy.trailing_stop_pct)
        )
        strategy.rebalance_interval_hours = int(
            merged.get("rebalance_interval_hours", strategy.rebalance_interval_hours)
        )
        strategy.position_timeout_hours = int(
            merged.get("position_timeout_hours", strategy.position_timeout_hours)
        )
        strategy.transaction_fee = float(
            merged.get("transaction_fee", strategy.transaction_fee)
        )
        strategy.slippage = float(merged.get("slippage", strategy.slippage))
        strategy.starting_balance = float(
            merged.get("starting_balance", strategy.starting_balance)
        )
        strategy.candle_resolution = merged.get(
            "candle_resolution",
            merged.get("resolution", strategy.candle_resolution),
        )
        strategy.max_history_days = int(
            merged.get("max_history_days", strategy.max_history_days)
        )
        strategy.benchmark_symbol = merged.get(
            "benchmark_symbol", strategy.benchmark_symbol
        )
        strategy.risk_free_rate = float(
            merged.get("risk_free_rate", strategy.risk_free_rate)
        )
        strategy.initial_amount = float(
            merged.get("initial_amount", strategy.initial_amount)
        )

        self.session.flush()

        latest_version = (
            self.session.query(StrategyVersion)
            .filter(StrategyVersion.strategy_id == strategy.id)
            .order_by(StrategyVersion.version_number.desc())
            .first()
        )
        next_version = (latest_version.version_number + 1) if latest_version else 1

        version = StrategyVersion(
            strategy_id=strategy.id,
            version_number=next_version,
            change_description=note,
            config_snapshot=self._to_dict(strategy),
            changes={},
            created_by_user_id=int(merged.get("user_id", strategy.user_id)),
        )
        self.session.add(version)
        self.session.commit()
        self.session.refresh(strategy)
        return self._to_dict(strategy)

    def delete(self, strategy_id: int) -> bool:
        strategy = (
            self.session.query(Strategy)
            .filter(Strategy.id == strategy_id, Strategy.deleted_at.is_(None))
            .first()
        )
        if not strategy:
            return False
        strategy.deleted_at = datetime.utcnow()
        self.session.commit()
        return True

    def versions(self, strategy_id: int) -> List[dict]:
        rows = (
            self.session.query(StrategyVersion)
            .filter(StrategyVersion.strategy_id == strategy_id)
            .order_by(StrategyVersion.id.desc())
            .all()
        )
        return [
            {
                "id": row.id,
                "strategy_id": row.strategy_id,
                "name": row.config_snapshot.get("name", ""),
                "description": row.change_description,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "config": row.config_snapshot,
            }
            for row in rows
        ]

    def revert(self, strategy_id: int, version_id: int) -> Optional[dict]:
        version = (
            self.session.query(StrategyVersion)
            .filter(
                StrategyVersion.strategy_id == strategy_id,
                StrategyVersion.id == version_id,
            )
            .first()
        )
        if not version:
            return None
        return self.update(
            strategy_id,
            version.config_snapshot,
            note=f"Reverted to version {version_id}",
        )


class UnitOfWork:
    """Unit of Work for core bot operations"""

    def __init__(self, session: Session):
        self.session = session
        self.bots = BotRepository(session)
        self.jobs = JobRepository(session)
        self.trades = TradeRepository(session)
        self.events = EventRepository(session)
        self.strategies = StrategyRepository(session)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.session.rollback()
        else:
            self.session.commit()
