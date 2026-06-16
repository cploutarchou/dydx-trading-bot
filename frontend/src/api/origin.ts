export const PRODUCTION_API_BASE_URL = 'https://api.executionlab.io';
export const STAGING_API_BASE_URL = 'https://api.staging.executionlab.io';
const LOCAL_API_BASE_URL = 'http://localhost:8888';

type RuntimeEnvironment = 'local' | 'staging' | 'production';

type RuntimeConfigLike = {
  apiBaseUrl?: string;
};

type LocationLike = {
  protocol: string;
  host: string;
  hostname?: string;
};

type ApiBaseResolutionContext = {
  buildTimeApiBaseUrl?: string;
  buildTimeLegacyApiUrl?: string;
  dev?: boolean;
  locationLike?: Partial<LocationLike>;
  runtimeConfig?: RuntimeConfigLike | null;
};

const buildTimeApiBase = (
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ||
  (import.meta.env.VITE_API_URL as string | undefined)
)?.trim();

const trimTrailingSlash = (value: string): string => value.replace(/\/+$/, '');

const hostnameFromLocation = (locationLike?: Partial<LocationLike>): string => {
  const rawHostname =
    locationLike?.hostname ||
    String(locationLike?.host || '')
      .split(':')[0]
      ?.trim();
  return String(rawHostname || '').toLowerCase();
};

export const isLocalHostname = (hostname: string): boolean => {
  const normalized = hostname.trim().toLowerCase();
  return (
    normalized === 'localhost' ||
    normalized === '127.0.0.1' ||
    normalized.endsWith('.localhost')
  );
};

export const isStagingHostname = (hostname: string): boolean => {
  const normalized = hostname.trim().toLowerCase();
  return (
    normalized === 'staging.executionlab.io' ||
    normalized.startsWith('staging-') ||
    normalized.startsWith('staging.')
  );
};

const resolveEnvironmentFromHostname = (hostname: string, dev: boolean): RuntimeEnvironment => {
  if (dev || isLocalHostname(hostname)) {
    return 'local';
  }
  if (isStagingHostname(hostname)) {
    return 'staging';
  }
  return 'production';
};

const defaultLocationLike = (): LocationLike => {
  if (typeof window !== 'undefined') {
    return window.location;
  }
  return {
    protocol: 'https:',
    host: 'executionlab.io',
    hostname: 'executionlab.io',
  };
};

const defaultRuntimeConfig = (): RuntimeConfigLike | null => {
  if (typeof window === 'undefined') {
    return null;
  }
  return window.__EXECUTIONLAB_CONFIG__ ?? null;
};

const parseConfiguredApiBase = (
  candidate: string | undefined,
  environment: RuntimeEnvironment
): string | null => {
  const trimmed = String(candidate || '').trim();
  if (!trimmed) {
    return null;
  }

  try {
    const parsed = new URL(trimmed);
    const hostname = parsed.hostname.toLowerCase();
    const normalized = trimTrailingSlash(parsed.toString());

    if (hostname === 'api.staging.executionlab.io') {
      return parsed.protocol === 'https:' && environment !== 'production' ? normalized : null;
    }

    if (hostname === 'api.executionlab.io') {
      return parsed.protocol === 'https:' && environment !== 'staging' ? normalized : null;
    }

    if (isLocalHostname(hostname)) {
      return environment === 'local' && /^https?:$/.test(parsed.protocol) ? normalized : null;
    }

    return null;
  } catch {
    return null;
  }
};

export const resolveApiBaseUrl = (context: ApiBaseResolutionContext = {}): string => {
  const locationLike = context.locationLike ?? defaultLocationLike();
  const hostname = hostnameFromLocation(locationLike);
  const dev = context.dev ?? import.meta.env.DEV;
  const environment = resolveEnvironmentFromHostname(hostname, dev);

  const runtimeBase = parseConfiguredApiBase(
    context.runtimeConfig === undefined
      ? defaultRuntimeConfig()?.apiBaseUrl
      : context.runtimeConfig?.apiBaseUrl,
    environment
  );
  if (runtimeBase) {
    return runtimeBase;
  }

  const configuredBuildBase = parseConfiguredApiBase(
    context.buildTimeApiBaseUrl ?? buildTimeApiBase,
    environment
  );
  if (configuredBuildBase) {
    return configuredBuildBase;
  }

  const configuredLegacyBuildBase = parseConfiguredApiBase(
    context.buildTimeLegacyApiUrl,
    environment
  );
  if (configuredLegacyBuildBase) {
    return configuredLegacyBuildBase;
  }

  if (environment === 'local') {
    return LOCAL_API_BASE_URL;
  }

  if (environment === 'staging') {
    return STAGING_API_BASE_URL;
  }

  return PRODUCTION_API_BASE_URL;
};

export const preferBackendDevProxy =
  import.meta.env.DEV &&
  (!buildTimeApiBase ||
    buildTimeApiBase === 'http://localhost:8888' ||
    buildTimeApiBase === 'http://127.0.0.1:8888');

export const getBackendHttpBase = (): string =>
  preferBackendDevProxy ? '' : resolveApiBaseUrl();

export const resolveBackendUrl = (
  input: string,
  baseUrl: string = getBackendHttpBase()
): string => {
  if (/^https?:\/\//i.test(input)) {
    return input;
  }

  if (!baseUrl || !/^https?:\/\//i.test(baseUrl)) {
    return input;
  }

  return new URL(input, baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`).toString();
};

export const shouldAttemptCookieSessionBootstrap = (
  baseUrl: string = getBackendHttpBase(),
  locationLike: Partial<LocationLike> = defaultLocationLike()
): boolean => {
  const browserProtocol = String(locationLike.protocol || '')
    .trim()
    .toLowerCase();
  const browserHost = String(locationLike.host || '')
    .trim()
    .toLowerCase();

  if (browserProtocol !== 'https:' || isLocalHostname(browserHost.split(':')[0] || '')) {
    return false;
  }

  if (!baseUrl || !/^https?:\/\//i.test(baseUrl)) {
    return true;
  }

  try {
    const parsedBaseUrl = new URL(baseUrl);
    return parsedBaseUrl.protocol === 'https:' && !isLocalHostname(parsedBaseUrl.hostname);
  } catch {
    return false;
  }
};

export const resolveBackendWebSocketUrl = (
  path: string,
  token?: string,
  baseUrl: string = getBackendHttpBase(),
  locationLike: Partial<LocationLike> = defaultLocationLike()
): string => {
  if (/^wss?:\/\//i.test(path)) {
    const directUrl = new URL(path);
    if (token) {
      directUrl.searchParams.set('access_token', token);
    }
    return directUrl.toString();
  }

  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const fallbackHttpOrigin = `${locationLike.protocol === 'https:' ? 'https:' : 'http:'}//${locationLike.host}`;
  const httpBase = baseUrl && /^https?:\/\//i.test(baseUrl) ? baseUrl : fallbackHttpOrigin;
  const targetUrl = new URL(normalizedPath, httpBase.endsWith('/') ? httpBase : `${httpBase}/`);
  targetUrl.protocol = targetUrl.protocol === 'https:' ? 'wss:' : 'ws:';

  if (token) {
    targetUrl.searchParams.set('access_token', token);
  }

  return targetUrl.toString();
};
