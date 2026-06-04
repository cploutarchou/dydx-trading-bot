import { afterEach, describe, expect, it, vi } from 'vitest';
import { BACKOFFICE_ROLES, CLIENT_ROLES, IB_ROLES } from '../auth/roles';
import { getCurrentPortalType } from './portal';
import { backofficePortalHref, clientPortalHref } from './portalLinks';
import { getPortalRouteManifest } from './routeManifest';

const makeLocalStorage = () => {
  const storage = new Map<string, string>();
  return {
    clear: () => storage.clear(),
    getItem: (key: string) => storage.get(key) ?? null,
    removeItem: (key: string) => storage.delete(key),
    setItem: (key: string, value: string) => storage.set(key, value),
  };
};

const stubLocation = (search = '') => {
  vi.stubGlobal('window', {
    location: {
      hostname: 'localhost',
      port: '5173',
      protocol: 'http:',
      search,
    },
    localStorage: makeLocalStorage(),
  });
};

describe('portal route manifest', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('keeps client workspace routes role-scoped to client users', () => {
    const routes = getPortalRouteManifest('client');

    expect(routes.find((route) => route.path === '/dashboard')?.allowedRoles).toEqual(CLIENT_ROLES);
    expect(routes.find((route) => route.path === '/backtests')?.allowedRoles).toEqual(CLIENT_ROLES);
    expect(routes.find((route) => route.path === '/strategies/managet')?.allowedRoles).toEqual(
      CLIENT_ROLES
    );
    expect(routes.some((route) => route.path.startsWith('/admin'))).toBe(false);
  });

  it('keeps backoffice routes behind backoffice roles', () => {
    const routes = getPortalRouteManifest('backoffice');

    expect(routes.find((route) => route.path === '/dashboard')?.allowedRoles).toEqual(
      BACKOFFICE_ROLES
    );
    expect(routes.find((route) => route.path === '/crm/*')?.allowedRoles).toEqual(
      BACKOFFICE_ROLES
    );
    expect(routes.find((route) => route.path === '/admin/celery')?.allowedRoles).toEqual([
      'admin',
      'super_admin',
      'backoffice_admin',
    ]);
  });

  it('allows IB and backoffice oversight roles into the IB portal', () => {
    const routes = getPortalRouteManifest('ib');
    const wildcardRoles = routes.find((route) => route.path === '/*')?.allowedRoles ?? [];

    expect(wildcardRoles).toEqual([...IB_ROLES, ...BACKOFFICE_ROLES]);
  });

  it('uses same-origin dev portal links so local auth state survives admin switching', () => {
    stubLocation('');

    expect(getCurrentPortalType()).toBe('client');
    expect(backofficePortalHref('/dashboard')).toBe('/dashboard?portal=backoffice');

    stubLocation('?portal=backoffice');
    expect(getCurrentPortalType()).toBe('backoffice');
    expect(clientPortalHref('/dashboard')).toBe('/dashboard?portal=client');
  });
});
