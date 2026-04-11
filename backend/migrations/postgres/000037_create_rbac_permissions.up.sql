CREATE TABLE IF NOT EXISTS permissions (
    id BIGSERIAL PRIMARY KEY,
    permission_key VARCHAR(100) NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    is_sensitive BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS role_permissions (
    id BIGSERIAL PRIMARY KEY,
    role VARCHAR(64) NOT NULL,
    permission_key VARCHAR(100) NOT NULL REFERENCES permissions(permission_key) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(role, permission_key)
);

CREATE TABLE IF NOT EXISTS user_permission_overrides (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    permission_key VARCHAR(100) NOT NULL REFERENCES permissions(permission_key) ON DELETE CASCADE,
    effect VARCHAR(10) NOT NULL CHECK (effect IN ('allow', 'deny')),
    reason TEXT NOT NULL DEFAULT '',
    granted_by_user_id BIGINT REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, permission_key)
);

CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role);
CREATE INDEX IF NOT EXISTS idx_user_permission_overrides_user ON user_permission_overrides(user_id);

INSERT INTO permissions (permission_key, description, is_sensitive) VALUES
    ('crm.read', 'Read CRM dashboards and operational datasets', FALSE),
    ('crm.write', 'Write CRM operational data', TRUE),
    ('users.read', 'Read user records', FALSE),
    ('users.update', 'Update user records', TRUE),
    ('users.disable', 'Disable user accounts', TRUE),
    ('kyc.read', 'Read KYC and verification information', TRUE),
    ('kyc.review', 'Approve or reject KYC/review actions', TRUE),
    ('finance.read', 'Read finance and commission information', TRUE),
    ('finance.manage', 'Manage finance and commission information', TRUE),
    ('audit.read', 'Read audit events and sensitive action traces', TRUE),
    ('security.events.read', 'Read authentication and security event streams', TRUE),
    ('roles.manage', 'Manage roles and permission assignments', TRUE),
    ('crm.admin.manage', 'Manage CRM operators and admin-level CRM settings', TRUE)
ON CONFLICT (permission_key) DO NOTHING;

INSERT INTO role_permissions (role, permission_key)
SELECT role_map.role, role_map.permission_key
FROM (
    VALUES
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
        ('security_analyst', 'security.events.read')
) AS role_map(role, permission_key)
ON CONFLICT (role, permission_key) DO NOTHING;
