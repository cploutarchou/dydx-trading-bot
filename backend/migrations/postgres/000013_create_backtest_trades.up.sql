-- Create backtest_trades table
CREATE TABLE IF NOT EXISTS backtest_trades
(
  id              SERIAL PRIMARY KEY,
  run_id_fk       INTEGER      NOT NULL,
  trade_id        VARCHAR(100) NOT NULL UNIQUE,
  market_1        VARCHAR(50)  NOT NULL,
  market_2        VARCHAR(50)  NOT NULL,
  entry_timestamp TIMESTAMP     NOT NULL,
  entry_price_1   REAL         NOT NULL,
  entry_price_2   REAL         NOT NULL,
  entry_z_score   REAL         NOT NULL,
  side_1          VARCHAR(10)  NOT NULL,
  side_2          VARCHAR(10)  NOT NULL,
  size_1          REAL         NOT NULL,
  size_2          REAL         NOT NULL,
  exit_timestamp  TIMESTAMP DEFAULT NULL,
  exit_price_1    REAL     DEFAULT NULL,
  exit_price_2    REAL     DEFAULT NULL,
  exit_z_score    REAL     DEFAULT NULL,
  pnl             REAL     DEFAULT NULL,
  pnl_pct         REAL     DEFAULT NULL,
  duration_hours  REAL     DEFAULT NULL,
  hedge_ratio     REAL         NOT NULL,
  transaction_fee REAL         NOT NULL,
  slippage        REAL         NOT NULL,
  FOREIGN KEY (run_id_fk) REFERENCES backtest_runs (id)
);

CREATE INDEX idx_backtest_trade_market ON backtest_trades (market_1, market_2);
CREATE INDEX idx_backtest_trade_run_entry ON backtest_trades (run_id_fk, entry_timestamp);
CREATE INDEX ix_backtest_trades_entry_timestamp ON backtest_trades (entry_timestamp);
CREATE INDEX ix_backtest_trades_exit_timestamp ON backtest_trades (exit_timestamp);
CREATE INDEX ix_backtest_trades_id ON backtest_trades (id);
CREATE INDEX ix_backtest_trades_market_1 ON backtest_trades (market_1);
CREATE INDEX ix_backtest_trades_market_2 ON backtest_trades (market_2);
CREATE INDEX ix_backtest_trades_run_id_fk ON backtest_trades (run_id_fk);
CREATE UNIQUE INDEX ix_backtest_trades_trade_id ON backtest_trades (trade_id);

