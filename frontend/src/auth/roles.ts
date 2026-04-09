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
    case 'backoffice':
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
