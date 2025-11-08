-- Create backtest_comparisons table
CREATE TABLE IF NOT EXISTS backtest_comparisons
(
  id                  SERIAL PRIMARY KEY,
  name                VARCHAR(100) NOT NULL,
  description         VARCHAR(500) DEFAULT NULL,
  user_id             INTEGER      NOT NULL,
  strategy_id_1       INTEGER      NOT NULL,
  strategy_id_2       INTEGER      NOT NULL,
  run_id_1            INTEGER      NOT NULL,
  run_id_2            INTEGER      NOT NULL,
  winner_run_id       INTEGER      DEFAULT NULL,
  pnl_difference      REAL         DEFAULT NULL,
  sharpe_difference   REAL         DEFAULT NULL,
  win_rate_difference REAL         DEFAULT NULL,
  drawdown_difference REAL         DEFAULT NULL,
  comparison_metrics  JSON         DEFAULT NULL,
  created_at          TIMESTAMP     DEFAULT NULL,
  updated_at          TIMESTAMP     DEFAULT NULL,
  FOREIGN KEY (run_id_1) REFERENCES backtest_runs (id),
  FOREIGN KEY (run_id_2) REFERENCES backtest_runs (id),
  FOREIGN KEY (strategy_id_1) REFERENCES backtest_strategies (id),
  FOREIGN KEY (strategy_id_2) REFERENCES backtest_strategies (id),
  FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE INDEX idx_comparison_runs ON backtest_comparisons (run_id_1, run_id_2);
CREATE INDEX idx_comparison_strategies ON backtest_comparisons (strategy_id_1, strategy_id_2);
CREATE INDEX idx_comparison_user_created ON backtest_comparisons (user_id, created_at);
CREATE INDEX ix_backtest_comparisons_created_at ON backtest_comparisons (created_at);
CREATE INDEX ix_backtest_comparisons_id ON backtest_comparisons (id);
CREATE INDEX ix_backtest_comparisons_name ON backtest_comparisons (name);
CREATE INDEX ix_backtest_comparisons_user_id ON backtest_comparisons (user_id);

