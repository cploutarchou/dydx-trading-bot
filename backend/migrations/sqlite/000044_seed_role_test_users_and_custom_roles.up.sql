CREATE TABLE IF NOT EXISTS custom_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    is_system BOOLEAN NOT NULL DEFAULT 0,
    created_by_user_id INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id)
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
ON CONFLICT (role) DO UPDATE
SET display_name = excluded.display_name,
    description = excluded.description,
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
ON CONFLICT (username) DO UPDATE
SET email = excluded.email,
    role = excluded.role,
    full_name = excluded.full_name,
    is_active = excluded.is_active,
    is_admin = excluded.is_admin,
    password_change_required = excluded.password_change_required,
    hashed_password = excluded.hashed_password,
    updated_at = CURRENT_TIMESTAMP;
