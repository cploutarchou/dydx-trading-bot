import { describe, expect, it } from 'vitest';
import { filterNavItemsForRole, getWorkspaceNavItems } from './workspaceNav';

describe('Celery admin navigation', () => {
  it('shows the Celery ops link only to admin roles', () => {
    const backofficeItems = getWorkspaceNavItems('backoffice');
    const clientItems = getWorkspaceNavItems('client');

    expect(filterNavItemsForRole(backofficeItems, 'admin').some((item) => item.path === '/admin/celery')).toBe(true);
    expect(filterNavItemsForRole(backofficeItems, 'backoffice').some((item) => item.path === '/admin/celery')).toBe(false);
    expect(filterNavItemsForRole(backofficeItems, 'client').some((item) => item.path === '/admin/celery')).toBe(false);
    expect(filterNavItemsForRole(clientItems, 'admin').some((item) => item.path === '/admin/celery')).toBe(true);
    expect(filterNavItemsForRole(clientItems, 'client').some((item) => item.path === '/admin/celery')).toBe(false);
  });
});
