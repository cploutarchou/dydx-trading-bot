-- Create backtest_positions table
CREATE TABLE IF NOT EXISTS backtest_positions
(
  id              INT AUTO_INCREMENT PRIMARY KEY,
  run_id_fk       INTEGER      NOT NULL,
  position_id     VARCHAR(100) NOT NULL UNIQUE,
  market_1        VARCHAR(50)  NOT NULL,
  market_2        VARCHAR(50)  NOT NULL,
  status          VARCHAR(20)  NOT NULL,
  entry_timestamp TIMESTAMP     NOT NULL,
  close_timestamp TIMESTAMP DEFAULT NULL,
  entry_price_1   FLOAT         NOT NULL,
  entry_price_2   FLOAT         NOT NULL,
  entry_z_score   FLOAT         NOT NULL,
  current_price_1 FLOAT     DEFAULT NULL,
  current_price_2 FLOAT     DEFAULT NULL,
  current_z_score FLOAT     DEFAULT NULL,
  size_1          FLOAT         NOT NULL,
  size_2          FLOAT         NOT NULL,
  side_1          VARCHAR(10)  NOT NULL,
  side_2          VARCHAR(10)  NOT NULL,
  hedge_ratio     FLOAT         NOT NULL,
  unrealized_pnl  FLOAT     DEFAULT NULL,
  realized_pnl    FLOAT     DEFAULT NULL,
  KEY idx_fk_run_id_fk (run_id_fk)
);

CREATE INDEX idx_backtest_position_run_time ON backtest_positions (run_id_fk, entry_timestamp);
CREATE INDEX idx_backtest_position_status ON backtest_positions (run_id_fk, status);
CREATE INDEX ix_backtest_positions_id ON backtest_positions (id);
CREATE UNIQUE INDEX ix_backtest_positions_position_id ON backtest_positions (position_id);
CREATE INDEX ix_backtest_positions_run_id_fk ON backtest_positions (run_id_fk);

