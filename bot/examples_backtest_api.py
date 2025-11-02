"""
Backtest API Usage Examples
Demonstrates how to use the new backtesting API endpoints
"""

import time

import requests


class BacktestAPIClient:
    """Client for interacting with the backtest API"""

    def __init__(self, base_url="http://localhost:8889", token=None):
        self.base_url = base_url
        self.token = token

    def _get_headers(self):
        """Get headers with Bearer token"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def login(self, username="admin", password="admin123"):
        """Login and store JWT token"""
        response = requests.post(
            f"{self.base_url}/auth/login",
            json={"username": username, "password": password},
        )

        if response.status_code == 200:
            data = response.json()["data"]
            self.token = data["access_token"]
            print(f"✅ Logged in as {data['user']['username']}")
            return True
        else:
            print(f"❌ Login failed: {response.text}")
            return False

    def create_backtest(self, config):
        """Create and start a new backtest"""
        response = requests.post(
            f"{self.base_url}/api/v1/backtests",
            json=config,
            headers=self._get_headers(),
        )

        if response.status_code == 200:
            return response.json()["data"]
        else:
            print(f"❌ Failed to create backtest: {response.text}")
            return None

    def get_backtest_status(self, run_id):
        """Get backtest status and progress"""
        response = requests.get(
            f"{self.base_url}/api/v1/backtests/{run_id}/status",
            headers=self._get_headers(),
        )

        if response.status_code == 200:
            return response.json()["data"]
        else:
            print(f"❌ Failed to get status: {response.text}")
            return None

    def get_backtest_details(self, run_id):
        """Get detailed backtest results"""
        response = requests.get(
            f"{self.base_url}/api/v1/backtests/{run_id}", headers=self._get_headers()
        )

        if response.status_code == 200:
            return response.json()["data"]
        else:
            print(f"❌ Failed to get details: {response.text}")
            return None

    def list_backtests(self, limit=10):
        """List recent backtests"""
        response = requests.get(
            f"{self.base_url}/api/v1/backtests?limit={limit}",
            headers=self._get_headers(),
        )

        if response.status_code == 200:
            return response.json()["data"]["runs"]
        else:
            print(f"❌ Failed to list backtests: {response.text}")
            return []

    def get_backtest_trades(self, run_id, limit=20):
        """Get trades for specific backtest"""
        response = requests.get(
            f"{self.base_url}/api/v1/backtests/{run_id}/trades?limit={limit}",
            headers=self._get_headers(),
        )

        if response.status_code == 200:
            return response.json()["data"]["trades"]
        else:
            print(f"❌ Failed to get trades: {response.text}")
            return []

    def cancel_backtest(self, run_id):
        """Cancel running backtest"""
        response = requests.post(
            f"{self.base_url}/api/v1/backtests/{run_id}/cancel",
            headers=self._get_headers(),
        )

        return response.status_code == 200


def example_1_basic_backtest():
    """Example 1: Basic backtest creation and monitoring"""

    print("🚀 Example 1: Basic Backtest Creation")
    print("=" * 50)

    # Initialize client and login
    client = BacktestAPIClient()
    if not client.login():
        return

    # Define backtest configuration
    config = {
        "name": "Conservative BTC-ETH Strategy",
        "start_date": "2024-09-01",
        "end_date": "2024-10-31",
        "strategy_params": {
            "zscore_threshold": 2.0,
            "usd_per_trade": 25.0,
            "close_at_zscore_cross": True,
            "stats_window": 21,
        },
        "max_pairs": 3,
        "starting_balance": 1000.0,
    }

    # Create backtest
    print("\n📊 Creating backtest...")
    result = client.create_backtest(config)
    if not result:
        return

    run_id = result["run_id"]
    print(f"✅ Backtest created: {run_id}")
    print(f"   Name: {result['name']}")
    print(f"   Status: {result['status']}")

    # Monitor progress
    print("\n⏳ Monitoring progress...")
    while True:
        status = client.get_backtest_status(run_id)
        if not status:
            break

        print(
            f"   Status: {status['status']:<10} "
            f"Progress: {status.get('progress_pct', 0):.1f}% "
            f"ETA: {status.get('eta_seconds', 0)}s"
        )

        if status["status"] in ["completed", "failed", "cancelled"]:
            break

        time.sleep(5)  # Check every 5 seconds

    # Get final results
    if status and status["status"] == "completed":
        details = client.get_backtest_details(run_id)
        if details:
            print("\n📈 Backtest Results:")
            print(f"   Total P&L: ${details['total_pnl']:.2f}")
            print(f"   Win Rate: {details['win_rate']:.1%}")
            print(f"   Total Trades: {details['total_trades']}")
            print(f"   Sharpe Ratio: {details['sharpe_ratio']:.2f}")

            # Show recent trades
            trades = client.get_backtest_trades(run_id, limit=5)
            if trades:
                print("\n💰 Recent Trades:")
                for trade in trades[:3]:
                    pnl = trade.get("pnl", 0)
                    status_emoji = "✅" if pnl > 0 else "❌"
                    print(
                        f"   {status_emoji} {trade['market_1']}/{trade['market_2']}: ${pnl:.2f}"
                    )
    else:
        status_msg = status["status"] if status else "unknown"
        print(f"\n❌ Backtest failed with status: {status_msg}")

    print("\n" + "=" * 50)


def example_2_strategy_comparison():
    """Example 2: Compare multiple strategies"""

    print("🚀 Example 2: Strategy Comparison")
    print("=" * 50)

    client = BacktestAPIClient()
    if not client.login():
        return

    # Define multiple strategies to test
    strategies = [
        {
            "name": "Conservative Strategy (Z=2.0)",
            "strategy_params": {
                "zscore_threshold": 2.0,
                "usd_per_trade": 50.0,
                "stats_window": 30,
            },
        },
        {
            "name": "Aggressive Strategy (Z=1.0)",
            "strategy_params": {
                "zscore_threshold": 1.0,
                "usd_per_trade": 50.0,
                "stats_window": 15,
            },
        },
        {
            "name": "Balanced Strategy (Z=1.5)",
            "strategy_params": {
                "zscore_threshold": 1.5,
                "usd_per_trade": 50.0,
                "stats_window": 21,
            },
        },
    ]

    backtest_runs = []

    # Start all backtests
    print("\n📊 Starting multiple backtests...")
    for strategy in strategies:
        config = {
            "name": strategy["name"],
            "start_date": "2024-09-01",
            "end_date": "2024-09-30",  # Shorter period for comparison
            "strategy_params": strategy["strategy_params"],
            "max_pairs": 5,
            "starting_balance": 1000.0,
        }

        result = client.create_backtest(config)
        if result:
            backtest_runs.append({"run_id": result["run_id"], "name": strategy["name"]})
            print(f"✅ Started: {strategy['name']} ({result['run_id']})")
        else:
            print(f"❌ Failed: {strategy['name']}")

    # Wait for all to complete
    print("\n⏳ Waiting for backtests to complete...")
    completed_results = []

    while backtest_runs:
        for i, run in enumerate(
            backtest_runs[:]
        ):  # Copy list to avoid modification issues
            status = client.get_backtest_status(run["run_id"])
            if not status:
                backtest_runs.remove(run)
                continue

            if status["status"] == "completed":
                details = client.get_backtest_details(run["run_id"])
                if details:
                    completed_results.append(
                        {
                            "name": run["name"],
                            "total_pnl": details["total_pnl"],
                            "win_rate": details["win_rate"],
                            "total_trades": details["total_trades"],
                            "sharpe_ratio": details["sharpe_ratio"],
                        }
                    )
                backtest_runs.remove(run)
            elif status["status"] in ["failed", "cancelled"]:
                print(f"❌ {run['name']} failed")
                backtest_runs.remove(run)

        if backtest_runs:
            time.sleep(10)  # Check every 10 seconds

    # Display comparison results
    if completed_results:
        print("\n📊 Strategy Comparison Results:")
        print("-" * 80)
        print(
            f"{'Strategy':<30} {'P&L':<10} {'Win Rate':<10} {'Trades':<8} {'Sharpe':<8}"
        )
        print("-" * 80)

        for result in sorted(
            completed_results, key=lambda x: x["total_pnl"], reverse=True
        ):
            print(
                f"{result['name']:<30} "
                f"${result['total_pnl']:>8.2f} "
                f"{result['win_rate']:>8.1%} "
                f"{result['total_trades']:>7} "
                f"{result['sharpe_ratio']:>7.2f}"
            )

        # Find best strategy
        best = max(completed_results, key=lambda x: x["total_pnl"])
        print(f"\n🏆 Best Strategy: {best['name']} (${best['total_pnl']:.2f} P&L)")

    print("\n" + "=" * 50)


def example_3_backtest_management():
    """Example 3: Backtest management operations"""

    print("🚀 Example 3: Backtest Management")
    print("=" * 50)

    client = BacktestAPIClient()
    if not client.login():
        return

    # List existing backtests
    print("\n📋 Listing recent backtests...")
    recent_runs = client.list_backtests(limit=5)

    if recent_runs:
        print(f"Found {len(recent_runs)} recent backtests:")
        for run in recent_runs:
            status_emoji = {
                "completed": "✅",
                "failed": "❌",
                "running": "⏳",
                "cancelled": "🚫",
            }.get(run["status"], "❓")
            pnl_str = f"${run['total_pnl']:.2f}" if run.get("total_pnl") else "N/A"
            print(
                f"   {status_emoji} {run['name']:<25} {run['status']:<10} P&L: {pnl_str}"
            )
    else:
        print("No recent backtests found")

    # Get detailed analysis of most recent completed backtest
    completed_runs = [r for r in recent_runs if r["status"] == "completed"]
    if completed_runs:
        latest = completed_runs[0]
        print(f"\n🔍 Detailed Analysis: {latest['name']}")

        details = client.get_backtest_details(latest["run_id"])
        if details:
            print(
                f"   Period: {details['start_date'][:10]} to {details['end_date'][:10]}"
            )
            print(f"   Total P&L: ${details['total_pnl']:.2f}")
            print(f"   Return %: {details['total_return_pct']:.2f}%")
            print(f"   Win Rate: {details['win_rate']:.1%}")
            print(f"   Max Drawdown: {details['max_drawdown_pct']:.2f}%")

            # Show trade distribution
            trades = client.get_backtest_trades(latest["run_id"], limit=100)
            if trades:
                winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
                losing_trades = [t for t in trades if t.get("pnl", 0) <= 0]

                print("\n📊 Trade Analysis:")
                print(f"   Total Trades: {len(trades)}")
                print(
                    f"   Winning: {len(winning_trades)} ({len(winning_trades) / len(trades):.1%})"
                )
                print(
                    f"   Losing: {len(losing_trades)} ({len(losing_trades) / len(trades):.1%})"
                )

                if winning_trades:
                    avg_win = sum(t.get("pnl", 0) for t in winning_trades) / len(
                        winning_trades
                    )
                    print(f"   Avg Win: ${avg_win:.2f}")

                if losing_trades:
                    avg_loss = sum(t.get("pnl", 0) for t in losing_trades) / len(
                        losing_trades
                    )
                    print(f"   Avg Loss: ${avg_loss:.2f}")

    print("\n" + "=" * 50)


def example_4_parameter_optimization():
    """Example 4: Parameter optimization example"""

    print("🚀 Example 4: Parameter Optimization")
    print("=" * 50)

    client = BacktestAPIClient()
    if not client.login():
        return

    # Test different Z-score thresholds
    z_thresholds = [1.0, 1.2, 1.5, 1.8, 2.0, 2.5]
    optimization_results = []

    print(f"\n🔧 Testing {len(z_thresholds)} Z-score thresholds...")

    for z_threshold in z_thresholds:
        config = {
            "name": f"Optimization Z={z_threshold}",
            "start_date": "2024-09-15",
            "end_date": "2024-10-15",  # 1 month test
            "strategy_params": {
                "zscore_threshold": z_threshold,
                "usd_per_trade": 100.0,
                "stats_window": 21,
                "close_at_zscore_cross": True,
            },
            "max_pairs": 10,
            "starting_balance": 1000.0,
        }

        result = client.create_backtest(config)
        if result:
            optimization_results.append(
                {
                    "run_id": result["run_id"],
                    "z_threshold": z_threshold,
                    "name": config["name"],
                }
            )
            print(f"✅ Started Z={z_threshold}")
        else:
            print(f"❌ Failed Z={z_threshold}")

    # Wait and collect results
    print("\n⏳ Running optimization backtests...")
    final_results = []

    # Simple polling approach (in production, use WebSocket for real-time updates)
    max_wait_time = 600  # 10 minutes max
    start_time = time.time()

    while optimization_results and (time.time() - start_time) < max_wait_time:
        for result in optimization_results[:]:
            status = client.get_backtest_status(result["run_id"])
            if not status:
                optimization_results.remove(result)
                continue

            if status["status"] == "completed":
                details = client.get_backtest_details(result["run_id"])
                if details:
                    final_results.append(
                        {
                            "z_threshold": result["z_threshold"],
                            "total_pnl": details["total_pnl"],
                            "win_rate": details["win_rate"],
                            "total_trades": details["total_trades"],
                            "sharpe_ratio": details["sharpe_ratio"],
                            "max_drawdown_pct": details["max_drawdown_pct"],
                        }
                    )
                optimization_results.remove(result)
            elif status["status"] in ["failed", "cancelled"]:
                print(f"❌ Failed: Z={result['z_threshold']}")
                optimization_results.remove(result)

        if optimization_results:
            remaining = len(optimization_results)
            print(f"   {remaining} backtests still running...")
            time.sleep(15)

    # Display optimization results
    if final_results:
        print("\n📊 Parameter Optimization Results:")
        print("-" * 70)
        print(
            f"{'Z-Score':<8} {'P&L':<10} {'Win Rate':<10} {'Trades':<8} {'Sharpe':<8} {'Drawdown':<10}"
        )
        print("-" * 70)

        for result in sorted(final_results, key=lambda x: x["total_pnl"], reverse=True):
            print(
                f"{result['z_threshold']:<8.1f} "
                f"${result['total_pnl']:>8.2f} "
                f"{result['win_rate']:>8.1%} "
                f"{result['total_trades']:>7} "
                f"{result['sharpe_ratio']:>7.2f} "
                f"{result['max_drawdown_pct']:>8.2f}%"
            )

        # Find optimal parameter
        best = max(final_results, key=lambda x: x["total_pnl"])
        print(
            f"\n🎯 Optimal Z-Score: {best['z_threshold']} (${best['total_pnl']:.2f} P&L)"
        )
    else:
        print("❌ No optimization results available")

    print("\n" + "=" * 50)


def main():
    """Run all examples"""

    print("🤖 dYdX Trading Bot - Backtest API Examples")
    print("=" * 60)
    print("This script demonstrates the new backtesting API functionality")
    print("Make sure the bot API server is running on localhost:8889")
    print("=" * 60)

    # Check if API server is available
    try:
        response = requests.get("http://localhost:8889/health", timeout=5)
        if response.status_code == 200:
            print("✅ API Server is running")
        else:
            print("❌ API Server is not responding correctly")
            return
    except requests.exceptions.RequestException:
        print("❌ API Server is not available at localhost:8889")
        print("   Please start the server with: python start_api.py")
        return

    print("\nSelect an example to run:")
    print("1. Basic Backtest Creation")
    print("2. Strategy Comparison")
    print("3. Backtest Management")
    print("4. Parameter Optimization")
    print("0. Run all examples")

    choice = input("\nEnter your choice (0-4): ").strip()

    examples = {
        "1": example_1_basic_backtest,
        "2": example_2_strategy_comparison,
        "3": example_3_backtest_management,
        "4": example_4_parameter_optimization,
    }

    if choice == "0":
        for example_func in examples.values():
            try:
                example_func()
                time.sleep(2)  # Brief pause between examples
            except KeyboardInterrupt:
                print("\n🛑 Interrupted by user")
                break
            except Exception as e:
                print(f"❌ Example failed: {e}")
    elif choice in examples:
        try:
            examples[choice]()
        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user")
        except Exception as e:
            print(f"❌ Example failed: {e}")
    else:
        print("❌ Invalid choice")

    print("\n🎉 Examples completed!")


if __name__ == "__main__":
    main()
