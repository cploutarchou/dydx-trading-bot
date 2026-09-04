import { platformHost } from './urlSafety';

export type PortalKind = 'crm' | 'ib' | 'client';

interface PortalSubdomainConfig {
  enabled: boolean;
  host: string;
}

const STORAGE_KEYS = {
  crm: {
    enabled: 'platform.crm_subdomain_enabled',
    host: 'platform.crm_subdomain_host',
  },
  ib: {
    enabled: 'platform.ib_subdomain_enabled',
    host: 'platform.ib_subdomain_host',
  },
  client: {
    enabled: 'platform.client_subdomain_enabled',
    host: 'platform.client_subdomain_host',
  },
} as const;

const DEFAULTS: Record<PortalKind, PortalSubdomainConfig> = {
  crm: {
    enabled: false,
    host: import.meta.env.VITE_CRM_HOST || 'crm.localhost',
  },
  ib: {
    enabled: false,
    host: import.meta.env.VITE_IB_PORTAL_HOST || 'ib.localhost',
  },
  client: {
    enabled: false,
    host: import.meta.env.VITE_CLIENT_HOST || 'app.localhost',
  },
};

const parseBoolean = (value: string | null | undefined, fallback: boolean): boolean => {
  if (value == null) return fallback;
  const normalized = value.trim().toLowerCase();
  if (['true', '1', 'yes', 'on'].includes(normalized)) return true;
  if (['false', '0', 'no', 'off'].includes(normalized)) return false;
  return fallback;
};

// Admin-configured hosts must stay on platform-owned domains; anything else
// falls back to the built-in default (audit FE-029).
const sanitizeHost = (host: string, fallback: string): string => platformHost(host, fallback);

export const getPortalSubdomainConfig = (portal: PortalKind): PortalSubdomainConfig => {
  const defaults = DEFAULTS[portal];
  if (typeof window === 'undefined') {
    return defaults;
  }

  const keys = STORAGE_KEYS[portal];
  const enabled = parseBoolean(window.localStorage.getItem(keys.enabled), defaults.enabled);
  const host = sanitizeHost(window.localStorage.getItem(keys.host) ?? defaults.host, defaults.host);

  return {
    enabled,
    host,
  };
};

export const setPortalSubdomainConfig = (
  portal: PortalKind,
  config: PortalSubdomainConfig
): void => {
  if (typeof window === 'undefined') {
    return;
  }

  const keys = STORAGE_KEYS[portal];
  const defaults = DEFAULTS[portal];
  window.localStorage.setItem(keys.enabled, String(config.enabled));
  window.localStorage.setItem(keys.host, sanitizeHost(config.host, defaults.host));
};
