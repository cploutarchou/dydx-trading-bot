ALTER TABLE strategy_execution_states ADD COLUMN is_running BOOLEAN DEFAULT FALSE;
ALTER TABLE strategy_execution_states ADD COLUMN last_run_at TIMESTAMP;
ALTER TABLE strategy_execution_states ADD COLUMN next_run_at TIMESTAMP;
ALTER TABLE strategy_execution_states ADD COLUMN state TEXT;

UPDATE strategy_execution_states
SET is_running = COALESCE(is_running, enabled, CASE WHEN LOWER(COALESCE(status, '')) IN ('running', 'starting') THEN TRUE ELSE FALSE END);

UPDATE strategy_execution_states
SET last_run_at = COALESCE(last_run_at, last_started, last_trade_at);

UPDATE strategy_execution_states
SET state = COALESCE(
  NULLIF(state, ''),
  NULLIF(status, ''),
  CASE WHEN COALESCE(is_running, enabled, FALSE) = TRUE THEN 'running' ELSE 'stopped' END
);

UPDATE strategy_execution_states
SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
    updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP);
