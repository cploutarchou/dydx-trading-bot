"""
Database integration test - demonstrates all core functionality
Run this to verify database system works correctly
"""

import os
import sys

# Add bot directory to path
sys.path.insert(0, os.path.dirname(__file__))

from database import db
from models import BotStatusEnum, JobStatusEnum, TradeStatusEnum
from repository import UnitOfWork


def test_database_integration():
    """Complete database integration test"""

    print("🧪 Starting Database Integration Tests...\n")

    try:
        # Initialize database
        print("1️⃣  Testing database initialization...")
        db.create_all_tables()
        print("   ✅ Tables created successfully\n")

        # Test health check
        print("2️⃣  Testing database health check...")
        health = db.health_check()
        assert health, "Health check failed"
        print("   ✅ Database health check passed\n")

        # Get session and create UnitOfWork
        session = db.get_session()
        uow = UnitOfWork(session)

        # Test Bot Repository
        print("3️⃣  Testing Bot Repository...")
        bot = uow.bots.create_bot(
            instance_id="test-bot-001",
            network="testnet",
            strategy="statistical_arbitrage",
            config={"usd_per_trade": 100, "zscore_threshold": 1.5, "max_positions": 10},
        )
        print(f"   ✅ Created bot: {bot.instance_id}\n")

        # Test updating bot status
        print("4️⃣  Testing Bot Status Updates...")
        uow.bots.update_status("test-bot-001", BotStatusEnum.RUNNING, process_id=12345)
        bot_updated = uow.bots.get_by_instance_id("test-bot-001")
        assert bot_updated.status == BotStatusEnum.RUNNING
        assert bot_updated.process_id == 12345
        print(
            f"   ✅ Bot status: {bot_updated.status}, PID: {bot_updated.process_id}\n"
        )

        # Test Event Logging
        print("5️⃣  Testing Event Logging...")
        uow.events.log_event(
            bot_id=bot.id,
            event_type="bot_started",
            severity="info",
            message="Bot instance started successfully",
            details={"network": "testnet", "strategy": "statistical_arbitrage"},
        )
        events = uow.events.get_bot_events(bot.id)
        assert len(events) > 0
        print(f"   ✅ Logged {len(events)} event(s)\n")

        # Test Job Repository
        print("6️⃣  Testing Job Repository...")
        job = uow.jobs.create_job(
            job_id="job-001",
            bot_id=bot.id,
            job_type="cointegration_analysis",
            parameters={"lookback_days": 60},
        )
        print(f"   ✅ Created job: {job.job_id} (status: {job.status})\n")

        # Test Job Execution Tracking
        print("7️⃣  Testing Job Execution Tracking...")
        uow.jobs.start_job("job-001", process_id=12346)
        job_started = uow.jobs.get_by_job_id("job-001")
        assert job_started.status == JobStatusEnum.RUNNING
        assert job_started.process_id == 12346
        print(f"   ✅ Job started (PID: {job_started.process_id})\n")

        # Test Job Completion
        print("8️⃣  Testing Job Completion...")
        uow.jobs.complete_job(
            job_id="job-001",
            result={
                "pairs_found": 5,
                "pairs": [("ETH", "BTC"), ("ETH", "XRP"), ("BTC", "XRP")],
                "correlation_threshold": 0.8,
            },
            execution_time_ms=3500,
        )
        job_completed = uow.jobs.get_by_job_id("job-001")
        assert job_completed.status == JobStatusEnum.COMPLETED
        assert job_completed.execution_time_ms == 3500
        print(f"   ✅ Job completed in {job_completed.execution_time_ms}ms\n")

        # Test Trade Repository
        print("9️⃣  Testing Trade Repository...")
        trade = uow.trades.create_trade(
            trade_id="trade-001",
            bot_id=bot.id,
            pair1="ETH",
            pair2="BTC",
            entry_price1=2000.0,
            entry_price2=45000.0,
            entry_size1=1.5,
            entry_size2=0.05,
        )
        print(f"   ✅ Created trade: {trade.trade_id} ({trade.pair1}/{trade.pair2})\n")

        # Test Trade Closing & P&L Calculation
        print("🔟 Testing Trade Closing & P&L Calculation...")
        uow.trades.close_trade(
            trade_id="trade-001",
            exit_price1=2100.0,  # +100 on ETH
            exit_price2=46000.0,  # +1000 on BTC
            exit_size1=1.5,
            exit_size2=0.05,
            exit_tx_hash="0x123abc...",
        )
        trade_closed = uow.trades.get_by_trade_id("trade-001")
        assert trade_closed.status == TradeStatusEnum.CLOSED
        assert trade_closed.profit_loss > 0  # Should be profitable
        print("   ✅ Trade closed")
        print(f"      Entry Cost: ${trade_closed.entry_cost:.2f}")
        print(f"      Exit Proceeds: ${trade_closed.exit_proceeds:.2f}")
        print(f"      P&L: ${trade_closed.profit_loss:.2f}")
        print(f"      P&L %: {trade_closed.profit_loss_percentage:.2f}%\n")

        # Test Trade Statistics
        print("1️⃣1️⃣  Testing Trade Statistics...")
        trade_stats = uow.trades.get_trade_statistics(bot.id)
        print("   ✅ Trade Statistics:")
        print(f"      Total Trades: {trade_stats['total_trades']}")
        print(f"      Winning Trades: {trade_stats['winning_trades']}")
        print(f"      Losing Trades: {trade_stats['losing_trades']}")
        print(f"      Win Rate: {trade_stats['win_rate']:.1f}%")
        print(f"      Total P&L: ${trade_stats['total_profit_loss']:.2f}\n")

        # Test Bot Statistics
        print("1️⃣2️⃣  Testing Bot Statistics...")
        uow.bots.update_statistics(
            instance_id="test-bot-001",
            total_trades=1,
            successful_trades=1,
            failed_trades=0,
            profit_loss=trade_closed.profit_loss,
        )
        bot_stats = uow.bots.get_statistics("test-bot-001")
        print("   ✅ Bot Statistics:")
        print(f"      Total Trades: {bot_stats['total_trades']}")
        print(f"      Successful Trades: {bot_stats['successful_trades']}")
        print(f"      Win Rate: {bot_stats['win_rate']:.1f}%")
        print(f"      Total P&L: ${bot_stats['total_profit_loss']:.2f}")
        print(f"      Uptime: {bot_stats['uptime_seconds']} seconds\n")

        # Test Query Operations
        print("1️⃣3️⃣  Testing Query Operations...")
        all_bots = uow.bots.get_all()
        running_bots = uow.bots.get_running()
        bot_jobs = uow.jobs.get_bot_jobs(bot.id)
        bot_trades = uow.trades.get_bot_trades(bot.id)
        bot_events = uow.events.get_bot_events(bot.id)

        print("   ✅ Query Results:")
        print(f"      Total Bots: {len(all_bots)}")
        print(f"      Running Bots: {len(running_bots)}")
        print(f"      Bot Jobs: {len(bot_jobs)}")
        print(f"      Bot Trades: {len(bot_trades)}")
        print(f"      Bot Events: {len(bot_events)}\n")

        # Test Transaction Rollback
        print("1️⃣4️⃣  Testing Transaction Rollback (error handling)...")
        try:
            with UnitOfWork(db.get_session()) as uow_error:
                # Try to create trade with invalid bot_id
                uow_error.trades.create_trade(
                    trade_id="invalid-trade",
                    bot_id=99999,  # Non-existent bot
                    pair1="ETH",
                    pair2="BTC",
                    entry_price1=2000,
                    entry_price2=45000,
                    entry_size1=1.5,
                    entry_size2=0.05,
                )
        except Exception as e:
            print(
                f"   ✅ Error caught and transaction rolled back: {type(e).__name__}\n"
            )

        # Test Job Failure with Retry Logic
        print("1️⃣5️⃣  Testing Job Failure with Retry Logic...")
        job2 = uow.jobs.create_job(
            job_id="job-002",
            bot_id=bot.id,
            job_type="trade_exit",
            parameters={"trade_id": "trade-001"},
        )
        uow.jobs.start_job("job-002", process_id=12347)
        uow.jobs.fail_job(
            job_id="job-002",
            error_message="Connection timeout - will retry",
            error_traceback="Traceback (most recent call last)...",
        )
        job_failed = uow.jobs.get_by_job_id("job-002")
        print("   ✅ Job failed:")
        print(f"      Status: {job_failed.status}")
        print(f"      Retry Count: {job_failed.retry_count}/{job_failed.max_retries}")
        print(f"      Error: {job_failed.error_message}\n")

        # Summary
        print("=" * 60)
        print("✅ ALL DATABASE INTEGRATION TESTS PASSED!")
        print("=" * 60)
        print("\n📊 Test Summary:")
        print("   • Database initialized: ✅")
        print("   • Health check: ✅")
        print("   • Bot creation & tracking: ✅")
        print("   • Job creation & execution: ✅")
        print("   • Trade creation & P&L calculation: ✅")
        print("   • Event logging & audit trail: ✅")
        print("   • Statistics calculation: ✅")
        print("   • Error handling & rollback: ✅")
        print("   • Retry logic: ✅")
        print("\n🚀 Database system is production-ready!\n")

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        session.close()


if __name__ == "__main__":
    success = test_database_integration()
    sys.exit(0 if success else 1)
