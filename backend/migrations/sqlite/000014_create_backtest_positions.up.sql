-- Create backtest_positions table
CREATE TABLE IF NOT EXISTS backtest_positions
(
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id_fk       INTEGER      NOT NULL,
  position_id     VARCHAR(100) NOT NULL UNIQUE,
  market_1        VARCHAR(50)  NOT NULL,
  market_2        VARCHAR(50)  NOT NULL,
  status          VARCHAR(20)  NOT NULL,
  entry_timestamp DATETIME     NOT NULL,
  close_timestamp DATETIME DEFAULT NULL,
  entry_price_1   REAL         NOT NULL,
  entry_price_2   REAL         NOT NULL,
  entry_z_score   REAL         NOT NULL,
  current_price_1 REAL     DEFAULT NULL,
  current_price_2 REAL     DEFAULT NULL,
  current_z_score REAL     DEFAULT NULL,
  size_1          REAL         NOT NULL,
  size_2          REAL         NOT NULL,
  side_1          VARCHAR(10)  NOT NULL,
  side_2          VARCHAR(10)  NOT NULL,
  hedge_ratio     REAL         NOT NULL,
  unrealized_pnl  REAL     DEFAULT NULL,
  realized_pnl    REAL     DEFAULT NULL,
  FOREIGN KEY (run_id_fk) REFERENCES backtest_runs (id)
);

CREATE INDEX idx_backtest_position_run_time ON backtest_positions (run_id_fk, entry_timestamp);
CREATE INDEX idx_backtest_position_status ON backtest_positions (run_id_fk, status);
CREATE INDEX ix_backtest_positions_id ON backtest_positions (id);
CREATE UNIQUE INDEX ix_backtest_positions_position_id ON backtest_positions (position_id);
CREATE INDEX ix_backtest_positions_run_id_fk ON backtest_positions (run_id_fk);

