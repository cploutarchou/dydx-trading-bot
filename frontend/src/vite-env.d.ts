/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
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
