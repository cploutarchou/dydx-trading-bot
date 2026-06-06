-- Migration 000025: Create bot_alerts table for bot runtime alert tracking
CREATE TABLE IF NOT EXISTS bot_alerts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  bot_instance_id INTEGER NOT NULL REFERENCES bot_instances(id) ON DELETE CASCADE,
  alert_type TEXT NOT NULL,
  severity TEXT NOT NULL DEFAULT 'info',
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  details TEXT,
  is_read INTEGER NOT NULL DEFAULT 0,
  acknowledged_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bot_alerts_bot_instance_id ON bot_alerts (bot_instance_id);
CREATE INDEX IF NOT EXISTS idx_bot_alerts_is_read ON bot_alerts (is_read);
CREATE INDEX IF NOT EXISTS idx_bot_alerts_created_at ON bot_alerts (created_at DESC);

