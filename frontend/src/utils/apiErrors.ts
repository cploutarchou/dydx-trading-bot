/**
 * Human-friendly operator messages for API failures.
 *
 * Raw transport errors ("Request failed with status code 502", "Network Error")
 * are meaningless to operators and erode trust in control-room surfaces. This
 * helper maps them to short, actionable sentences. Keep the wording consistent
 * with the inline-notice style used across desks: state, then next step.
 */

interface HttpLikeError {
  response?: { status?: number };
  code?: string;
  message?: string;
}

const isHttpLikeError = (error: unknown): error is HttpLikeError =>
  typeof error === 'object' && error !== null && ('response' in error || 'code' in error);

const STATUS_MESSAGES: Record<number, string> = {
  400: 'The request was rejected by the backend. Check the inputs and try again.',
  401: 'Your session may have expired — sign in again to refresh access.',
  403: 'Your account does not have permission for this action.',
  404: 'This information is not available right now.',
  409: 'The backend reported a conflict — refresh and review the latest state.',
  429: 'Too many requests in a short window — retry in a moment.',
  500: 'The backend hit an internal error. Retry shortly; if it persists, check service logs.',
  502: 'An upstream service is unreachable. Verify the bot service is running, then retry.',
  503: 'The service is temporarily unavailable (likely an upstream dependency). Retry shortly.',
  504: 'The request timed out at the gateway. Retry when the service stabilizes.',
};

const humanizeNetworkCode = (code: string): string | null => {
  if (code === 'ERR_NETWORK' || code === 'ECONNABORTED' || code === 'ETIMEDOUT') {
    return 'The backend could not be reached. Check your connection and that the API service is running.';
  }
  if (code === 'ERR_CANCELED') {
    return 'The request was superseded by a newer one.';
  }
  return null;
};

/**
 * Convert any thrown value (axios error, Error, string, unknown) into an
 * operator-readable sentence. Unknown statuses still produce a usable message
 * that includes the status code.
 */
export const humanizeApiError = (error: unknown, context?: string): string => {
  const prefix = context ? `${context} — ` : '';

  if (typeof error === 'string' && error.trim() !== '') {
    return prefix + error;
  }

  if (error instanceof Error || isHttpLikeError(error)) {
    const status = isHttpLikeError(error) ? error.response?.status : undefined;
    if (status !== undefined) {
      const known = STATUS_MESSAGES[status];
      if (known) return prefix + known;
      return `${prefix}The request failed (status ${status}). Retry shortly; if it persists, check service logs.`;
    }

    const code = isHttpLikeError(error) ? error.code : undefined;
    if (code) {
      const networkMessage = humanizeNetworkCode(code);
      if (networkMessage) return prefix + networkMessage;
    }

    const message = error.message ?? '';
    if (message === 'Network Error') {
      return prefix + humanizeNetworkCode('ERR_NETWORK')!;
    }
    if (message.startsWith('Request failed with status code')) {
      // Defensive: status was stripped somewhere; keep the code visible but readable.
      return `${prefix}The request failed (${message.replace('Request failed with status code', 'status').trim()}). Retry shortly.`;
    }
    if (message.trim() !== '') {
      return prefix + message;
    }
  }

  return prefix + 'Something went wrong while reaching the backend. Retry in a moment.';
};

/**
 * Reduce a thrown value to fields that are safe to write to the console.
 *
 * An axios error carries the full request (`config.data`, headers) and the raw
 * response body; on credential-bearing calls that includes wallet seed
 * phrases and tokens. Log this summary instead of the error object.
 */
export const summarizeErrorForLog = (
  error: unknown
): { name?: string; message: string; status?: number; code?: string } => {
  if (typeof error === 'string') return { message: error };
  if (typeof error !== 'object' || error === null) return { message: String(error) };

  const candidate = error as {
    name?: unknown;
    message?: unknown;
    code?: unknown;
    response?: { status?: unknown };
  };
  const summary: { name?: string; message: string; status?: number; code?: string } = {
    message: typeof candidate.message === 'string' ? candidate.message : 'Unknown error',
  };
  if (typeof candidate.name === 'string') summary.name = candidate.name;
  if (typeof candidate.code === 'string') summary.code = candidate.code;
  if (typeof candidate.response?.status === 'number') summary.status = candidate.response.status;
  return summary;
};
