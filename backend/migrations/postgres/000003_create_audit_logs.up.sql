-- Create audit_logs table
CREATE TABLE IF NOT EXISTS audit_logs
(
  id            SERIAL PRIMARY KEY,
  user_id       INTEGER      DEFAULT NULL,
  action        VARCHAR(100) NOT NULL,
  resource_type VARCHAR(50)  NOT NULL,
  resource_id   VARCHAR(100) DEFAULT NULL,
  details       JSON         DEFAULT NULL,
  status        VARCHAR(20)  DEFAULT NULL,
  ip_address    VARCHAR(50)  DEFAULT NULL,
  created_at    TIMESTAMP     DEFAULT NULL,
  FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE INDEX idx_audit_resource ON audit_logs (resource_type, resource_id);
CREATE INDEX idx_audit_user_action ON audit_logs (user_id, action);
CREATE INDEX ix_audit_logs_action ON audit_logs (action);
CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);
CREATE INDEX ix_audit_logs_id ON audit_logs (id);
CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);

