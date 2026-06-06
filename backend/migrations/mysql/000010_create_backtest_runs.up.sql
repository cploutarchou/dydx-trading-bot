-- Create backtest_runs table (MySQL/MariaDB version)
-- Converted from: backend/migrations/postgres/000010_create_backtest_runs.up.sql
-- Changes: SERIAL → AUTO_INCREMENT, REAL → FLOAT, TEXT → LONGTEXT

CREATE TABLE IF NOT EXISTS backtest_runs
(
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  run_id              VARCHAR(50) NOT NULL UNIQUE,
  status              VARCHAR(20) DEFAULT NULL,
  created_at          TIMESTAMP   NULL DEFAULT NULL,
  started_at          TIMESTAMP   NULL DEFAULT NULL,
  completed_at        TIMESTAMP   NULL DEFAULT NULL,
  duration_seconds    FLOAT       DEFAULT NULL,
  start_date          VARCHAR(10) NOT NULL,
  end_date            VARCHAR(10) NOT NULL,
  num_pairs           INTEGER     NOT NULL,
  total_markets       INTEGER     NOT NULL,
  resolution          VARCHAR(20) DEFAULT NULL,
  config              JSON        DEFAULT NULL,
  total_trades        INTEGER     DEFAULT NULL,
  profitable_trades   INTEGER     DEFAULT NULL,
  losing_trades       INTEGER     DEFAULT NULL,
  win_rate            FLOAT       DEFAULT NULL,
  total_pnl           FLOAT       DEFAULT NULL,
  total_pnl_usd       FLOAT       DEFAULT NULL,
  sharpe_ratio        FLOAT       DEFAULT NULL,
  sortino_ratio       FLOAT       DEFAULT NULL,
  calmar_ratio        FLOAT       DEFAULT NULL,
  max_drawdown        FLOAT       DEFAULT NULL,
  profit_factor       FLOAT       DEFAULT NULL,
  starting_balance    FLOAT       DEFAULT NULL,
  ending_balance      FLOAT       DEFAULT NULL,
  max_balance         FLOAT       DEFAULT NULL,
  min_balance         FLOAT       DEFAULT NULL,
  error_message       LONGTEXT    DEFAULT NULL,
  user_id             INTEGER     DEFAULT NULL,
  strategy_id         INTEGER     DEFAULT NULL,
  strategy_snapshot   JSON        DEFAULT NULL,
  strategy_version_id INTEGER     DEFAULT NULL,
  FOREIGN KEY (strategy_id),
  FOREIGN KEY (strategy_version_id),
  FOREIGN KEY (user_id)
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
