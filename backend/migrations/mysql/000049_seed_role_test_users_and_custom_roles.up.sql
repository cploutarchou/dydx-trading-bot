CREATE TABLE IF NOT EXISTS custom_roles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    role VARCHAR(64) NOT NULL UNIQUE,
    display_name VARCHAR(120) NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    is_system TINYINT(1) NOT NULL DEFAULT 0,
    created_by_user_id BIGINT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_custom_roles_role ON custom_roles(role);

INSERT INTO custom_roles (role, display_name, description, is_system, created_at, updated_at)
VALUES
    ('admin', 'Admin', 'Built-in platform administrator role', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('super_admin', 'Super Admin', 'Built-in unrestricted platform administrator role', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('backoffice', 'Backoffice', 'Built-in CRM/backoffice operator role', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('operations_admin', 'Operations Admin', 'Built-in operations administrator role', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('compliance_admin', 'Compliance Admin', 'Built-in compliance administrator role', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('support_agent', 'Support Agent', 'Built-in support operator role', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('finance_admin', 'Finance Admin', 'Built-in finance administrator role', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('read_only_auditor', 'Read Only Auditor', 'Built-in audit-only role', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('security_analyst', 'Security Analyst', 'Built-in security analyst role', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('ib', 'IB', 'Built-in introducing broker role', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('sub_ib', 'Sub-IB', 'Built-in sub introducing broker role', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('user', 'User', 'Built-in normal user role', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('accounting', 'Accounting', 'Built-in accounting operator role', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('marketing', 'Marketing', 'Built-in marketing operator role', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('agent', 'Agent', 'Built-in agent operator role', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('client', 'Client', 'Built-in client role', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON DUPLICATE KEY UPDATE display_name = VALUES(display_name),
    description = VALUES(description),
    is_system = 1,
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
    1,
    0,
    0,
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
    1,
    0,
    0,
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
    1,
    0,
    0,
    '$2a$10$cdefghijklmnopqrstuvwu0CJBEqyaK25EFI1QGVONX1dqF01Vzam',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  )
ON DUPLICATE KEY UPDATE email = VALUES(email),
    role = VALUES(role),
    full_name = VALUES(full_name),
    is_active = VALUES(is_active),
    is_admin = VALUES(is_admin),
    password_change_required = VALUES(password_change_required),
    hashed_password = VALUES(hashed_password),
    updated_at = CURRENT_TIMESTAMP;
