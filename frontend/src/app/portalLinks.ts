import { getCurrentPortalType, type AppPortalType } from './portal';

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

const withPortalPathPrefix = (portal: AppPortalType, path: string): string => {
  if (portal === 'backoffice') {
    return path === '/crm' || path.startsWith('/crm/') ? path : `/crm${path === '/' ? '' : path}`;
  }

  if (portal === 'ib') {
    return path === '/ib-portal' || path.startsWith('/ib-portal/')
      ? path
      : `/ib-portal${path === '/' ? '' : path}`;
  }

  if (path.startsWith('/crm/')) {
    return path.replace(/^\/crm/, '') || '/';
  }

  if (path.startsWith('/ib-portal/')) {
    return path.replace(/^\/ib-portal/, '') || '/';
  }

  return path;
};

export const portalHref = (portal: AppPortalType, path: string = '/dashboard'): string => {
  const normalizedPath = normalizePath(path);
  if (typeof window === 'undefined') {
    return normalizedPath;
  }

  const currentPortal = getCurrentPortalType();
  if (import.meta.env.DEV) {
    return currentPortal === portal
      ? normalizedPath
      : withDevPortalOverride(normalizedPath, portal);
  }

  if (currentPortal === portal) {
    return normalizedPath;
  }

  return withPortalPathPrefix(portal, normalizedPath);
};

export const clientPortalHref = (path: string = '/dashboard'): string => portalHref('client', path);

export const backofficePortalHref = (path: string = '/dashboard'): string =>
  portalHref('backoffice', path);
