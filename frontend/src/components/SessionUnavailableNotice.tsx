/**
 * Session Unavailable Notice
 *
 * Rendered by the route guards instead of the login redirect when the session
 * bootstrap failed without a backend rejection: the server session is
 * untouched, so the user has not been signed out. Retry re-runs the session
 * bootstrap. Sign out is the only path from here that ends the server
 * session, and it is the user's explicit choice.
 */

import { useId } from 'react';
import { useAuthStore } from '../store/auth';

export const SessionUnavailableNotice = () => {
  const headingId = useId();
  const initializeSession = useAuthStore((state) => state.initializeSession);
  const logout = useAuthStore((state) => state.logout);
  const sessionLoading = useAuthStore((state) => state.sessionLoading);

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-6">
      <section
        role="alert"
        aria-labelledby={headingId}
        className="w-full max-w-md rounded-2xl border border-amber-500/40 bg-amber-500/10 p-6 text-left"
      >
        <h1 id={headingId} className="text-lg font-semibold text-amber-200">
          Connection problem
        </h1>
        <p className="mt-2 text-sm text-slate-200">
          We could not reach the server to confirm your session. You have not been signed out. The
          page keeps retrying; you can also retry now or sign out.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => {
              void initializeSession();
            }}
            disabled={sessionLoading}
            className="rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {sessionLoading ? 'Retrying…' : 'Retry now'}
          </button>
          <button
            type="button"
            onClick={logout}
            className="rounded-lg border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-800"
          >
            Sign out
          </button>
        </div>
      </section>
    </div>
  );
};
