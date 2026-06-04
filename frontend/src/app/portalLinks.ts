import { getPortalSubdomainConfig, type PortalKind } from '../utils/portalSubdomainSettings';
import { getCurrentPortalType, type AppPortalType } from './portal';

const PORTAL_TO_CONFIG_KIND: Record<AppPortalType, PortalKind> = {
  backoffice: 'crm',
  client: 'client',
  ib: 'ib',
};

const normalizePath = (path: string): string => {
  const trimmed = path.trim();
  if (!trimmed || trimmed === '/') return '/';
  return trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
};

const withDevPortalOverride = (path: string, portal: AppPortalType): string => {
  const url = new URL(path, 'http://local.portal');
  url.searchParams.set('portal', portal);
  return `${url.pathname}${url.search}${url.hash}`;
};

export const portalHref = (portal: AppPortalType, path: string = '/dashboard'): string => {
  const normalizedPath = normalizePath(path);
  if (typeof window === 'undefined') {
    return normalizedPath;
  }

  const currentPortal = getCurrentPortalType();
  if (import.meta.env.DEV) {
    return currentPortal === portal ? normalizedPath : withDevPortalOverride(normalizedPath, portal);
  }

  const config = getPortalSubdomainConfig(PORTAL_TO_CONFIG_KIND[portal]);
  if (!config.enabled || currentPortal === portal) {
    return normalizedPath;
  }

  const host = config.host.trim();
  if (!host) {
    return normalizedPath;
  }

  const { protocol, port } = window.location;
  const portPart = port ? `:${port}` : '';
  return `${protocol}//${host}${portPart}${normalizedPath}`;
};

export const clientPortalHref = (path: string = '/dashboard'): string =>
  portalHref('client', path);

export const backofficePortalHref = (path: string = '/dashboard'): string =>
  portalHref('backoffice', path);
