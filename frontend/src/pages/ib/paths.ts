const IB_PORTAL_SUBDOMAIN_PREFIXES = ['ib.', 'ib-portal.'] as const;

export const isIBPortalHost = (hostname?: string): boolean => {
  if (typeof window === 'undefined' && !hostname) {
    return false;
  }

  const host = String(hostname ?? window.location.hostname).toLowerCase();
  return IB_PORTAL_SUBDOMAIN_PREFIXES.some((prefix) => host.startsWith(prefix));
};

export const ibPortalPath = (section: string): string => {
  const normalized = section.replace(/^\/+/, '');
  return `/ib-portal/${normalized}`;
};

export const ibPortalSectionFromPath = (pathname: string): string | null => {
  const parts = pathname.split('/').filter(Boolean);
  if (parts[0] !== 'ib-portal') return null;
  return parts[1] ?? 'dashboard';
};

export const ibPortalHref = (section: string): string => {
  return ibPortalPath(section);
};
