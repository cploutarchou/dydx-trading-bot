/**
 * An API failure that keeps the HTTP status and the backend error code.
 *
 * Most api.ts methods rethrow a plain Error with the human message only. Some
 * screens must branch on the backend code instead (for example a 409 that asks
 * for an explicit acknowledgement before a save), so those methods throw this
 * error. It lives outside api.ts so component tests that mock the api module
 * can still build and recognise it.
 */
export class ApiRequestError extends Error {
  readonly status: number | null;
  readonly code: string | null;

  constructor(message: string, status: number | null, code: string | null) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.code = code;
  }
}

/** The backend error code of a failed request, or null when it carried none. */
export const getApiErrorCode = (error: unknown): string | null =>
  error instanceof ApiRequestError ? error.code : null;
