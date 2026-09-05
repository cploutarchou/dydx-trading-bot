/**
 * URL safety helpers (audit FE-029). React 19 blocks `javascript:` URLs at
 * render time, but upstream content (news feeds, admin-configured hosts)
 * deserves an explicit https-only guard as defense in depth.
 */

const HTTPS_URL = /^https:\/\/[^\s]+$/i;

/** Returns the URL only when it is a well-formed https URL, else undefined. */
export const httpsUrl = (value: unknown): string | undefined =>
  typeof value === 'string' && HTTPS_URL.test(value.trim()) ? value.trim() : undefined;

const ALLOWED_HOST_SUFFIXES = ['executionlab.io', 'executionlab.dev'];

/**
 * Keeps only admin-configured hosts that end in a platform-owned domain.
 * Prevents arbitrary-host links if platform settings or localStorage were
 * tampered with.
 */
export const platformHost = (host: string, fallback: string): string => {
  const normalized = host.trim().toLowerCase().replace(/^https?:\/\//, '').replace(/\/$/, '');
  if (!normalized) return fallback;
  const isPlatformOwned = ALLOWED_HOST_SUFFIXES.some(
    (suffix) => normalized === suffix || normalized.endsWith(`.${suffix}`)
  );
  return isPlatformOwned ? normalized : fallback;
};
