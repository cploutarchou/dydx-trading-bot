DELETE FROM role_permissions
WHERE (role = 'backoffice' AND permission_key IN ('users.disable', 'roles.manage', 'crm.admin.manage'))
   OR (role = 'operations_admin' AND permission_key IN ('users.disable', 'crm.admin.manage'))
   OR (role = 'accounting' AND permission_key IN ('crm.read', 'users.read', 'finance.read', 'audit.read'))
   OR (role = 'marketing' AND permission_key IN ('crm.read', 'users.read'))
   OR (role = 'agent' AND permission_key IN ('crm.read', 'users.read', 'users.update'));

DROP INDEX IF EXISTS idx_partner_relationships_sponsor_active;
DROP INDEX IF EXISTS idx_partner_relationships_sponsor_partner;
DROP INDEX IF EXISTS idx_users_role;
