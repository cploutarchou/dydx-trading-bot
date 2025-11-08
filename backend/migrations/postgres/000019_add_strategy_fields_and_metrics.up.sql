-- Migration 000019: Add strategy fields to backtest_trades and create backtest_metrics table

-- Add new columns to backtest_trades
ALTER TABLE backtest_trades
  ADD COLUMN strategy_id INTEGER DEFAULT NULL;
ALTER TABLE backtest_trades
  ADD COLUMN strategy_name VARCHAR(255) DEFAULT NULL;
ALTER TABLE backtest_trades
  ADD COLUMN strategy_zscore_threshold REAL DEFAULT NULL;

-- Create indexes for new columns
CREATE INDEX idx_backtest_trades_strategy_id ON backtest_trades (strategy_id);
CREATE INDEX idx_backtest_trades_strategy_name ON backtest_trades (strategy_name);

-- Create backtest_metrics table
CREATE TABLE IF NOT EXISTS backtest_metrics
(
  id                       SERIAL PRIMARY KEY,
  run_id                   INTEGER NOT NULL UNIQUE,
  total_pnl                REAL    NOT NULL,
  total_return_pct         REAL    NOT NULL,
  total_trades             INTEGER NOT NULL,
  winning_trades           INTEGER NOT NULL,
  losing_trades            INTEGER NOT NULL,
  win_rate                 REAL    NOT NULL,
  avg_win                  REAL    NOT NULL,
  avg_loss                 REAL    NOT NULL,
  profit_factor            REAL    NOT NULL,
  max_drawdown             REAL    NOT NULL,
  max_drawdown_pct         REAL    NOT NULL,
  sharpe_ratio             REAL    NOT NULL,
  calmar_ratio             REAL    NOT NULL,
  max_consecutive_losses   INTEGER NOT NULL,
  avg_trade_duration_hours REAL    NOT NULL,
  created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (run_id) REFERENCES backtest_runs (id)
);

-- Create indexes for backtest_metrics
CREATE INDEX idx_backtest_metrics_run_id ON backtest_metrics (run_id);
CREATE INDEX idx_backtest_metrics_created_at ON backtest_metrics (created_at);
CREATE INDEX idx_backtest_metrics_total_pnl ON backtest_metrics (total_pnl);
CREATE INDEX idx_backtest_metrics_sharpe_ratio ON backtest_metrics (sharpe_ratio);

