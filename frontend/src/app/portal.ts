import { BACKOFFICE_ROLES, CLIENT_ROLES, IB_ROLES, type WorkspaceRole } from '../auth/roles';

export type AppPortalType = 'client' | 'backoffice' | 'ib';

const normalizePortalType = (value?: string | null): AppPortalType | null => {
  const normalized = String(value ?? '')
    .trim()
    .toLowerCase();

  if (normalized === 'client' || normalized === 'client-portal') return 'client';
  if (normalized === 'backoffice' || normalized === 'crm') return 'backoffice';
  if (normalized === 'ib' || normalized === 'ib-portal') return 'ib';
  return null;
};

export const getCurrentPortalType = (): AppPortalType => {
  const configured = normalizePortalType(import.meta.env.VITE_APP_PORTAL_TYPE);
  if (configured) return configured;

  if (typeof window === 'undefined') return 'client';

  const hostname = window.location.hostname.toLowerCase();
  if (hostname.startsWith('crm.')) return 'backoffice';
  if (hostname.startsWith('ib.') || hostname.startsWith('ib-portal.')) return 'ib';
  return 'client';
};

export const getPortalAllowedRoles = (portal: AppPortalType): WorkspaceRole[] => {
  switch (portal) {
    case 'backoffice':
      return BACKOFFICE_ROLES;
    case 'ib':
      return [...IB_ROLES, ...BACKOFFICE_ROLES];
    case 'client':
    default:
      return CLIENT_ROLES;
  }
};

export const getPortalLabel = (portal: AppPortalType): string => {
  switch (portal) {
    case 'backoffice':
      return 'CRM / Backoffice';
    case 'ib':
      return 'IB Portal';
    case 'client':
    default:
      return 'Client Portal';
  }
};
