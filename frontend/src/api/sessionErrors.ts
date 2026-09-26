/**
 * Session error classification shared by the API client and the auth store.
 *
 * Only an authoritative rejection from the backend, a 401 or a 403, means the
 * session is gone. A network error, a timeout, a cancelled request or a 5xx
 * says nothing about the session: the HttpOnly cookie is still in the browser
 * and the next attempt may succeed. Treating those as "logged out" used to
 * POST /auth/logout, which deleted the server session and signed the user out
 * of every tab because one page load hit a transient error.
 */

import { isAxiosError } from 'axios';
import { traceHeaderName } from './trace';

const AUTH_REJECTION_STATUSES: ReadonlySet<number> = new Set([401, 403]);

/** True only for a 401 or 403 response: the backend rejected the session. */
export const isAuthRejection = (error: unknown): boolean =>
  isAxiosError(error) &&
  error.response !== undefined &&
  AUTH_REJECTION_STATUSES.has(error.response.status);

export interface SessionErrorSummary {
  message: string;
  status: number | null;
  traceId: string | null;
}

const nonEmptyString = (value: unknown): value is string =>
  typeof value === 'string' && value !== '';

/**
 * Log-friendly view of a failed session call, with the backend trace id when
 * the response carried one, so a support log line can be matched to the
 * gateway's request log.
 */
export const describeSessionError = (error: unknown): SessionErrorSummary => {
  if (isAxiosError(error)) {
    const headers = error.response?.headers as Record<string, unknown> | undefined;
    const body = error.response?.data as { trace_id?: unknown } | undefined;
    const traceId =
      [headers?.[traceHeaderName.toLowerCase()], body?.trace_id].find(nonEmptyString) ?? null;
    return { message: error.message, status: error.response?.status ?? null, traceId };
  }
  return {
    message: error instanceof Error ? error.message : String(error),
    status: null,
    traceId: null,
  };
};
