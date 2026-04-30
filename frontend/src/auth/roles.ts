export type WorkspaceRole =
  | 'admin'
  | 'super_admin'
  | 'backoffice'
  | 'operations_admin'
  | 'finance_admin'
  | 'support_agent'
  | 'ib'
  | 'sub_ib'
  | 'client'
  | 'user'
  | 'accounting'
  | 'marketing'
  | 'agent';

interface RoleLike {
  role?: string;
  is_admin?: boolean;
}

export const BACKOFFICE_ROLES: WorkspaceRole[] = [
  'admin',
  'super_admin',
  'backoffice',
  'operations_admin',
  'finance_admin',
  'support_agent',
];

export const CLIENT_ROLES: WorkspaceRole[] = ['client', 'user'];

export const IB_ROLES: WorkspaceRole[] = ['ib', 'sub_ib'];

const BACKOFFICE_ALIASES = new Set([
  'backoffice',
  'operations_admin',
  'compliance_admin',
  'support_agent',
  'finance_admin',
  'read_only_auditor',
  'security_analyst',
]);

export const normalizeWorkspaceRole = (role?: string, isAdmin?: boolean): WorkspaceRole => {
  const normalized = (role || '').trim().toLowerCase();
  if (isAdmin) {
    return normalized === 'super_admin' ? 'super_admin' : 'admin';
  }

  switch (normalized) {
    case 'admin':
    case 'super_admin':
    case 'operations_admin':
    case 'finance_admin':
    case 'support_agent':
    case 'ib':
    case 'sub_ib':
    case 'client':
    case 'user':
    case 'accounting':
    case 'marketing':
    case 'agent':
      return normalized;
    default:
      return BACKOFFICE_ALIASES.has(normalized) ? 'backoffice' : 'client';
  }
};

export const getUserWorkspaceRole = (user?: RoleLike | null): WorkspaceRole =>
  normalizeWorkspaceRole(user?.role, user?.is_admin);

export const roleMatches = (role: WorkspaceRole, allowedRoles?: WorkspaceRole[]): boolean => {
  if (!allowedRoles || allowedRoles.length === 0) {
    return true;
  }
  if (role === 'admin' || role === 'super_admin') {
    return (
      allowedRoles.includes(role) ||
      allowedRoles.includes('admin') ||
      allowedRoles.includes('super_admin') ||
      allowedRoles.includes('backoffice')
    );
  }
  if (allowedRoles.includes('backoffice') && BACKOFFICE_ROLES.includes(role)) {
    return true;
  }
  return allowedRoles.includes(role);
};
