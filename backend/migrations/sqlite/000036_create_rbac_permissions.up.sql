CREATE TABLE IF NOT EXISTS permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    permission_key TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    is_sensitive INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS role_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    permission_key TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(role, permission_key),
    FOREIGN KEY (permission_key) REFERENCES permissions(permission_key) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_permission_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    permission_key TEXT NOT NULL,
    effect TEXT NOT NULL CHECK (effect IN ('allow', 'deny')),
    reason TEXT NOT NULL DEFAULT '',
    granted_by_user_id INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, permission_key),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (granted_by_user_id) REFERENCES users(id),
    FOREIGN KEY (permission_key) REFERENCES permissions(permission_key) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role);
CREATE INDEX IF NOT EXISTS idx_user_permission_overrides_user ON user_permission_overrides(user_id);

INSERT OR IGNORE INTO permissions (permission_key, description, is_sensitive) VALUES
    ('crm.read', 'Read CRM dashboards and operational datasets', 0),
    ('crm.write', 'Write CRM operational data', 1),
    ('users.read', 'Read user records', 0),
    ('users.update', 'Update user records', 1),
    ('users.disable', 'Disable user accounts', 1),
    ('kyc.read', 'Read KYC and verification information', 1),
    ('kyc.review', 'Approve or reject KYC/review actions', 1),
    ('finance.read', 'Read finance and commission information', 1),
    ('finance.manage', 'Manage finance and commission information', 1),
    ('audit.read', 'Read audit events and sensitive action traces', 1),
    ('security.events.read', 'Read authentication and security event streams', 1),
    ('roles.manage', 'Manage roles and permission assignments', 1),
    ('crm.admin.manage', 'Manage CRM operators and admin-level CRM settings', 1);

INSERT OR IGNORE INTO role_permissions (role, permission_key) VALUES
    ('admin', 'crm.read'),
    ('admin', 'crm.write'),
    ('admin', 'users.read'),
    ('admin', 'users.update'),
    ('admin', 'users.disable'),
    ('admin', 'kyc.read'),
    ('admin', 'kyc.review'),
    ('admin', 'finance.read'),
    ('admin', 'finance.manage'),
    ('admin', 'audit.read'),
    ('admin', 'security.events.read'),
    ('admin', 'roles.manage'),
    ('admin', 'crm.admin.manage'),

    ('super_admin', 'crm.read'),
    ('super_admin', 'crm.write'),
    ('super_admin', 'users.read'),
    ('super_admin', 'users.update'),
    ('super_admin', 'users.disable'),
    ('super_admin', 'kyc.read'),
    ('super_admin', 'kyc.review'),
    ('super_admin', 'finance.read'),
    ('super_admin', 'finance.manage'),
    ('super_admin', 'audit.read'),
    ('super_admin', 'security.events.read'),
    ('super_admin', 'roles.manage'),
    ('super_admin', 'crm.admin.manage'),

    ('backoffice', 'crm.read'),
    ('backoffice', 'users.read'),
    ('backoffice', 'users.update'),
    ('backoffice', 'kyc.read'),
    ('backoffice', 'kyc.review'),
    ('backoffice', 'audit.read'),
    ('backoffice', 'security.events.read'),

    ('operations_admin', 'crm.read'),
    ('operations_admin', 'users.read'),
    ('operations_admin', 'users.update'),
    ('operations_admin', 'kyc.read'),
    ('operations_admin', 'kyc.review'),
    ('operations_admin', 'audit.read'),
    ('operations_admin', 'security.events.read'),

    ('compliance_admin', 'crm.read'),
    ('compliance_admin', 'users.read'),
    ('compliance_admin', 'kyc.read'),
    ('compliance_admin', 'kyc.review'),
    ('compliance_admin', 'audit.read'),
    ('compliance_admin', 'security.events.read'),

    ('support_agent', 'crm.read'),
    ('support_agent', 'users.read'),
    ('support_agent', 'users.update'),
    ('support_agent', 'kyc.read'),

    ('finance_admin', 'crm.read'),
    ('finance_admin', 'users.read'),
    ('finance_admin', 'finance.read'),
    ('finance_admin', 'finance.manage'),
    ('finance_admin', 'audit.read'),

    ('read_only_auditor', 'crm.read'),
    ('read_only_auditor', 'users.read'),
    ('read_only_auditor', 'kyc.read'),
    ('read_only_auditor', 'finance.read'),
    ('read_only_auditor', 'audit.read'),
    ('read_only_auditor', 'security.events.read'),

    ('security_analyst', 'crm.read'),
    ('security_analyst', 'users.read'),
    ('security_analyst', 'audit.read'),
    ('security_analyst', 'security.events.read');
