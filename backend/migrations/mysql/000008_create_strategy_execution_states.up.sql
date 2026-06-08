-- Create strategy_execution_states table
CREATE TABLE IF NOT EXISTS strategy_execution_states
(
  id                       INT AUTO_INCREMENT PRIMARY KEY,
  strategy_id              INTEGER NOT NULL UNIQUE,
  enabled                  TINYINT(1)      DEFAULT NULL,
  status                   VARCHAR(20)  DEFAULT NULL,
  trades_executed          INTEGER      DEFAULT NULL,
  pnl                      FLOAT         DEFAULT NULL,
  pnl_pct                  FLOAT         DEFAULT NULL,
  last_error               VARCHAR(500) DEFAULT NULL,
  error_count              INTEGER      DEFAULT NULL,
  last_error_at            TIMESTAMP     DEFAULT NULL,
  config_snapshot          JSON         DEFAULT NULL,
  last_started             TIMESTAMP     DEFAULT NULL,
  last_stopped             TIMESTAMP     DEFAULT NULL,
  last_trade_at            TIMESTAMP     DEFAULT NULL,
  uptime_seconds           INTEGER      DEFAULT NULL,
  last_cointegration_check TIMESTAMP     DEFAULT NULL,
  active_pairs_count       INTEGER      DEFAULT NULL,
  open_positions_count     INTEGER      DEFAULT NULL,
  max_drawdown             FLOAT         DEFAULT NULL,
  sharpe_ratio             FLOAT         DEFAULT NULL,
  win_rate                 FLOAT         DEFAULT NULL,
  created_at               TIMESTAMP     DEFAULT NULL,
  updated_at               TIMESTAMP     DEFAULT NULL,
  KEY idx_fk_strategy_id (strategy_id)
);

CREATE INDEX idx_execution_state_status ON strategy_execution_states (strategy_id, status);
CREATE INDEX idx_execution_state_strategy_enabled ON strategy_execution_states (strategy_id, enabled);
CREATE INDEX idx_execution_state_updated ON strategy_execution_states (updated_at);
CREATE INDEX ix_strategy_execution_states_created_at ON strategy_execution_states (created_at);
CREATE INDEX ix_strategy_execution_states_enabled ON strategy_execution_states (enabled);
CREATE INDEX ix_strategy_execution_states_id ON strategy_execution_states (id);
CREATE INDEX ix_strategy_execution_states_status ON strategy_execution_states (status);
CREATE INDEX ix_strategy_execution_states_strategy_id ON strategy_execution_states (strategy_id);
CREATE INDEX ix_strategy_execution_states_updated_at ON strategy_execution_states (updated_at);

