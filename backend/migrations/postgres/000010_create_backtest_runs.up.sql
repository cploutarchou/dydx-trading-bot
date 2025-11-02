-- Create backtest_runs table
CREATE TABLE IF NOT EXISTS backtest_runs
(
  id                  SERIAL PRIMARY KEY,
  run_id              VARCHAR(50) NOT NULL UNIQUE,
  status              VARCHAR(20) DEFAULT NULL,
  created_at          TIMESTAMP    DEFAULT NULL,
  started_at          TIMESTAMP    DEFAULT NULL,
  completed_at        TIMESTAMP    DEFAULT NULL,
  duration_seconds    REAL        DEFAULT NULL,
  start_date          VARCHAR(10) NOT NULL,
  end_date            VARCHAR(10) NOT NULL,
  num_pairs           INTEGER     NOT NULL,
  total_markets       INTEGER     NOT NULL,
  resolution          VARCHAR(20) DEFAULT NULL,
  config              JSON        DEFAULT NULL,
  total_trades        INTEGER     DEFAULT NULL,
  profitable_trades   INTEGER     DEFAULT NULL,
  losing_trades       INTEGER     DEFAULT NULL,
  win_rate            REAL        DEFAULT NULL,
  total_pnl           REAL        DEFAULT NULL,
  total_pnl_usd       REAL        DEFAULT NULL,
  sharpe_ratio        REAL        DEFAULT NULL,
  sortino_ratio       REAL        DEFAULT NULL,
  calmar_ratio        REAL        DEFAULT NULL,
  max_drawdown        REAL        DEFAULT NULL,
  profit_factor       REAL        DEFAULT NULL,
  starting_balance    REAL        DEFAULT NULL,
  ending_balance      REAL        DEFAULT NULL,
  max_balance         REAL        DEFAULT NULL,
  min_balance         REAL        DEFAULT NULL,
  error_message       TEXT        DEFAULT NULL,
  user_id             INTEGER     DEFAULT NULL,
  strategy_id         INTEGER     DEFAULT NULL,
  strategy_snapshot   JSON        DEFAULT NULL,
  strategy_version_id INTEGER     DEFAULT NULL,
  FOREIGN KEY (strategy_id) REFERENCES backtest_strategies (id),
  FOREIGN KEY (strategy_version_id) REFERENCES strategy_version_history (id),
  FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE INDEX idx_run_date_range ON backtest_runs (start_date, end_date);
CREATE INDEX idx_run_status_created ON backtest_runs (status, created_at);
CREATE INDEX idx_run_user_created ON backtest_runs (user_id, created_at);
CREATE INDEX ix_backtest_runs_created_at ON backtest_runs (created_at);
CREATE INDEX ix_backtest_runs_id ON backtest_runs (id);
CREATE UNIQUE INDEX ix_backtest_runs_run_id ON backtest_runs (run_id);
CREATE INDEX ix_backtest_runs_status ON backtest_runs (status);
CREATE INDEX ix_backtest_runs_strategy_id ON backtest_runs (strategy_id);
CREATE INDEX ix_backtest_runs_strategy_version_id ON backtest_runs (strategy_version_id);
CREATE INDEX ix_backtest_runs_user_id ON backtest_runs (user_id);

