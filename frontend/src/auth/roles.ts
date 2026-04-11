export type WorkspaceRole =
  | 'admin'
  | 'backoffice'
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

export const normalizeWorkspaceRole = (role?: string, isAdmin?: boolean): WorkspaceRole => {
  const normalized = (role || '').trim().toLowerCase();
  if (isAdmin) {
    return 'admin';
  }

  switch (normalized) {
    case 'admin':
    case 'super_admin':
      return 'admin';
    case 'backoffice':
    case 'operations_admin':
    case 'compliance_admin':
    case 'support_agent':
    case 'finance_admin':
    case 'read_only_auditor':
    case 'security_analyst':
      return 'backoffice';
    case 'ib':
    case 'sub_ib':
    case 'client':
    case 'user':
    case 'accounting':
    case 'marketing':
    case 'agent':
      return normalized;
    default:
      return 'client';
  }
};

export const getUserWorkspaceRole = (user?: RoleLike | null): WorkspaceRole =>
  normalizeWorkspaceRole(user?.role, user?.is_admin);

export const roleMatches = (role: WorkspaceRole, allowedRoles?: WorkspaceRole[]): boolean => {
  if (!allowedRoles || allowedRoles.length === 0) {
    return true;
  }
  if (role === 'admin') {
    return true;
  }
  return allowedRoles.includes(role);
};
