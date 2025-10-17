#!/usr/bin/env python3
"""
Backtest analysis script for dYdX trading bot

Analyzes and compares saved backtest results, generates
performance reports and visualizations.

Usage:
    python scripts/analyze_backtest_results.py
    python scripts/analyze_backtest_results.py --top 5
    python scripts/analyze_backtest_results.py --export results.csv
"""

import argparse
import logging

# Add the app directory to path (following existing script patterns)
import os
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

# Now import app modules
from logging_setup import setup_logging  # noqa: E402
from models.backtest_models import BacktestResult  # noqa: E402
from models.backtest_storage import backtest_storage  # noqa: E402


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Analyze dYdX trading bot backtest results',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--directory',
        default='app/backtest_results',
        help='Directory containing backtest results (default: app/backtest_results)'
    )
    parser.add_argument(
        '--top',
        type=int,
        default=10,
        help='Number of top results to display (default: 10)'
    )
    parser.add_argument(
        '--sort-by',
        choices=['total_pnl', 'total_return_pct', 'sharpe_ratio', 'win_rate'],
        default='total_pnl',
        help='Metric to sort results by (default: total_pnl)'
    )
    parser.add_argument(
        '--export',
        help='Export results to CSV file'
    )
    parser.add_argument(
        '--detailed',
        action='store_true',
        help='Show detailed analysis for each result'
    )
    parser.add_argument(
        '--chart',
        action='store_true',
        help='Generate performance charts (requires matplotlib)'
    )

    return parser.parse_args()


def format_currency(value: float) -> str:
    """Format currency value for display."""
    if value >= 0:
        return f"${value:,.2f}"
    else:
        return f"-${abs(value):,.2f}"


def format_percentage(value: float) -> str:
    """Format percentage value for display."""
    if value >= 0:
        return f"+{value:.1f}%"
    else:
        return f"{value:.1f}%"


def print_summary_table(results: List[BacktestResult], sort_by: str, top_n: int):
    """Print formatted summary table of backtest results."""
    if not results:
        print("📭 No backtest results found.")
        return

    # Sort results
    if sort_by == 'total_pnl':
        results.sort(key=lambda r: r.metrics.total_pnl, reverse=True)
    elif sort_by == 'total_return_pct':
        results.sort(key=lambda r: r.metrics.total_return_pct, reverse=True)
    elif sort_by == 'sharpe_ratio':
        results.sort(key=lambda r: r.metrics.sharpe_ratio, reverse=True)
    elif sort_by == 'win_rate':
        results.sort(key=lambda r: r.metrics.win_rate, reverse=True)

    # Display top results
    display_results = results[:top_n]

    print(f"\n{'='*100}")
    print(
        f"           BACKTEST RESULTS ANALYSIS (Top {len(display_results)} by {sort_by.replace('_', ' ').title()})")
    print(f"{'='*100}")

    # Table header
    header = f"{'#':<3} {'Period':<20} {'Days':<5} {'Trades':<7} {'PnL':<12} {'Return':<9} {'Win Rate':<9} {'Sharpe':<7}"
    print(header)
    print("-" * len(header))

    # Table rows
    for i, result in enumerate(display_results, 1):
        period = f"{result.start_date[:10]} to {result.end_date[:10]}"
        days = result.total_days
        trades = result.metrics.total_trades
        pnl = format_currency(result.metrics.total_pnl)
        return_pct = format_percentage(result.metrics.total_return_pct)
        win_rate = f"{result.metrics.win_rate:.1f}%"
        sharpe = f"{result.metrics.sharpe_ratio:.2f}"

        row = f"{i:<3} {period:<20} {days:<5} {trades:<7} {pnl:<12} {return_pct:<9} {win_rate:<9} {sharpe:<7}"
        print(row)

    print("-" * len(header))


