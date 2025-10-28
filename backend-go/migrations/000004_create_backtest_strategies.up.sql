-- Create backtest_strategies table
CREATE TABLE IF NOT EXISTS backtest_strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(500) DEFAULT NULL,
    category VARCHAR(50) DEFAULT NULL,
    user_id INTEGER NOT NULL,
    is_public BOOLEAN DEFAULT NULL,
    is_default BOOLEAN DEFAULT NULL,
    zscore_threshold REAL NOT NULL,
    stats_window INTEGER NOT NULL,
    max_half_life REAL NOT NULL,
    usd_per_trade REAL NOT NULL,
    usd_min_collateral REAL NOT NULL,
    close_at_zscore_cross BOOLEAN NOT NULL,
    find_cointegrated_pairs BOOLEAN NOT NULL,
    manage_exits BOOLEAN NOT NULL,
    place_trades BOOLEAN NOT NULL,
    abort_all_positions BOOLEAN NOT NULL,
    max_positions INTEGER NOT NULL,
    max_drawdown_pct REAL NOT NULL,
    stop_loss_pct REAL NOT NULL,
    take_profit_pct REAL NOT NULL,
    trailing_stop_pct REAL NOT NULL,
    rebalance_interval_hours INTEGER NOT NULL,
    position_timeout_hours INTEGER NOT NULL,
    transaction_fee REAL NOT NULL,
    slippage REAL NOT NULL,
    starting_balance REAL NOT NULL,
    candle_resolution VARCHAR(20) NOT NULL,
    max_history_days INTEGER NOT NULL,
    benchmark_symbol VARCHAR(20) DEFAULT NULL,
    risk_free_rate REAL NOT NULL,
    initial_amount REAL NOT NULL,
    usage_count INTEGER DEFAULT NULL,
    last_used_at DATETIME DEFAULT NULL,
    created_at DATETIME DEFAULT NULL,
    updated_at DATETIME DEFAULT NULL,
    deleted_at DATETIME DEFAULT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE INDEX idx_strategy_category ON backtest_strategies(category);
CREATE INDEX idx_strategy_default ON backtest_strategies(is_default);
CREATE INDEX idx_strategy_public ON backtest_strategies(is_public);
CREATE INDEX idx_strategy_user_name ON backtest_strategies(user_id, name);
CREATE INDEX ix_backtest_strategies_created_at ON backtest_strategies(created_at);
CREATE INDEX ix_backtest_strategies_id ON backtest_strategies(id);
CREATE INDEX ix_backtest_strategies_name ON backtest_strategies(name);
CREATE INDEX ix_backtest_strategies_user_id ON backtest_strategies(user_id);

