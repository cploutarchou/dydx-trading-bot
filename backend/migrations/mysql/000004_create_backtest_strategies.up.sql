-- Create backtest_strategies table (MySQL/MariaDB version)
-- Converted from: backend/migrations/postgres/000004_create_backtest_strategies.up.sql
-- Changes: SERIAL → AUTO_INCREMENT, REAL → FLOAT

CREATE TABLE IF NOT EXISTS backtest_strategies
(
  id                       INT AUTO_INCREMENT PRIMARY KEY,
  name                     VARCHAR(100) NOT NULL,
  description              VARCHAR(500) DEFAULT NULL,
  category                 VARCHAR(50)  DEFAULT NULL,
  user_id                  INTEGER      NOT NULL,
  is_public                TINYINT(1)      DEFAULT NULL,
  is_default               TINYINT(1)      DEFAULT NULL,
  zscore_threshold         FLOAT        NOT NULL,
  stats_window             INTEGER      NOT NULL,
  max_half_life            FLOAT        NOT NULL,
  usd_per_trade            FLOAT        NOT NULL,
  usd_min_collateral       FLOAT        NOT NULL,
  close_at_zscore_cross    TINYINT(1)      NOT NULL,
  find_cointegrated_pairs  TINYINT(1)      NOT NULL,
  manage_exits             TINYINT(1)      NOT NULL,
  place_trades             TINYINT(1)      NOT NULL,
  abort_all_positions      TINYINT(1)      NOT NULL,
  max_positions            INTEGER      NOT NULL,
  max_drawdown_pct         FLOAT        NOT NULL,
  stop_loss_pct            FLOAT        NOT NULL,
  take_profit_pct          FLOAT        NOT NULL,
  trailing_stop_pct        FLOAT        NOT NULL,
  rebalance_interval_hours INTEGER      NOT NULL,
  position_timeout_hours   INTEGER      NOT NULL,
  transaction_fee          FLOAT        NOT NULL,
  slippage                 FLOAT        NOT NULL,
  starting_balance         FLOAT        NOT NULL,
  candle_resolution        VARCHAR(20)  NOT NULL,
  max_history_days         INTEGER      NOT NULL,
  benchmark_symbol         VARCHAR(20)  DEFAULT NULL,
  risk_free_rate           FLOAT        NOT NULL,
  initial_amount           FLOAT        NOT NULL,
  usage_count              INTEGER      DEFAULT 0,
  last_used_at             TIMESTAMP    NULL DEFAULT NULL,
  created_at               TIMESTAMP    NULL DEFAULT NULL,
  updated_at               TIMESTAMP    NULL DEFAULT NULL,
  deleted_at               TIMESTAMP    NULL DEFAULT NULL,
  FOREIGN KEY (user_id)
);

CREATE INDEX idx_strategy_category ON backtest_strategies (category);
CREATE INDEX idx_strategy_default ON backtest_strategies (is_default);
CREATE INDEX idx_strategy_public ON backtest_strategies (is_public);
CREATE INDEX idx_strategy_user_name ON backtest_strategies (user_id, name);
CREATE INDEX ix_backtest_strategies_created_at ON backtest_strategies (created_at);
CREATE INDEX ix_backtest_strategies_id ON backtest_strategies (id);
CREATE INDEX ix_backtest_strategies_name ON backtest_strategies (name);
CREATE INDEX ix_backtest_strategies_user_id ON backtest_strategies (user_id);
