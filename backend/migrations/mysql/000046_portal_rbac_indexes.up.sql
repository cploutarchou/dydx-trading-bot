CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_partner_relationships_sponsor_partner
    ON partner_relationships(sponsor_user_id, partner_user_id);
CREATE INDEX IF NOT EXISTS idx_partner_relationships_sponsor_active
    ON partner_relationships(sponsor_user_id, is_active);

INSERT IGNORE INTO role_permissions (role, permission_key)
VALUES
    ('backoffice', 'users.disable'),
    ('backoffice', 'roles.manage'),
    ('backoffice', 'crm.admin.manage'),
    ('operations_admin', 'users.disable'),
    ('operations_admin', 'crm.admin.manage'),
    ('accounting', 'crm.read'),
    ('accounting', 'users.read'),
    ('accounting', 'finance.read'),
    ('accounting', 'audit.read'),
    ('marketing', 'crm.read'),
    ('marketing', 'users.read'),
    ('agent', 'crm.read'),
    ('agent', 'users.read'),
    ('agent', 'users.update');
