import { describe, expect, it } from 'vitest';
import { BACKOFFICE_ROLES, canBypassComingSoon, getUserWorkspaceRole, roleMatches } from './roles';

describe('workspace role helpers', () => {
  it('allows only admin and backoffice roles to bypass Coming Soon mode', () => {
    expect(canBypassComingSoon({ role: 'admin', is_admin: true })).toBe(true);
    expect(canBypassComingSoon({ role: 'operations_admin', is_admin: false })).toBe(true);
    expect(canBypassComingSoon({ role: 'backoffice', is_admin: false })).toBe(true);
    expect(canBypassComingSoon({ role: 'client', is_admin: false })).toBe(false);
    expect(canBypassComingSoon({ role: 'user', is_admin: false })).toBe(false);
    expect(canBypassComingSoon(null)).toBe(false);
  });

  it('keeps admin role matching behavior unchanged', () => {
    expect(getUserWorkspaceRole({ role: 'super_admin', is_admin: true })).toBe('super_admin');
    expect(roleMatches('admin', ['client'])).toBe(true);
    expect(roleMatches('client', ['admin'])).toBe(false);
  });

  it('fails closed for unknown/custom roles on backoffice route lists', () => {
    expect(roleMatches('contractor_dev', ['backoffice'])).toBe(false);
    expect(roleMatches('contractor_dev', BACKOFFICE_ROLES)).toBe(false);
    expect(roleMatches('contractor_dev', ['client', 'user'])).toBe(false);
  });

  it('still admits custom roles when they are explicitly allow-listed', () => {
    expect(roleMatches('contractor_dev', ['client', 'contractor_dev'])).toBe(true);
  });

  it('keeps built-in role groups matching their allow lists', () => {
    expect(roleMatches('support_agent', ['backoffice'])).toBe(true);
    expect(roleMatches('ib', ['ib', 'sub_ib'])).toBe(true);
    expect(roleMatches('sub_ib', ['ib', 'sub_ib'])).toBe(true);
    expect(roleMatches('client', ['client', 'user'])).toBe(true);
  });
});
