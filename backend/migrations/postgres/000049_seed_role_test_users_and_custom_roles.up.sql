CREATE TABLE IF NOT EXISTS custom_roles (
    id BIGSERIAL PRIMARY KEY,
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

-- SECURITY: these are development/demo convenience accounts whose password
-- hashes live in the repo. (1) Never overwrite an existing row's password on
-- conflict — a re-run must not clobber an operator's rotated credentials back
-- to the repo-known values. (2) Fresh installs seed them with
-- password_change_required = TRUE so the known passwords must be rotated
-- before the accounts are meaningfully usable. Remove these seeds entirely
-- if this environment faces the internet.
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
    TRUE,
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
    TRUE,
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
    TRUE,
    '$2a$10$cdefghijklmnopqrstuvwu0CJBEqyaK25EFI1QGVONX1dqF01Vzam',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  )
ON CONFLICT (username) DO NOTHING;
