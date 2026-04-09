const configuredApiBase = (import.meta.env.VITE_API_URL as string | undefined)?.trim();

export const preferBackendDevProxy =
  import.meta.env.DEV &&
  (!configuredApiBase ||
    configuredApiBase === 'http://localhost:8888' ||
    configuredApiBase === 'http://127.0.0.1:8888');

export const getBackendHttpBase = (): string =>
  preferBackendDevProxy ? '' : configuredApiBase || 'http://localhost:8888';

export const resolveBackendUrl = (input: string, baseUrl: string = getBackendHttpBase()): string => {
  if (/^https?:\/\//i.test(input)) {
    return input;
  }

  if (!baseUrl || !/^https?:\/\//i.test(baseUrl)) {
    return input;
  }

  return new URL(input, baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`).toString();
};

type LocationLike = {
  protocol: string;
  host: string;
};

const defaultLocationLike = (): LocationLike => {
  if (typeof window !== 'undefined') {
    return window.location;
  }
  return {
    protocol: 'http:',
    host: 'localhost:8888',
  };
};

export const resolveBackendWebSocketUrl = (
  path: string,
  token?: string,
  baseUrl: string = getBackendHttpBase(),
  locationLike: LocationLike = defaultLocationLike()
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
