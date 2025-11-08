-- Create backtest_logs table
CREATE TABLE IF NOT EXISTS backtest_logs
(
  id         SERIAL PRIMARY KEY,
  run_id_fk  INTEGER NOT NULL,
  message    TEXT    NOT NULL,
  level      VARCHAR(20) DEFAULT NULL,
  created_at TIMESTAMP    DEFAULT NULL,
  FOREIGN KEY (run_id_fk) REFERENCES backtest_runs (id)
);

CREATE INDEX idx_backtest_log_run_created ON backtest_logs (run_id_fk, created_at);
CREATE INDEX ix_backtest_logs_created_at ON backtest_logs (created_at);
CREATE INDEX ix_backtest_logs_id ON backtest_logs (id);
CREATE INDEX ix_backtest_logs_run_id_fk ON backtest_logs (run_id_fk);