def print_detailed_analysis(results: List[BacktestResult]):
    """Print detailed analysis for each result."""
    print(f"\n{'='*80}")
    print("                    DETAILED ANALYSIS")
    print(f"{'='*80}")

    for i, result in enumerate(results[:5], 1):  # Show top 5 detailed
        print(
            f"\n📊 Result #{i}: {result.start_date[:10]} to {result.end_date[:10]}")
        print("-" * 60)

        metrics = result.metrics

        # Basic performance
        print(f"Total PnL: {format_currency(metrics.total_pnl)}")
        print(f"Total Return: {format_percentage(metrics.total_return_pct)}")
        print(f"Starting Balance: {format_currency(result.starting_balance)}")
        print(f"Ending Balance: {format_currency(result.ending_balance)}")

        # Trade statistics
        print("\nTrade Statistics:")
        print(f"  Total Trades: {metrics.total_trades}")
        print(f"  Winning Trades: {metrics.winning_trades}")
        print(f"  Losing Trades: {metrics.losing_trades}")
        print(f"  Win Rate: {metrics.win_rate:.1f}%")

        # Performance metrics
        print("\nPerformance Metrics:")
        print(f"  Average Win: {format_currency(metrics.avg_win)}")
        print(f"  Average Loss: {format_currency(metrics.avg_loss)}")
        print(f"  Profit Factor: {metrics.profit_factor:.2f}")
        print(f"  Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        print(f"  Calmar Ratio: {metrics.calmar_ratio:.2f}")

        # Risk metrics
        print("\nRisk Metrics:")
        print(f"  Max Drawdown: {format_currency(metrics.max_drawdown)}")
        print(f"  Max Drawdown %: {metrics.max_drawdown_pct:.1f}%")
        print(f"  Max Consecutive Losses: {metrics.max_consecutive_losses}")
        print(
            f"  Avg Trade Duration: {metrics.avg_trade_duration_hours:.1f} hours")

        # Configuration snapshot
        config = result.config_snapshot
        print("\nConfiguration:")
        print(f"  Z-Score Threshold: {config.get('zscore_threshold', 'N/A')}")
        print(f"  USD Per Trade: ${config.get('usd_per_trade', 'N/A')}")
        print(f"  Transaction Fee: {config.get('transaction_fee', 'N/A'):.4f}")
        print(f"  Slippage: {config.get('slippage', 'N/A'):.4f}")


def print_aggregate_statistics(results: List[BacktestResult]):
    """Print aggregate statistics across all results."""
    if len(results) < 2:
        return

    print(f"\n{'='*80}")
    print("                 AGGREGATE STATISTICS")
    print(f"{'='*80}")

    total_pnls = [r.metrics.total_pnl for r in results]
    win_rates = [r.metrics.win_rate for r in results]
    sharpe_ratios = [r.metrics.sharpe_ratio for r in results]
    total_trades = [r.metrics.total_trades for r in results]

    profitable_tests = len([pnl for pnl in total_pnls if pnl > 0])

    print(f"Total Backtests: {len(results)}")
    print(
        f"Profitable Tests: {profitable_tests} ({profitable_tests/len(results)*100:.1f}%)")
    print("")
    print("PnL Statistics:")
    print(f"  Best: {format_currency(max(total_pnls))}")
    print(f"  Worst: {format_currency(min(total_pnls))}")
    print(f"  Average: {format_currency(sum(total_pnls)/len(total_pnls))}")
    print("")
    print("Win Rate Statistics:")
    print(f"  Best: {max(win_rates):.1f}%")
    print(f"  Worst: {min(win_rates):.1f}%")
    print(f"  Average: {sum(win_rates)/len(win_rates):.1f}%")
    print("")
    print("Sharpe Ratio Statistics:")
    print(f"  Best: {max(sharpe_ratios):.2f}")
    print(f"  Worst: {min(sharpe_ratios):.2f}")
    print(f"  Average: {sum(sharpe_ratios)/len(sharpe_ratios):.2f}")
    print("")
    print("Trade Volume Statistics:")
    print(f"  Most Trades: {max(total_trades)}")
    print(f"  Fewest Trades: {min(total_trades)}")
    print(f"  Average Trades: {sum(total_trades)/len(total_trades):.1f}")


def export_to_csv(results: List[BacktestResult], filename: str):
    """Export results to CSV file."""
    import csv

    try:
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = [
                'start_date', 'end_date', 'total_days', 'starting_balance', 'ending_balance',
                'total_pnl', 'total_return_pct', 'total_trades', 'winning_trades', 'losing_trades',
                'win_rate', 'avg_win', 'avg_loss', 'profit_factor', 'max_drawdown',
                'max_drawdown_pct', 'sharpe_ratio', 'calmar_ratio', 'max_consecutive_losses',
                'avg_trade_duration_hours', 'zscore_threshold', 'usd_per_trade', 'analysis_timestamp'
            ]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                row = {
                    'start_date': result.start_date,
                    'end_date': result.end_date,
                    'total_days': result.total_days,
                    'starting_balance': result.starting_balance,
                    'ending_balance': result.ending_balance,
                    'total_pnl': result.metrics.total_pnl,
                    'total_return_pct': result.metrics.total_return_pct,
                    'total_trades': result.metrics.total_trades,
                    'winning_trades': result.metrics.winning_trades,
                    'losing_trades': result.metrics.losing_trades,
                    'win_rate': result.metrics.win_rate,
                    'avg_win': result.metrics.avg_win,
                    'avg_loss': result.metrics.avg_loss,
                    'profit_factor': result.metrics.profit_factor,
                    'max_drawdown': result.metrics.max_drawdown,
                    'max_drawdown_pct': result.metrics.max_drawdown_pct,
                    'sharpe_ratio': result.metrics.sharpe_ratio,
                    'calmar_ratio': result.metrics.calmar_ratio,
                    'max_consecutive_losses': result.metrics.max_consecutive_losses,
                    'avg_trade_duration_hours': result.metrics.avg_trade_duration_hours,
                    'zscore_threshold': result.config_snapshot.get('zscore_threshold'),
                    'usd_per_trade': result.config_snapshot.get('usd_per_trade'),
                    'analysis_timestamp': result.analysis_timestamp
                }
                writer.writerow(row)

        print(f"✅ Results exported to: {filename}")

    except Exception as e:
        print(f"❌ Failed to export CSV: {e}")


def generate_charts(results: List[BacktestResult]):
    """Generate performance charts using matplotlib."""
    try:
        from datetime import datetime

        import matplotlib.pyplot as plt

        if len(results) < 2:
            print("⚠️  Need at least 2 results to generate meaningful charts")
            return

        # Sort by date
        results.sort(key=lambda r: r.analysis_timestamp)

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('dYdX Trading Bot Backtest Analysis', fontsize=16)

        # Chart 1: PnL over time
        timestamps = [datetime.fromisoformat(r.analysis_timestamp.replace('Z', '+00:00'))
                      for r in results]
        pnls = [r.metrics.total_pnl for r in results]

        ax1.plot(timestamps, pnls, marker='o', linewidth=2)
        ax1.set_title('Total PnL by Backtest')
        ax1.set_ylabel('PnL ($)')
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis='x', rotation=45)

        # Chart 2: Win Rate distribution
        win_rates = [r.metrics.win_rate for r in results]
        ax2.hist(win_rates, bins=min(10, len(results)//2 + 1),
                 alpha=0.7, edgecolor='black')
        ax2.set_title('Win Rate Distribution')
        ax2.set_xlabel('Win Rate (%)')
        ax2.set_ylabel('Frequency')
        ax2.grid(True, alpha=0.3)

        # Chart 3: Sharpe Ratio vs PnL scatter
        sharpe_ratios = [r.metrics.sharpe_ratio for r in results]
        ax3.scatter(sharpe_ratios, pnls, alpha=0.7, s=60)
        ax3.set_title('Sharpe Ratio vs Total PnL')
        ax3.set_xlabel('Sharpe Ratio')
        ax3.set_ylabel('Total PnL ($)')
        ax3.grid(True, alpha=0.3)

        # Chart 4: Trade count vs PnL
        trade_counts = [r.metrics.total_trades for r in results]
        ax4.scatter(trade_counts, pnls, alpha=0.7, s=60)
        ax4.set_title('Trade Count vs Total PnL')
        ax4.set_xlabel('Total Trades')
        ax4.set_ylabel('Total PnL ($)')
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()

        # Save chart
        chart_filename = f"backtest_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        chart_path = Path("app/backtest_results") / chart_filename
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')

        print(f"📈 Charts saved to: {chart_path}")

        # Optionally display chart
        # plt.show()

    except ImportError:
        print("📊 Charts require matplotlib. Install with: pip install matplotlib")
    except Exception as e:
        print(f"❌ Failed to generate charts: {e}")


def main():
    """Main analysis function."""
    args = parse_arguments()

    # Initialize logging
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        # Check if results directory exists
        results_dir = Path(args.directory)
        if not results_dir.exists():
            print(f"❌ Results directory not found: {args.directory}")
            print("💡 Run a backtest first: make backtest-quick")
            sys.exit(1)

        # Load all backtest results
        print("📊 Loading backtest results...")
        result_files = backtest_storage.list_backtest_results()

        if not result_files:
            print(f"📭 No backtest results found in {args.directory}")
            print("💡 Run a backtest first: make backtest-quick")
            sys.exit(1)

        # Load full result objects
        results = []
        for result_info in result_files:
            result = backtest_storage.load_backtest_result(
                result_info['filename'])
            if result:
                results.append(result)

        print(f"✅ Loaded {len(results)} backtest results")

        # Print summary table
        print_summary_table(results, args.sort_by, args.top)

        # Print aggregate statistics
        print_aggregate_statistics(results)

        # Print detailed analysis if requested
        if args.detailed:
            print_detailed_analysis(results)

        # Export to CSV if requested
        if args.export:
            export_to_csv(results, args.export)

        # Generate charts if requested
        if args.chart:
            generate_charts(results)

        # Storage info
        storage_info = backtest_storage.get_storage_info()
        print("\n📁 Storage Info:")
        print(f"   Directory: {storage_info['storage_directory']}")
        print(f"   Total Size: {storage_info['total_size_kb']:.1f} KB")
        print(f"   Best PnL: {format_currency(storage_info['best_pnl'])}")
        print(f"   Worst PnL: {format_currency(storage_info['worst_pnl'])}")

        logger.info("Analysis completed successfully")

    except Exception as e:
        logger.error("Analysis failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
