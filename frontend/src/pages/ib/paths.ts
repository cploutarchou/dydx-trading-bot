import { getCurrentPortalType } from '../../app/portal';
import { getPortalSubdomainConfig } from '../../utils/portalSubdomainSettings';

const IB_PORTAL_SUBDOMAIN_PREFIXES = ['ib.', 'ib-portal.'] as const;

const toIBPortalHost = (hostname: string): string => {
  const host = hostname.toLowerCase();
  if (host === 'localhost' || host.endsWith('.localhost')) {
    return 'ib-portal.localhost';
  }
  if (IB_PORTAL_SUBDOMAIN_PREFIXES.some((prefix) => host.startsWith(prefix))) {
    return host;
  }

  const parts = host.split('.');
  if (parts.length >= 2) {
    return `ib.${parts.slice(-2).join('.')}`;
  }
  return `ib.${host}`;
};

export const isIBPortalHost = (hostname?: string): boolean => {
  if (typeof window === 'undefined' && !hostname) {
    return false;
  }

  const config = getPortalSubdomainConfig('ib');
  const host = String(hostname ?? window.location.hostname).toLowerCase();
  return (
    host === config.host.toLowerCase() ||
    IB_PORTAL_SUBDOMAIN_PREFIXES.some((prefix) => host.startsWith(prefix))
  );
};

export const ibPortalPath = (section: string): string => {
  const normalized = section.replace(/^\/+/, '');
  return getCurrentPortalType() === 'ib' || isIBPortalHost()
    ? `/${normalized}`
    : `/ib-portal/${normalized}`;
};

export const ibPortalSectionFromPath = (pathname: string): string | null => {
  const parts = pathname.split('/').filter(Boolean);
  if (parts.length === 0) {
    return 'dashboard';
  }

  if (parts[0] === 'ib-portal') {
    return parts[1] ?? 'dashboard';
  }

  return getCurrentPortalType() === 'ib' || isIBPortalHost() ? parts[0] : null;
};

export const ibPortalHref = (section: string): string => {
  const path = ibPortalPath(section);
  if (typeof window === 'undefined') {
    return path;
  }

  const config = getPortalSubdomainConfig('ib');
  if (!config.enabled) {
    return path;
  }

  if (isIBPortalHost()) {
    return path;
  }

  const { protocol, port } = window.location;
  const nextHost = config.host || toIBPortalHost(window.location.hostname);
  const portPart = port ? `:${port}` : '';
  return `${protocol}//${nextHost}${portPart}${path}`;
};
