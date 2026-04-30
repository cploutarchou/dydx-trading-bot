DELETE FROM role_permissions
WHERE (role, permission_key) IN (
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
    ('agent', 'users.update')
);

DROP INDEX IF EXISTS idx_partner_relationships_sponsor_active;
DROP INDEX IF EXISTS idx_partner_relationships_sponsor_partner;
DROP INDEX IF EXISTS idx_users_role;
