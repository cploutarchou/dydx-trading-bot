import { describe, expect, it } from 'vitest';
import { BACKOFFICE_ROLES, CLIENT_ROLES, IB_ROLES } from '../auth/roles';
import { getPortalRouteManifest } from './routeManifest';

describe('portal route manifest', () => {
  it('keeps client workspace routes role-scoped to client users', () => {
    const routes = getPortalRouteManifest('client');

    expect(routes.find((route) => route.path === '/dashboard')?.allowedRoles).toEqual(CLIENT_ROLES);
    expect(routes.find((route) => route.path === '/backtests')?.allowedRoles).toEqual(CLIENT_ROLES);
    expect(routes.find((route) => route.path === '/strategies/managet')?.allowedRoles).toEqual(
      CLIENT_ROLES
    );
    expect(routes.find((route) => route.path === '/admin/celery')?.allowedRoles).toEqual([
      'admin',
      'super_admin',
      'backoffice_admin',
    ]);
  });

  it('keeps backoffice routes behind backoffice roles', () => {
    const routes = getPortalRouteManifest('backoffice');

    expect(routes.find((route) => route.path === '/dashboard')?.allowedRoles).toEqual(
      BACKOFFICE_ROLES
    );
    expect(routes.find((route) => route.path === '/crm/*')?.allowedRoles).toEqual(
      BACKOFFICE_ROLES
    );
  });

  it('allows IB and backoffice oversight roles into the IB portal', () => {
    const routes = getPortalRouteManifest('ib');
    const wildcardRoles = routes.find((route) => route.path === '/*')?.allowedRoles ?? [];

    expect(wildcardRoles).toEqual([...IB_ROLES, ...BACKOFFICE_ROLES]);
  });
});
