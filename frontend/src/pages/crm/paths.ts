const CRM_SUBDOMAIN_PREFIX = 'crm.';

export const isCRMHost = (hostname?: string): boolean => {
  if (typeof window === 'undefined' && !hostname) {
    return false;
  }

  const host = String(hostname ?? window.location.hostname).toLowerCase();
  return host.startsWith(CRM_SUBDOMAIN_PREFIX);
};

export const crmPath = (section: string): string => {
  const normalized = section.replace(/^\/+/, '');
  return `/crm/${normalized}`;
};

export const crmSectionFromPath = (pathname: string): string | null => {
  const parts = pathname.split('/').filter(Boolean);
  if (parts[0] !== 'crm') return null;
  return parts[1] ?? 'dashboard';
};

export const crmHref = (section: string): string => {
  return crmPath(section);
};
