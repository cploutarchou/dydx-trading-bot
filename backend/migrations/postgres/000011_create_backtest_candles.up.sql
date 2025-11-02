-- Create backtest_candles table
CREATE TABLE IF NOT EXISTS backtest_candles
(
  id           SERIAL PRIMARY KEY,
  run_id_fk    INTEGER      NOT NULL,
  market       VARCHAR(255) NOT NULL,
  timestamp    TIMESTAMP     NOT NULL,
  resolution   VARCHAR(20) DEFAULT NULL,
  open_price   REAL         NOT NULL,
  high_price   REAL         NOT NULL,
  low_price    REAL         NOT NULL,
  close_price  REAL         NOT NULL,
  volume       REAL         NOT NULL,
  trades_count INTEGER     DEFAULT NULL,
  created_at   TIMESTAMP    DEFAULT NULL,
  FOREIGN KEY (run_id_fk) REFERENCES backtest_runs (id)
);

CREATE INDEX idx_backtest_candle_market_time ON backtest_candles (market, timestamp);
CREATE INDEX idx_backtest_candle_run_market ON backtest_candles (run_id_fk, market);
CREATE INDEX idx_backtest_candle_run_time ON backtest_candles (run_id_fk, timestamp);
CREATE INDEX ix_backtest_candles_id ON backtest_candles (id);
CREATE INDEX ix_backtest_candles_market ON backtest_candles (market);
CREATE INDEX ix_backtest_candles_run_id_fk ON backtest_candles (run_id_fk);
CREATE INDEX ix_backtest_candles_timestamp ON backtest_candles (timestamp);

