-- Create trade_logs table
CREATE TABLE IF NOT EXISTS trade_logs
(
  id              INT AUTO_INCREMENT PRIMARY KEY,
  result_id_fk    INTEGER     NOT NULL,
  trade_number    INTEGER     NOT NULL,
  entry_timestamp TIMESTAMP    NOT NULL,
  exit_timestamp  TIMESTAMP DEFAULT NULL,
  entry_price_1   FLOAT        NOT NULL,
  entry_price_2   FLOAT        NOT NULL,
  exit_price_1    FLOAT     DEFAULT NULL,
  exit_price_2    FLOAT     DEFAULT NULL,
  quantity_1      FLOAT        NOT NULL,
  quantity_2      FLOAT        NOT NULL,
  side_1          VARCHAR(10) NOT NULL,
  side_2          VARCHAR(10) NOT NULL,
  pnl             FLOAT     DEFAULT NULL,
  pnl_usd         FLOAT     DEFAULT NULL,
  entry_zscore    FLOAT     DEFAULT NULL,
  exit_zscore     FLOAT     DEFAULT NULL,
  created_at      TIMESTAMP DEFAULT NULL,
  KEY idx_fk_result_id_fk (result_id_fk)
);

CREATE INDEX idx_trade_result ON trade_logs (result_id_fk, entry_timestamp);
CREATE INDEX ix_trade_logs_id ON trade_logs (id);
CREATE INDEX ix_trade_logs_result_id_fk ON trade_logs (result_id_fk);

