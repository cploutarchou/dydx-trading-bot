CREATE TABLE IF NOT EXISTS custom_roles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    role VARCHAR(64) NOT NULL UNIQUE,
    display_name VARCHAR(120) NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    created_by_user_id BIGINT REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_custom_roles_role ON custom_roles(role);

INSERT INTO custom_roles (role, display_name, description, is_system, created_at, updated_at)
VALUES
    ('admin', 'Admin', 'Built-in platform administrator role', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('super_admin', 'Super Admin', 'Built-in unrestricted platform administrator role', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('backoffice', 'Backoffice', 'Built-in CRM/backoffice operator role', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('operations_admin', 'Operations Admin', 'Built-in operations administrator role', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('compliance_admin', 'Compliance Admin', 'Built-in compliance administrator role', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('support_agent', 'Support Agent', 'Built-in support operator role', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('finance_admin', 'Finance Admin', 'Built-in finance administrator role', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('read_only_auditor', 'Read Only Auditor', 'Built-in audit-only role', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('security_analyst', 'Security Analyst', 'Built-in security analyst role', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('ib', 'IB', 'Built-in introducing broker role', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('sub_ib', 'Sub-IB', 'Built-in sub introducing broker role', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('user', 'User', 'Built-in normal user role', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('accounting', 'Accounting', 'Built-in accounting operator role', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('marketing', 'Marketing', 'Built-in marketing operator role', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('agent', 'Agent', 'Built-in agent operator role', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('client', 'Client', 'Built-in client role', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (role) DO UPDATE
SET display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    is_system = TRUE,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO users (
  username,
  email,
  role,
  full_name,
  avatar,
  is_active,
  is_admin,
  password_change_required,
  hashed_password,
  created_at,
  updated_at
)
VALUES
  (
    'user',
    'user@dydx-trading-bot.local',
    'user',
    'Test User',
    '',
    TRUE,
    FALSE,
    FALSE,
    '$2a$10$abcdefghijklmnopqrstuuqVwskozrMIYHaV2U8izbKS09gvJ9bm2',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'officer',
    'officer@dydx-trading-bot.local',
    'backoffice',
    'Backoffice Officer',
    '',
    TRUE,
    FALSE,
    FALSE,
    '$2a$10$bcdefghijklmnopqrstuvuDoUStSCH3iCWvmyku2QPZjCX8HZRZFK',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  ),
  (
    'ib',
    'ib@dydx-trading-bot.local',
    'ib',
    'Test IB',
    '',
    TRUE,
    FALSE,
    FALSE,
    '$2a$10$cdefghijklmnopqrstuvwu0CJBEqyaK25EFI1QGVONX1dqF01Vzam',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  )
ON CONFLICT (username) DO UPDATE
SET email = EXCLUDED.email,
    role = EXCLUDED.role,
    full_name = EXCLUDED.full_name,
    is_active = EXCLUDED.is_active,
    is_admin = EXCLUDED.is_admin,
    password_change_required = EXCLUDED.password_change_required,
    hashed_password = EXCLUDED.hashed_password,
    updated_at = CURRENT_TIMESTAMP;
