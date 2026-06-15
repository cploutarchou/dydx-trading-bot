import { describe, expect, it } from 'vitest';
import { PUBLIC_PAGE_NAVIGATION, isComingSoonBypassPath } from './publicAccess';

describe('public access routing', () => {
  it('keeps navigation between launch, ICO, and login routes stable', () => {
    expect(PUBLIC_PAGE_NAVIGATION).toEqual({
      launch: '/',
      ico: '/ico',
      login: '/login',
    });
  });

  it('allows required public/auth routes through the Coming Soon gate', () => {
    expect(isComingSoonBypassPath('/login')).toBe(true);
    expect(isComingSoonBypassPath('/ico')).toBe(true);
    expect(isComingSoonBypassPath('/ico/whitepaper')).toBe(true);
    expect(isComingSoonBypassPath('/ico/tokenomics')).toBe(true);
    expect(isComingSoonBypassPath('/2fa-setup')).toBe(true);
    expect(isComingSoonBypassPath('/force-password')).toBe(true);
  });

  it('does not bypass normal public or protected routes during Coming Soon mode', () => {
    expect(isComingSoonBypassPath('/')).toBe(false);
    expect(isComingSoonBypassPath('/dashboard')).toBe(false);
    expect(isComingSoonBypassPath('/pricing')).toBe(false);
  });
});
