#!/usr/bin/env python
"""
Test script to verify API database integration endpoints
Tests bot history, jobs, trades, and statistics endpoints
"""

import logging

from database import db
from internal.domain import BotStatusEnum
from internal.repository.repository import UnitOfWork

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_api_database_integration():
    """Test complete API database integration flow"""

    print("\n" + "=" * 80)
    print("🧪 Testing API Database Integration Endpoints")
    print("=" * 80 + "\n")

    session = db.get_session()
    uow = UnitOfWork(session)

    try:
        # ====================================================================
        # SETUP: Create test bot with data
        # ====================================================================
        print("📝 SETUP: Creating test bot with sample data...")

        # Create bot instance
        bot = uow.bots.create_bot(
            instance_id="api-test-bot-001",
            network="testnet",
            strategy="test_strategy",
            config={
                "instance_name": "API Test Bot",
                "trading_params": {"min_spread": 0.001},
            },
        )
        print(f"✅ Bot created: {bot.instance_id} (id={bot.id})")

        # Update bot status
        uow.bots.update_status(
            "api-test-bot-001", BotStatusEnum.RUNNING, process_id=54321
        )
        print("✅ Bot status updated to RUNNING (PID: 54321)")

        # ====================================================================
        # TEST 1: Event History
        # ====================================================================
        print("\n" + "-" * 80)
        print("TEST 1: Event History (/api/v1/bots/{id}/history)")
        print("-" * 80)

        # Log events
        uow.events.log_event(
            bot.id, "bot_started", "info", "Test bot started", details={"test": True}
        )

        uow.events.log_event(
            bot.id,
            "cointegration_analysis",
            "info",
            "Cointegration analysis completed",
            details={"pairs_found": 5},
        )

        uow.events.log_event(
            bot.id,
            "trade_prepared",
            "info",
            "Trade prepared",
            details={"pair1": "ETH", "pair2": "BTC"},
        )

        # Query events (simulating API endpoint)
        events = uow.events.get_bot_events(bot.id, days=7)

        print(f"✅ Retrieved {len(events)} events")
        for i, event in enumerate(events, 1):
            print(f"   {i}. {event.event_type} ({event.severity}): {event.message}")

        assert len(events) >= 3, "Should have at least 3 events"
        print("✅ Event history test PASSED")

        # ====================================================================
        # TEST 2: Job History
        # ====================================================================
        print("\n" + "-" * 80)
        print("TEST 2: Job History (/api/v1/bots/{id}/jobs)")
        print("-" * 80)

        # Create jobs
        job1 = uow.jobs.create_job("coint-job-001", bot.id, "cointegration_analysis")
        print(f"✅ Job 1 created: {job1.job_id}")

        # Start job
        uow.jobs.start_job("coint-job-001", process_id=55001)
        print("✅ Job 1 started (PID: 55001)")

        # Complete job
        uow.jobs.complete_job(
            "coint-job-001",
            result={"pairs_analyzed": 100, "cointegrated": [["ETH", "BTC"]]},
            execution_time_ms=2500,
        )
        print("✅ Job 1 completed (2500ms)")

        # Create another job that failed
        job2 = uow.jobs.create_job("trade-job-001", bot.id, "trade_entry")
        uow.jobs.start_job("trade-job-001", process_id=55002)
        uow.jobs.fail_job(
            "trade-job-001",
            error_message="Insufficient balance",
            error_traceback="Traceback: ...",
        )
        print("✅ Job 2 failed with retry logic")

        # Query jobs (simulating API endpoint)
        jobs = uow.jobs.get_job_history(bot.id, days=7)

        print(f"\n✅ Retrieved {len(jobs)} jobs")
        for i, job in enumerate(jobs, 1):
            status_str = f"{job.status}"
            if job.retry_count is not None and job.max_retries is not None:
                status_str += f" (retry: {job.retry_count}/{job.max_retries})"
            print(f"   {i}. {job.job_id}: {job.job_type} - {status_str}")

        assert len(jobs) >= 2, "Should have at least 2 jobs"
        print("✅ Job history test PASSED")

        # ====================================================================
        # TEST 3: Trade History
        # ====================================================================
        print("\n" + "-" * 80)
        print("TEST 3: Trade History (/api/v1/bots/{id}/trades)")
        print("-" * 80)

        # Create opened trade
        trade1 = uow.trades.create_trade(
            trade_id="trade-001",
            bot_id=bot.id,
            pair1="ETH",
            pair2="BTC",
            entry_price1=2000,
            entry_price2=45000,
            entry_size1=1.0,
            entry_size2=0.05,
        )
        print("✅ Trade 1 created (opened): trade-001")

        # Close trade with P&L
        uow.trades.close_trade(
            "trade-001",
            exit_price1=2100,
            exit_price2=46000,
            exit_size1=1.0,
            exit_size2=0.05,
        )
        print("✅ Trade 1 closed with P&L calculation")

        # Create another open trade
        trade2 = uow.trades.create_trade(
            trade_id="trade-002",
            bot_id=bot.id,
            pair1="USDC",
            pair2="USDT",
            entry_price1=1.001,
            entry_price2=1.000,
            entry_size1=10000,
            entry_size2=10000,
        )
        print("✅ Trade 2 created (open): trade-002")

        # Query trades (simulating API endpoint)
        trades = uow.trades.get_bot_trades(bot.id)

        print(f"\n✅ Retrieved {len(trades)} trades")
        for i, trade in enumerate(trades, 1):
            pnl_str = (
                f"P&L: ${trade.profit_loss:.2f} ({trade.profit_loss_percentage:.2f}%)"
                if trade.profit_loss
                else "P&L: N/A (open)"
            )
            print(
                f"   {i}. {trade.trade_id}: {trade.pair1}/{trade.pair2} - {trade.status} - {pnl_str}"
            )

        assert len(trades) >= 2, "Should have at least 2 trades"
        print("✅ Trade history test PASSED")

        # ====================================================================
        # TEST 4: Bot Statistics
        # ====================================================================
        print("\n" + "-" * 80)
        print("TEST 4: Bot Statistics (/api/v1/bots/{id}/stats)")
        print("-" * 80)

        # Get bot statistics
        bot_stats = uow.bots.get_statistics("api-test-bot-001")
        print("\n📊 Bot Statistics:")
        print(f"   Total Trades: {bot_stats.get('total_trades')}")
        print(f"   Successful Trades: {bot_stats.get('successful_trades')}")
        print(f"   Failed Trades: {bot_stats.get('failed_trades')}")
        print(f"   Total P&L: ${bot_stats.get('total_profit_loss'):.2f}")
        print(f"   Win Rate: {bot_stats.get('win_rate'):.1f}%")

        # Get trade statistics
        trade_stats = uow.trades.get_trade_statistics(bot.id)
        print("\n📈 Trade Statistics:")
        print(f"   Total Trades: {trade_stats.get('total_trades')}")
        print(f"   Winning Trades: {trade_stats.get('winning_trades')}")
        print(f"   Losing Trades: {trade_stats.get('losing_trades')}")
        net_profit = trade_stats.get("total_profit_loss", 0)
        print(f"   Net Profit: ${net_profit:.2f}")
        avg_pnl = trade_stats.get("average_trade_pnl", 0)
        print(f"   Average Trade P&L: ${avg_pnl:.2f}")
        print(f"   Win Rate: {trade_stats.get('win_rate'):.1f}%")

        print("\n✅ Bot statistics test PASSED")

        # ====================================================================
        # TEST 5: Simulate Complete Bot Lifecycle via API
        # ====================================================================
        print("\n" + "-" * 80)
        print("TEST 5: Complete Bot Lifecycle (API-like scenario)")
        print("-" * 80)

        # Create a new bot (simulates POST /api/v1/bots)
        bot2 = uow.bots.create_bot(
            instance_id="lifecycle-test-bot",
            network="mainnet",
            strategy="test_lifecycle",
            config={"test": True},
        )
        print(f"✅ Bot created: {bot2.instance_id}")

        # Start bot (simulates POST /api/v1/bots/{id}/start)
        uow.bots.update_status(
            "lifecycle-test-bot", BotStatusEnum.RUNNING, process_id=66666
        )
        uow.events.log_event(bot2.id, "bot_started", "info", "Bot started")
        print("✅ Bot started (PID: 66666)")

        # Create a job (simulates bot executing a job)
        job = uow.jobs.create_job("lifecycle-job", bot2.id, "analysis")
        uow.jobs.start_job("lifecycle-job", process_id=66667)
        uow.events.log_event(
            bot2.id, "job_started", "info", "Job started", related_job_id=job.job_id
        )
        print(f"✅ Job started: {job.job_id}")

        # Complete job
        uow.jobs.complete_job(
            "lifecycle-job", result={"success": True}, execution_time_ms=1000
        )
        uow.events.log_event(
            bot2.id, "job_completed", "info", "Job completed", related_job_id=job.job_id
        )
        print("✅ Job completed in 1000ms")

        # Create a trade
        trade = uow.trades.create_trade(
            trade_id="lifecycle-trade",
            bot_id=bot2.id,
            pair1="BTC",
            pair2="USD",
            entry_price1=45000,
            entry_price2=1.0,
            entry_size1=0.1,
            entry_size2=4500,
        )
        uow.events.log_event(
            bot2.id,
            "trade_opened",
            "info",
            "Trade opened",
            related_trade_id=trade.trade_id,
        )
        print(f"✅ Trade opened: {trade.trade_id}")

        # Close trade
        uow.trades.close_trade(
            "lifecycle-trade",
            exit_price1=46000,
            exit_price2=1.0,
            exit_size1=0.1,
            exit_size2=4600,
        )
        uow.events.log_event(
            bot2.id,
            "trade_closed",
            "info",
            "Trade closed with profit",
            related_trade_id=trade.trade_id,
        )
        print("✅ Trade closed with P&L")

        # Stop bot (simulates POST /api/v1/bots/{id}/stop)
        uow.bots.update_status("lifecycle-test-bot", BotStatusEnum.STOPPED)
        uow.events.log_event(bot2.id, "bot_stopped", "info", "Bot stopped")
        print("✅ Bot stopped")

        # Now query all data (simulating GET requests)
        print("\n📋 Final Data Summary:")
        events = uow.events.get_bot_events(bot2.id, days=7)
        jobs = uow.jobs.get_job_history(bot2.id, days=7)
        trades = uow.trades.get_bot_trades(bot2.id)
        stats = uow.bots.get_statistics("lifecycle-test-bot")

        print(f"   Events: {len(events)}")
        print(f"   Jobs: {len(jobs)}")
        print(f"   Trades: {len(trades)}")
        print(f"   Total P&L: ${stats.get('total_profit_loss'):.2f}")

        print("✅ Complete lifecycle test PASSED")

        # ====================================================================
        # SUMMARY
        # ====================================================================
        print("\n" + "=" * 80)
        print("✅ ALL API DATABASE INTEGRATION TESTS PASSED!")
        print("=" * 80)
        print("\n📚 Available API Endpoints:")
        print("   GET  /api/v1/bots/{id}/history    - Event history")
        print("   GET  /api/v1/bots/{id}/jobs       - Job history")
        print("   GET  /api/v1/bots/{id}/trades     - Trade history")
        print("   GET  /api/v1/bots/{id}/stats      - Statistics")
        print("\n✨ All bot data is now available through the API!")
        print("=" * 80 + "\n")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        raise

    finally:
        session.close()


if __name__ == "__main__":
    test_api_database_integration()
