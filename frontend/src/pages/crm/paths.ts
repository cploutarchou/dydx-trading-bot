const CRM_SUBDOMAIN_PREFIX = 'crm.';

const toCRMHost = (hostname: string): string => {
  const host = hostname.toLowerCase();
  if (host === 'localhost' || host.endsWith('.localhost')) {
    return 'crm.localhost';
  }
  if (host.startsWith(CRM_SUBDOMAIN_PREFIX)) {
    return host;
  }

  const parts = host.split('.');
  if (parts.length >= 2) {
    return `crm.${parts.slice(-2).join('.')}`;
  }
  return `crm.${host}`;
};

export const isCRMHost = (hostname?: string): boolean => {
  if (typeof window === 'undefined' && !hostname) {
    return false;
  }

  const host = String(hostname ?? window.location.hostname).toLowerCase();
  return host.startsWith(CRM_SUBDOMAIN_PREFIX);
};

export const crmPath = (section: string): string => {
  const normalized = section.replace(/^\/+/, '');
  return isCRMHost() ? `/${normalized}` : `/crm/${normalized}`;
};

export const crmSectionFromPath = (pathname: string): string | null => {
  const parts = pathname.split('/').filter(Boolean);
  if (parts.length === 0) {
    return 'dashboard';
  }

  if (parts[0] === 'crm') {
    return parts[1] ?? 'dashboard';
  }

  return isCRMHost() ? parts[0] : null;
};

export const crmHref = (section: string): string => {
  const path = crmPath(section);
  if (typeof window === 'undefined') {
    return path;
  }

  if (isCRMHost()) {
    return path;
  }

  const { protocol, port, hostname } = window.location;
  const nextHost = toCRMHost(hostname);
  const portPart = port ? `:${port}` : '';
  return `${protocol}//${nextHost}${portPart}${path}`;
};
