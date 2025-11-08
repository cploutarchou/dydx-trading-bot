"""
Backtest result models for the backtesting engine

These models define the data structures returned by backtest operations,
following the established patterns from the trading bot system.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class BacktestTrade:
    """Individual trade record from backtest execution"""

    trade_id: str
    market_1: str
    market_2: str
    timestamp: str  # ISO format entry timestamp
    entry_price_1: float
    entry_price_2: float
    z_score_entry: float
    side_1: str  # BUY/SELL
    side_2: str  # BUY/SELL
    size_1: float
    size_2: float
    hedge_ratio: float

    # Exit details (optional for open positions)
    exit_timestamp: Optional[str] = None
    exit_price_1: Optional[float] = None
    exit_price_2: Optional[float] = None
    z_score_exit: Optional[float] = None

    # Performance metrics
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    duration_hours: Optional[float] = None

    # Strategy context
    strategy_zscore_threshold: Optional[float] = None


@dataclass
class BacktestMetrics:
    """Performance metrics calculated from backtest results"""

    # Basic P&L
    total_pnl: float
    total_return_pct: float

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float  # Percentage (0-1)

    # Risk metrics
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None  # Absolute value
    max_drawdown_pct: Optional[float] = None  # Percentage
    profit_factor: Optional[float] = None  # Gross profit / Gross loss

    # Additional statistics
    average_win: Optional[float] = None
    average_loss: Optional[float] = None
    largest_win: Optional[float] = None
    largest_loss: Optional[float] = None

    # Time-based metrics
    total_time_in_market: Optional[float] = None  # Hours
    average_trade_duration: Optional[float] = None  # Hours


@dataclass
class BacktestResult:
    """Complete backtest execution result"""

    # Basic info
    run_id: str
    start_date: datetime
    end_date: datetime

    # Balance tracking
    starting_balance: float
    ending_balance: float

    # Performance metrics
    metrics: BacktestMetrics

    # Trade history
    trades: List[BacktestTrade]

    # Strategy parameters used
    strategy_params: dict

    # Execution metadata
    total_pairs_analyzed: Optional[int] = None
    execution_time_seconds: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "run_id": self.run_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "starting_balance": self.starting_balance,
            "ending_balance": self.ending_balance,
            "metrics": {
                "total_pnl": self.metrics.total_pnl,
                "total_return_pct": self.metrics.total_return_pct,
                "total_trades": self.metrics.total_trades,
                "winning_trades": self.metrics.winning_trades,
                "losing_trades": self.metrics.losing_trades,
                "win_rate": self.metrics.win_rate,
                "sharpe_ratio": self.metrics.sharpe_ratio,
                "max_drawdown": self.metrics.max_drawdown,
                "max_drawdown_pct": self.metrics.max_drawdown_pct,
                "profit_factor": self.metrics.profit_factor,
                "average_win": self.metrics.average_win,
                "average_loss": self.metrics.average_loss,
                "largest_win": self.metrics.largest_win,
                "largest_loss": self.metrics.largest_loss,
                "total_time_in_market": self.metrics.total_time_in_market,
                "average_trade_duration": self.metrics.average_trade_duration,
            },
            "trades": [
                {
                    "trade_id": trade.trade_id,
                    "market_1": trade.market_1,
                    "market_2": trade.market_2,
                    "timestamp": trade.timestamp,
                    "entry_price_1": trade.entry_price_1,
                    "entry_price_2": trade.entry_price_2,
                    "z_score_entry": trade.z_score_entry,
                    "side_1": trade.side_1,
                    "side_2": trade.side_2,
                    "size_1": trade.size_1,
                    "size_2": trade.size_2,
                    "hedge_ratio": trade.hedge_ratio,
                    "exit_timestamp": trade.exit_timestamp,
                    "exit_price_1": trade.exit_price_1,
                    "exit_price_2": trade.exit_price_2,
                    "z_score_exit": trade.z_score_exit,
                    "pnl": trade.pnl,
                    "pnl_pct": trade.pnl_pct,
                    "duration_hours": trade.duration_hours,
                    "strategy_zscore_threshold": trade.strategy_zscore_threshold,
                }
                for trade in self.trades
            ],
            "strategy_params": self.strategy_params,
            "total_pairs_analyzed": self.total_pairs_analyzed,
            "execution_time_seconds": self.execution_time_seconds,
        }


def calculate_backtest_metrics(
    trades: List[BacktestTrade], starting_balance: float, ending_balance: float
) -> BacktestMetrics:
    """
    Calculate performance metrics from trade history

    Args:
        trades: List of completed trades
        starting_balance: Initial account balance
        ending_balance: Final account balance

    Returns:
        BacktestMetrics with calculated performance statistics
    """
    if not trades:
        return BacktestMetrics(
            total_pnl=0.0,
            total_return_pct=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
        )

    # Filter to completed trades only
    completed_trades = [t for t in trades if t.pnl is not None]

    if not completed_trades:
        return BacktestMetrics(
            total_pnl=0.0,
            total_return_pct=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
        )

    # Basic calculations - filter out None values
    valid_pnls = [trade.pnl for trade in completed_trades if trade.pnl is not None]
    total_pnl = sum(valid_pnls) if valid_pnls else 0.0
    total_return_pct = ((ending_balance - starting_balance) / starting_balance) * 100

    winning_trades = [t for t in completed_trades if t.pnl is not None and t.pnl > 0]
    losing_trades = [t for t in completed_trades if t.pnl is not None and t.pnl <= 0]

    win_rate = len(winning_trades) / len(completed_trades) if completed_trades else 0.0

    # Calculate additional metrics
    winning_pnls = [t.pnl for t in winning_trades if t.pnl is not None]
    losing_pnls = [t.pnl for t in losing_trades if t.pnl is not None]

    average_win = sum(winning_pnls) / len(winning_pnls) if winning_pnls else 0.0
    average_loss = sum(losing_pnls) / len(losing_pnls) if losing_pnls else 0.0

    largest_win = max(winning_pnls, default=0.0)
    largest_loss = min(losing_pnls, default=0.0)

    # Profit factor: gross profit / gross loss
    gross_profit = sum(winning_pnls) if winning_pnls else 0.0
    gross_loss = abs(sum(losing_pnls)) if losing_pnls else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    # Time-based metrics
    durations = [
        t.duration_hours for t in completed_trades if t.duration_hours is not None
    ]
    total_time_in_market = sum(durations) if durations else None
    average_trade_duration = sum(durations) / len(durations) if durations else None

    # Calculate Sharpe ratio (simplified - would need risk-free rate for full calculation)
    if len(valid_pnls) > 1:
        mean_pnl = sum(valid_pnls) / len(valid_pnls)
        variance = sum((pnl - mean_pnl) ** 2 for pnl in valid_pnls) / (
            len(valid_pnls) - 1
        )
        std_dev = variance**0.5
        sharpe_ratio = mean_pnl / std_dev if std_dev > 0 else None
    else:
        sharpe_ratio = None

    # Calculate maximum drawdown
    balance_history = [starting_balance]
    running_balance = starting_balance

    for trade in completed_trades:
        if trade.pnl is not None:
            running_balance += trade.pnl
            balance_history.append(running_balance)

    # Find maximum drawdown
    peak = balance_history[0]
    max_drawdown = 0.0
    max_drawdown_pct = 0.0

    for balance in balance_history:
        if balance > peak:
            peak = balance

        drawdown = peak - balance
        drawdown_pct = (drawdown / peak) * 100 if peak > 0 else 0.0

        if drawdown > max_drawdown:
            max_drawdown = drawdown
            max_drawdown_pct = drawdown_pct

    return BacktestMetrics(
        total_pnl=total_pnl,
        total_return_pct=total_return_pct,
        total_trades=len(completed_trades),
        winning_trades=len(winning_trades),
        losing_trades=len(losing_trades),
        win_rate=win_rate,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        max_drawdown_pct=max_drawdown_pct,
        profit_factor=profit_factor,
        average_win=average_win,
        average_loss=average_loss,
        largest_win=largest_win,
        largest_loss=largest_loss,
        total_time_in_market=total_time_in_market,
        average_trade_duration=average_trade_duration,
    )
