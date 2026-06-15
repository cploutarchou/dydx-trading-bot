export const COMING_SOON_AUTH_BYPASS_PATHS = new Set([
  '/login',
  '/2fa-setup',
  '/force-password',
  '/ico',
  '/ico/whitepaper',
  '/ico/tokenomics',
]);

export const PUBLIC_PAGE_NAVIGATION = {
  launch: '/',
  ico: '/ico',
  login: '/login',
} as const;

export const isComingSoonBypassPath = (pathname: string): boolean =>
  COMING_SOON_AUTH_BYPASS_PATHS.has(pathname);
