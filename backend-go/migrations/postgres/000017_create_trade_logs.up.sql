-- Create trade_logs table
CREATE TABLE IF NOT EXISTS trade_logs
(
  id              SERIAL PRIMARY KEY,
  result_id_fk    INTEGER     NOT NULL,
  trade_number    INTEGER     NOT NULL,
  entry_timestamp TIMESTAMP    NOT NULL,
  exit_timestamp  TIMESTAMP DEFAULT NULL,
  entry_price_1   REAL        NOT NULL,
  entry_price_2   REAL        NOT NULL,
  exit_price_1    REAL     DEFAULT NULL,
  exit_price_2    REAL     DEFAULT NULL,
  quantity_1      REAL        NOT NULL,
  quantity_2      REAL        NOT NULL,
  side_1          VARCHAR(10) NOT NULL,
  side_2          VARCHAR(10) NOT NULL,
  pnl             REAL     DEFAULT NULL,
  pnl_usd         REAL     DEFAULT NULL,
  entry_zscore    REAL     DEFAULT NULL,
  exit_zscore     REAL     DEFAULT NULL,
  created_at      TIMESTAMP DEFAULT NULL,
  FOREIGN KEY (result_id_fk) REFERENCES backtest_results (id)
);

CREATE INDEX idx_trade_result ON trade_logs (result_id_fk, entry_timestamp);
CREATE INDEX ix_trade_logs_id ON trade_logs (id);
CREATE INDEX ix_trade_logs_result_id_fk ON trade_logs (result_id_fk);

