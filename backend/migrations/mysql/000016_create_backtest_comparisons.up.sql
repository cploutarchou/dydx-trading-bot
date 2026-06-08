-- Create backtest_comparisons table
CREATE TABLE IF NOT EXISTS backtest_comparisons
(
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  name                VARCHAR(100) NOT NULL,
  description         VARCHAR(500) DEFAULT NULL,
  user_id             INTEGER      NOT NULL,
  strategy_id_1       INTEGER      NOT NULL,
  strategy_id_2       INTEGER      NOT NULL,
  run_id_1            INTEGER      NOT NULL,
  run_id_2            INTEGER      NOT NULL,
  winner_run_id       INTEGER      DEFAULT NULL,
  pnl_difference      FLOAT         DEFAULT NULL,
  sharpe_difference   FLOAT         DEFAULT NULL,
  win_rate_difference FLOAT         DEFAULT NULL,
  drawdown_difference FLOAT         DEFAULT NULL,
  comparison_metrics  JSON         DEFAULT NULL,
  created_at          TIMESTAMP     DEFAULT NULL,
  updated_at          TIMESTAMP     DEFAULT NULL,
  KEY idx_fk_run_id_1 (run_id_1),
  KEY idx_fk_run_id_2 (run_id_2),
  KEY idx_fk_strategy_id_1 (strategy_id_1),
  KEY idx_fk_strategy_id_2 (strategy_id_2),
  KEY idx_fk_user_id (user_id)
);

CREATE INDEX idx_comparison_runs ON backtest_comparisons (run_id_1, run_id_2);
CREATE INDEX idx_comparison_strategies ON backtest_comparisons (strategy_id_1, strategy_id_2);
CREATE INDEX idx_comparison_user_created ON backtest_comparisons (user_id, created_at);
CREATE INDEX ix_backtest_comparisons_created_at ON backtest_comparisons (created_at);
CREATE INDEX ix_backtest_comparisons_id ON backtest_comparisons (id);
CREATE INDEX ix_backtest_comparisons_name ON backtest_comparisons (name);
CREATE INDEX ix_backtest_comparisons_user_id ON backtest_comparisons (user_id);

