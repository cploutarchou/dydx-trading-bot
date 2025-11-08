-- Create strategy_version_history table
CREATE TABLE IF NOT EXISTS strategy_version_history
(
  id                   SERIAL PRIMARY KEY,
  strategy_id          INTEGER NOT NULL,
  version_number       INTEGER NOT NULL,
  change_description   VARCHAR(500) DEFAULT NULL,
  config_snapshot      JSON    NOT NULL,
  changes              JSON         DEFAULT NULL,
  created_at           TIMESTAMP     DEFAULT NULL,
  created_by_user_id   INTEGER      DEFAULT NULL,
  backtest_count       INTEGER      DEFAULT NULL,
  best_backtest_pnl    REAL         DEFAULT NULL,
  average_backtest_pnl REAL         DEFAULT NULL,
  FOREIGN KEY (created_by_user_id) REFERENCES users (id),
  FOREIGN KEY (strategy_id) REFERENCES backtest_strategies (id),
  UNIQUE (strategy_id, version_number)
);

CREATE INDEX idx_strategy_version ON strategy_version_history (strategy_id, version_number);
CREATE INDEX idx_strategy_version_created ON strategy_version_history (strategy_id, created_at);
CREATE INDEX ix_strategy_version_history_created_at ON strategy_version_history (created_at);
CREATE INDEX ix_strategy_version_history_id ON strategy_version_history (id);
CREATE INDEX ix_strategy_version_history_strategy_id ON strategy_version_history (strategy_id);

