const TRACE_HEADER = 'X-Trace-Id';

const randomHex = (bytes: number): string => {
  const buffer = new Uint8Array(bytes);
  globalThis.crypto.getRandomValues(buffer);
  return Array.from(buffer, (value) => value.toString(16).padStart(2, '0')).join('');
};

export const createTraceId = (): string => `req-${randomHex(6)}`;

export const attachTraceHeader = (headers: Headers | Record<string, string>): string => {
  const traceId = createTraceId();
  if (headers instanceof Headers) {
    headers.set(TRACE_HEADER, traceId);
  } else {
    headers[TRACE_HEADER] = traceId;
  }
  return traceId;
};

export const getResponseTraceId = (headers: Headers | { get?: (name: string) => string | null }): string | null => {
  if (typeof headers.get === 'function') {
    return headers.get(TRACE_HEADER);
  }
  return null;
};

export const traceHeaderName = TRACE_HEADER;
