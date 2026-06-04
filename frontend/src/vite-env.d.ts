/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_AUTH_BASE_URL?: string;
  readonly VITE_APP_PORTAL_TYPE?: 'client' | 'backoffice' | 'ib';
  readonly VITE_CRM_HOST?: string;
  readonly VITE_IB_PORTAL_HOST?: string;
  readonly VITE_CLIENT_HOST?: string;
  readonly VITE_ENABLE_SUBDOMAIN_PORTAL_NAV?: string;
  /**
   * Cloudflare Turnstile site key for a Managed widget.
   * Widget mode is configured in Cloudflare, not in the client render options.
   */
  readonly VITE_TURNSTILE_SITE_KEY?: string;
  readonly VITE_DISABLE_TURNSTILE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
