"""
Backtesting data models for dYdX Trading Bot

Implements backtesting result structures following project patterns
from pair_storage.py and config.py dataclass approach.
"""

import logging
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """
    Individual trade record for backtesting analysis.

    Follows project dataclass pattern like CointegrationResult.

    Attributes:
        timestamp: Trade execution timestamp
        market_1: Base market symbol (e.g., 'BTC-USD')
        market_2: Quote market symbol (e.g., 'ETH-USD')
        side_1: Trade side for market_1 ('BUY' or 'SELL')
        side_2: Trade side for market_2 ('BUY' or 'SELL')
        size_1: Position size for market_1
        size_2: Position size for market_2
        entry_price_1: Entry price for market_1
        entry_price_2: Entry price for market_2
        exit_price_1: Exit price for market_1 (None if still open)
        exit_price_2: Exit price for market_2 (None if still open)
        z_score_entry: Z-score at trade entry
        z_score_exit: Z-score at trade exit (None if still open)
        pnl: Realized profit/loss (None if still open)
        duration_hours: Trade duration in hours (None if still open)
        hedge_ratio: Hedge ratio used for the pair
        trade_id: Unique identifier for the trade
    """
    timestamp: str
    market_1: str
    market_2: str
    side_1: str
    side_2: str
    size_1: float
    size_2: float
    entry_price_1: float
    entry_price_2: float
    z_score_entry: float
    hedge_ratio: float
    trade_id: str
    exit_timestamp: Optional[str] = None
    exit_price_1: Optional[float] = None
    exit_price_2: Optional[float] = None
    z_score_exit: Optional[float] = None
    pnl: Optional[float] = None
    duration_hours: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'BacktestTrade':
        """Create instance from dictionary (JSON deserialization)."""
        return cls(**data)

    @property
    def is_closed(self) -> bool:
        """Check if trade is closed."""
        return self.exit_price_1 is not None and self.exit_price_2 is not None

    @property
    def pair_key(self) -> str:
        """Get unique key for this pair."""
        return f"{self.market_1}_{self.market_2}"


@dataclass
class BacktestMetrics:
    """
    Performance metrics for backtesting results.

    Following project analytical approach like confidence scoring.
    """
    total_pnl: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    calmar_ratio: float
    max_consecutive_losses: int
    avg_trade_duration_hours: float

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'BacktestMetrics':
        """Create instance from dictionary."""
        return cls(**data)


@dataclass
class BacktestResult:
    """
    Complete backtesting result following project storage patterns.

    Attributes:
        start_date: Backtest start date (ISO string)
        end_date: Backtest end date (ISO string)
        total_days: Number of days in backtest period
        starting_balance: Initial balance for simulation
        ending_balance: Final balance after simulation
        metrics: Performance metrics
        trades: List of all executed trades
        config_snapshot: Configuration used for backtest
        analysis_timestamp: When backtest was run
        version: Backtest format version
    """
    start_date: str
    end_date: str
    total_days: int
    starting_balance: float
    ending_balance: float
    metrics: BacktestMetrics
    trades: List[BacktestTrade]
    config_snapshot: Dict
    analysis_timestamp: str
    version: str = "1.0"

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert nested dataclasses
        data['metrics'] = self.metrics.to_dict()
        data['trades'] = [trade.to_dict() for trade in self.trades]
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'BacktestResult':
        """Create instance from dictionary."""
        # Convert nested structures
        metrics = BacktestMetrics.from_dict(data['metrics'])
        trades = [BacktestTrade.from_dict(trade_data)
                  for trade_data in data['trades']]

        # Create instance with converted nested objects
        result_data = data.copy()
        result_data['metrics'] = metrics
        result_data['trades'] = trades

        return cls(**result_data)

    @property
    def summary_stats(self) -> Dict:
        """Get summary statistics for quick display."""
        return {
            "period": f"{self.start_date} to {self.end_date}",
            "total_pnl": f"${self.metrics.total_pnl:.2f}",
            "total_return": f"{self.metrics.total_return_pct:.1f}%",
            "total_trades": self.metrics.total_trades,
            "win_rate": f"{self.metrics.win_rate:.1f}%",
            "sharpe_ratio": f"{self.metrics.sharpe_ratio:.2f}",
            "max_drawdown": f"{self.metrics.max_drawdown_pct:.1f}%"
        }


