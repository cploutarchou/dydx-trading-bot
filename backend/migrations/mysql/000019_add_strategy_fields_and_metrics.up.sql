-- Migration 000019: Add strategy fields to backtest_trades and create backtest_metrics table

-- Add new columns to backtest_trades
ALTER TABLE backtest_trades
  ADD COLUMN strategy_id INTEGER DEFAULT NULL;
ALTER TABLE backtest_trades
  ADD COLUMN strategy_name VARCHAR(255) DEFAULT NULL;
ALTER TABLE backtest_trades
  ADD COLUMN strategy_zscore_threshold FLOAT DEFAULT NULL;

-- Create indexes for new columns
CREATE INDEX idx_backtest_trades_strategy_id ON backtest_trades (strategy_id);
CREATE INDEX idx_backtest_trades_strategy_name ON backtest_trades (strategy_name);

-- Create backtest_metrics table
CREATE TABLE IF NOT EXISTS backtest_metrics
(
  id                       INT AUTO_INCREMENT PRIMARY KEY,
  run_id                   INTEGER NOT NULL UNIQUE,
  total_pnl                FLOAT    NOT NULL,
  total_return_pct         FLOAT    NOT NULL,
  total_trades             INTEGER NOT NULL,
  winning_trades           INTEGER NOT NULL,
  losing_trades            INTEGER NOT NULL,
  win_rate                 FLOAT    NOT NULL,
  avg_win                  FLOAT    NOT NULL,
  avg_loss                 FLOAT    NOT NULL,
  profit_factor            FLOAT    NOT NULL,
  max_drawdown             FLOAT    NOT NULL,
  max_drawdown_pct         FLOAT    NOT NULL,
  sharpe_ratio             FLOAT    NOT NULL,
  calmar_ratio             FLOAT    NOT NULL,
  max_consecutive_losses   INTEGER NOT NULL,
  avg_trade_duration_hours FLOAT    NOT NULL,
  created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (run_id)
);

-- Create indexes for backtest_metrics
CREATE INDEX idx_backtest_metrics_run_id ON backtest_metrics (run_id);
CREATE INDEX idx_backtest_metrics_created_at ON backtest_metrics (created_at);
CREATE INDEX idx_backtest_metrics_total_pnl ON backtest_metrics (total_pnl);
CREATE INDEX idx_backtest_metrics_sharpe_ratio ON backtest_metrics (sharpe_ratio);

