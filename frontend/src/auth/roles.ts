export type WorkspaceRole =
  | 'admin'
  | 'super_admin'
  | 'backoffice_admin'
  | 'backoffice'
  | 'operations_admin'
  | 'compliance_admin'
  | 'finance_admin'
  | 'support_agent'
  | 'read_only_auditor'
  | 'security_analyst'
  | 'ib'
  | 'sub_ib'
  | 'client'
  | 'user'
  | 'accounting'
  | 'marketing'
  | 'agent'
  | (string & {});

interface RoleLike {
  role?: string;
  is_admin?: boolean;
}

export const BACKOFFICE_ROLES: WorkspaceRole[] = [
  'admin',
  'super_admin',
  'backoffice_admin',
  'backoffice',
  'operations_admin',
  'compliance_admin',
  'finance_admin',
  'support_agent',
  'read_only_auditor',
  'security_analyst',
  'accounting',
  'marketing',
  'agent',
];

export const CLIENT_ROLES: WorkspaceRole[] = ['client', 'user'];

export const IB_ROLES: WorkspaceRole[] = ['ib', 'sub_ib'];

export const TELEGRAM_GLOBAL_ADMIN_ROLES: WorkspaceRole[] = [
  'admin',
  'super_admin',
  'backoffice_admin',
];

const BACKOFFICE_ALIASES = new Set([
  'backoffice',
  'operations_admin',
  'compliance_admin',
  'support_agent',
  'finance_admin',
  'read_only_auditor',
  'security_analyst',
]);

const BUILT_IN_ROLES = new Set<string>([
  ...BACKOFFICE_ROLES,
  ...CLIENT_ROLES,
  ...IB_ROLES,
]);

export const normalizeWorkspaceRole = (role?: string, isAdmin?: boolean): WorkspaceRole => {
  const normalized = (role || '').trim().toLowerCase();
  if (isAdmin) {
    return normalized === 'super_admin' ? 'super_admin' : 'admin';
  }

  switch (normalized) {
    case 'admin':
    case 'super_admin':
    case 'backoffice_admin':
    case 'operations_admin':
    case 'compliance_admin':
    case 'finance_admin':
    case 'support_agent':
    case 'read_only_auditor':
    case 'security_analyst':
    case 'ib':
    case 'sub_ib':
    case 'client':
    case 'user':
    case 'accounting':
    case 'marketing':
    case 'agent':
      return normalized;
    default:
      if (BACKOFFICE_ALIASES.has(normalized)) return 'backoffice';
      return normalized || 'client';
  }
};

export const getUserWorkspaceRole = (user?: RoleLike | null): WorkspaceRole =>
  normalizeWorkspaceRole(user?.role, user?.is_admin);

export const roleMatches = (role: WorkspaceRole, allowedRoles?: WorkspaceRole[]): boolean => {
  if (!allowedRoles || allowedRoles.length === 0) {
    return true;
  }
  if (role === 'admin' || role === 'super_admin') {
    return true;
  }
  if (allowedRoles.includes('backoffice') && BACKOFFICE_ROLES.includes(role)) {
    return true;
  }
  const isCustomRole = !BUILT_IN_ROLES.has(role);
  const allowsBackoffice = allowedRoles.some((allowedRole) => BACKOFFICE_ROLES.includes(allowedRole));
  if (isCustomRole && allowsBackoffice) {
    return true;
  }
  return allowedRoles.includes(role);
};
