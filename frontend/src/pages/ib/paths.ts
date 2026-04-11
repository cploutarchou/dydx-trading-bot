const IB_PORTAL_SUBDOMAIN_PREFIX = 'ib-portal.';

const toIBPortalHost = (hostname: string): string => {
  const host = hostname.toLowerCase();
  if (host === 'localhost' || host.endsWith('.localhost')) {
    return 'ib-portal.localhost';
  }
  if (host.startsWith(IB_PORTAL_SUBDOMAIN_PREFIX)) {
    return host;
  }

  const parts = host.split('.');
  if (parts.length >= 2) {
    return `ib-portal.${parts.slice(-2).join('.')}`;
  }
  return `ib-portal.${host}`;
};

export const isIBPortalHost = (hostname?: string): boolean => {
  if (typeof window === 'undefined' && !hostname) {
    return false;
  }

  const host = String(hostname ?? window.location.hostname).toLowerCase();
  return host.startsWith(IB_PORTAL_SUBDOMAIN_PREFIX);
};

export const ibPortalPath = (section: string): string => {
  const normalized = section.replace(/^\/+/, '');
  return isIBPortalHost() ? `/${normalized}` : `/ib-portal/${normalized}`;
};

export const ibPortalSectionFromPath = (pathname: string): string | null => {
  const parts = pathname.split('/').filter(Boolean);
  if (parts.length === 0) {
    return 'dashboard';
  }

  if (parts[0] === 'ib-portal') {
    return parts[1] ?? 'dashboard';
  }

  return isIBPortalHost() ? parts[0] : null;
};

export const ibPortalHref = (section: string): string => {
  const path = ibPortalPath(section);
  if (typeof window === 'undefined') {
    return path;
  }

  if (isIBPortalHost()) {
    return path;
  }

  const { protocol, port, hostname } = window.location;
  const nextHost = toIBPortalHost(hostname);
  const portPart = port ? `:${port}` : '';
  return `${protocol}//${nextHost}${portPart}${path}`;
};