def calculate_backtest_metrics(trades: List[BacktestTrade],
                               starting_balance: float,
                               total_days: int) -> BacktestMetrics:
    """
    Calculate comprehensive performance metrics from trade list.

    Following project's analytical approach from func_cointegration.py.

    Args:
        trades: List of completed trades
        starting_balance: Initial account balance
        total_days: Total days in backtest period

    Returns:
        BacktestMetrics with calculated performance statistics
    """
    if not trades:
        return BacktestMetrics(
            total_pnl=0.0, total_return_pct=0.0, total_trades=0,
            winning_trades=0, losing_trades=0, win_rate=0.0,
            avg_win=0.0, avg_loss=0.0, profit_factor=0.0,
            max_drawdown=0.0, max_drawdown_pct=0.0,
            sharpe_ratio=0.0, calmar_ratio=0.0,
            max_consecutive_losses=0, avg_trade_duration_hours=0.0
        )

    # Filter completed trades only
    completed_trades = [
        trade for trade in trades if trade.is_closed and trade.pnl is not None]

    if not completed_trades:
        return BacktestMetrics(
            total_pnl=0.0, total_return_pct=0.0, total_trades=len(trades),
            winning_trades=0, losing_trades=0, win_rate=0.0,
            avg_win=0.0, avg_loss=0.0, profit_factor=0.0,
            max_drawdown=0.0, max_drawdown_pct=0.0,
            sharpe_ratio=0.0, calmar_ratio=0.0,
            max_consecutive_losses=0, avg_trade_duration_hours=0.0
        )

    # Basic PnL calculations
    total_pnl = sum(trade.pnl for trade in completed_trades)
    total_return_pct = (total_pnl / starting_balance) * 100

    # Win/Loss analysis
    winning_trades = [trade for trade in completed_trades if trade.pnl > 0]
    losing_trades = [trade for trade in completed_trades if trade.pnl <= 0]

    win_count = len(winning_trades)
    loss_count = len(losing_trades)
    win_rate = (win_count / len(completed_trades)) * \
        100 if completed_trades else 0

    avg_win = sum(trade.pnl for trade in winning_trades) / \
        win_count if win_count > 0 else 0
    avg_loss = sum(trade.pnl for trade in losing_trades) / \
        loss_count if loss_count > 0 else 0

    # Profit factor
    gross_profit = sum(trade.pnl for trade in winning_trades)
    gross_loss = abs(sum(trade.pnl for trade in losing_trades))
    profit_factor = gross_profit / \
        gross_loss if gross_loss > 0 else float('inf')

    # Drawdown calculation
    cumulative_pnl = 0
    peak_balance = starting_balance
    max_drawdown = 0
    max_drawdown_pct = 0

    for trade in completed_trades:
        cumulative_pnl += trade.pnl
        current_balance = starting_balance + cumulative_pnl

        if current_balance > peak_balance:
            peak_balance = current_balance
        else:
            drawdown = peak_balance - current_balance
            drawdown_pct = (drawdown / peak_balance) * 100

            if drawdown > max_drawdown:
                max_drawdown = drawdown
                max_drawdown_pct = drawdown_pct

    # Consecutive losses
    consecutive_losses = 0
    max_consecutive_losses = 0

    for trade in completed_trades:
        if trade.pnl <= 0:
            consecutive_losses += 1
            max_consecutive_losses = max(
                max_consecutive_losses, consecutive_losses)
        else:
            consecutive_losses = 0

    # Average trade duration
    durations = [
        trade.duration_hours for trade in completed_trades if trade.duration_hours is not None]
    avg_trade_duration = sum(durations) / len(durations) if durations else 0

    # Sharpe ratio (simplified - using daily returns)
    if len(completed_trades) > 1:
        daily_returns = []
        for trade in completed_trades:
            daily_return = (trade.pnl / starting_balance) * 100
            daily_returns.append(daily_return)

        if len(daily_returns) > 1:
            import statistics
            avg_return = statistics.mean(daily_returns)
            std_return = statistics.stdev(daily_returns)
            sharpe_ratio = (avg_return * 252) / (std_return *
                                                 (252 ** 0.5)) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
    else:
        sharpe_ratio = 0

    # Calmar ratio
    calmar_ratio = (total_return_pct * (365 / total_days)) / \
        max_drawdown_pct if max_drawdown_pct > 0 else 0

    return BacktestMetrics(
        total_pnl=total_pnl,
        total_return_pct=total_return_pct,
        total_trades=len(completed_trades),
        winning_trades=win_count,
        losing_trades=loss_count,
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        profit_factor=profit_factor,
        max_drawdown=max_drawdown,
        max_drawdown_pct=max_drawdown_pct,
        sharpe_ratio=sharpe_ratio,
        calmar_ratio=calmar_ratio,
        max_consecutive_losses=max_consecutive_losses,
        avg_trade_duration_hours=avg_trade_duration
    )
