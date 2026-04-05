"""
Real-time data update service
Captures live bot data and broadcasts updates via WebSocket
"""

import asyncio
import logging
from typing import Dict

from src.api.realtime_serializers import serialize_stats_risk_fields
from src.api.websocket_server import broadcast_position_update, broadcast_market_update, broadcast_stats_update, \
    broadcast_alert, broadcast_position_opened, broadcast_position_closed
from src.infrastructure.database import db
from src.shared.time_utils import utc_now_iso
from internal.repository.repository_realtime import UnitOfWorkRealtime

logger = logging.getLogger(__name__)


class RealTimeDataService:
    """Manages real-time data capture and broadcasting"""

    def __init__(self):
        self.update_tasks: Dict[int, asyncio.Task] = {}
        self.update_interval = 5  # seconds

    async def start_bot_monitoring(self, bot_instance_id: int):
        """Start monitoring data for a specific bot"""
        if bot_instance_id in self.update_tasks:
            logger.warning(f"Bot {bot_instance_id} already being monitored")
            return

        task = asyncio.create_task(self._monitor_bot(bot_instance_id))
        self.update_tasks[bot_instance_id] = task
        logger.info(f"Started monitoring bot {bot_instance_id}")

    async def stop_bot_monitoring(self, bot_instance_id: int):
        """Stop monitoring data for a specific bot"""
        if bot_instance_id not in self.update_tasks:
            return

        task = self.update_tasks.pop(bot_instance_id)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        logger.info(f"Stopped monitoring bot {bot_instance_id}")

    async def _monitor_bot(self, bot_instance_id: int):
        """Monitor and update data for a bot"""
        while True:
            try:
                await asyncio.sleep(self.update_interval)
                session = db.get_session()

                try:
                    uow = UnitOfWorkRealtime(session)

                    # Update position prices from current market data
                    await self._update_positions(bot_instance_id, uow)

                    # Update market data
                    await self._update_market_data(bot_instance_id, uow)

                    # Update statistics
                    await self._update_statistics(bot_instance_id, uow)

                    # Check alert conditions
                    await self._check_alerts(bot_instance_id, uow)

                finally:
                    session.close()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring bot {bot_instance_id}: {e}")

    async def _update_positions(self, bot_instance_id: int, uow: UnitOfWorkRealtime):
        """Update position prices and P&L"""
        try:
            positions = uow.positions.get_open_positions(bot_instance_id)

            for position in positions:
                # Get latest market prices
                market1 = uow.market_data.get_market_data(
                    bot_instance_id, position.pair1
                )
                market2 = uow.market_data.get_market_data(
                    bot_instance_id, position.pair2
                )

                if market1 and market2:
                    # Update position with new prices
                    uow.positions.update_position_prices(
                        position.position_id,
                        current_price1=float(market1.current_price),
                        current_price2=float(market2.current_price),
                    )

                    # Broadcast update
                    await broadcast_position_update(
                        bot_instance_id,
                        {
                            "position_id": position.position_id,
                            "pair1": position.pair1,
                            "pair2": position.pair2,
                            "current_price1": float(market1.current_price),
                            "current_price2": float(market2.current_price),
                            "unrealized_pnl": float(position.unrealized_pnl),
                            "unrealized_pnl_pct": float(position.unrealized_pnl_pct),
                            "updated_at": utc_now_iso(),
                        },
                    )

        except Exception as e:
            logger.error(f"Error updating positions for bot {bot_instance_id}: {e}")

    async def _update_market_data(self, bot_instance_id: int, uow: UnitOfWorkRealtime):
        """Update market data snapshots"""
        try:
            # This would be called with fresh market data from dYdX API
            # For now, just broadcast existing data
            market_data = uow.market_data.get_all_market_data(bot_instance_id)

            for market in market_data:
                await broadcast_market_update(
                    bot_instance_id,
                    {
                        "symbol": market.symbol,
                        "current_price": float(market.current_price),
                        "bid_price": float(market.bid_price)
                        if market.bid_price
                        else None,
                        "ask_price": float(market.ask_price)
                        if market.ask_price
                        else None,
                        "volume_24h": float(market.volume_24h)
                        if market.volume_24h
                        else None,
                        "updated_at": utc_now_iso(),
                    },
                )

        except Exception as e:
            logger.error(f"Error updating market data for bot {bot_instance_id}: {e}")

    async def _update_statistics(self, bot_instance_id: int, uow: UnitOfWorkRealtime):
        """Calculate and update bot statistics"""
        try:
            # Calculate stats from open positions
            uow.stats.calculate_and_update_stats(bot_instance_id, uow.positions)

            # Get updated stats
            stats = uow.stats.get_stats(bot_instance_id)

            if stats:
                await broadcast_stats_update(
                    bot_instance_id,
                    {
                        "total_open_positions": stats.total_open_positions,
                        "total_unrealized_pnl": float(stats.total_unrealized_pnl),
                        "total_unrealized_pnl_pct": float(
                            stats.total_unrealized_pnl_pct
                        ),
                        "daily_pnl": float(stats.daily_pnl),
                        "daily_pnl_pct": float(stats.daily_pnl_pct),
                        "daily_trades_opened": stats.daily_trades_opened,
                        "daily_trades_closed": stats.daily_trades_closed,
                        **serialize_stats_risk_fields(stats),
                        "updated_at": utc_now_iso(),
                    },
                )

        except Exception as e:
            logger.error(f"Error updating statistics for bot {bot_instance_id}: {e}")

    async def _check_alerts(self, bot_instance_id: int, uow: UnitOfWorkRealtime):
        """Check for alert conditions"""
        try:
            stats = uow.stats.get_stats(bot_instance_id)

            if not stats:
                return

            alerts_to_create = []

            # Check drawdown alert
            if (
                    stats.max_drawdown_session and stats.max_drawdown_session < -0.05
            ):  # -5% drawdown
                alerts_to_create.append(
                    {
                        "type": "max_drawdown",
                        "severity": "warning",
                        "message": f"Max drawdown reached: {stats.max_drawdown_session:.2%}",
                        "data": {"max_drawdown": float(stats.max_drawdown_session)},
                    }
                )

            # Check daily loss alert
            if stats.daily_pnl < 0 and stats.daily_pnl_pct < -0.10:  # -10% daily loss
                alerts_to_create.append(
                    {
                        "type": "daily_loss_limit",
                        "severity": "critical",
                        "message": f"Daily loss limit exceeded: {stats.daily_pnl_pct:.2%}",
                        "data": {
                            "daily_pnl": float(stats.daily_pnl),
                            "daily_pnl_pct": float(stats.daily_pnl_pct),
                        },
                    }
                )

            # Check high win rate
            if (
                    stats.daily_win_rate > 0.8 and stats.daily_trades_closed >= 5
            ):  # >80% win rate with 5+ trades
                alerts_to_create.append(
                    {
                        "type": "high_performance",
                        "severity": "info",
                        "message": f"High performance: {stats.daily_win_rate:.1%} win rate",
                        "data": {
                            "win_rate": float(stats.daily_win_rate),
                            "trades_closed": stats.daily_trades_closed,
                        },
                    }
                )

            # Create alerts and broadcast
            for alert_data in alerts_to_create:
                uow.alerts.create_alert(
                    bot_instance_id=bot_instance_id,
                    alert_type=alert_data["type"],
                    severity=alert_data["severity"],
                    message=alert_data["message"],
                    details=alert_data["data"],
                )

                await broadcast_alert(bot_instance_id, alert_data)

        except Exception as e:
            logger.error(f"Error checking alerts for bot {bot_instance_id}: {e}")

    async def add_position_opened(self, bot_instance_id: int, position_data: Dict):
        """Handle new position opened"""
        try:
            session = db.get_session()
            uow = UnitOfWorkRealtime(session)

            # Create position in database
            uow.positions.create_position(
                bot_instance_id=bot_instance_id,
                position_id=position_data["position_id"],
                pair1=position_data["pair1"],
                pair2=position_data["pair2"],
                side1=position_data["side1"],
                side2=position_data["side2"],
                entry_price1=position_data["entry_price1"],
                entry_price2=position_data["entry_price2"],
                entry_size1=position_data["entry_size1"],
                entry_size2=position_data["entry_size2"],
            )

            session.close()

            # Broadcast event
            await broadcast_position_opened(bot_instance_id, position_data)

        except Exception as e:
            logger.error(f"Error adding position: {e}")

    async def add_position_closed(self, bot_instance_id: int, position_data: Dict):
        """Handle position closed"""
        try:
            session = db.get_session()
            uow = UnitOfWorkRealtime(session)

            position_id = position_data["position_id"]
            realized_pnl = position_data.get("realized_pnl", 0)

            # Close position in database
            uow.positions.close_position(position_id=position_id)

            session.close()

            # Broadcast event
            position_data["realized_pnl"] = realized_pnl
            await broadcast_position_closed(bot_instance_id, position_data)

        except Exception as e:
            logger.error(f"Error closing position: {e}")

    async def update_market_data(
            self, bot_instance_id: int, symbol: str, market_data: Dict
    ):
        """Update market data for a symbol"""
        try:
            session = db.get_session()
            uow = UnitOfWorkRealtime(session)

            # Upsert market data
            uow.market_data.upsert_market_data(
                bot_instance_id=bot_instance_id,
                symbol=symbol,
                current_price=market_data["current_price"],
                bid_price=market_data.get("bid_price"),
                ask_price=market_data.get("ask_price"),
                volume_24h=market_data.get("volume_24h"),
                volatility_24h=market_data.get("volatility_24h"),
                rsi=market_data.get("rsi"),
                macd=market_data.get("macd"),
                moving_avg_20=market_data.get("moving_avg_20"),
                moving_avg_50=market_data.get("moving_avg_50"),
                funding_rate=market_data.get("funding_rate"),
            )

            session.close()

        except Exception as e:
            logger.error(f"Error updating market data: {e}")


# Global instance
realtime_service = RealTimeDataService()


async def start_realtime_service():
    """Initialize real-time service"""
    logger.info("Real-time data service started")


async def stop_realtime_service():
    """Shutdown real-time service"""
    for bot_id in list(realtime_service.update_tasks.keys()):
        await realtime_service.stop_bot_monitoring(bot_id)
    logger.info("Real-time data service stopped")
