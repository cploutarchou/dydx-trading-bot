/**
 * Compatibility shim for the legacy auth store.
 *
 * The active application routing and session bootstrap use `src/store/auth.ts`.
 * Re-exporting that store here prevents a second divergent auth implementation
 * from drifting out of sync with the live app.
 */

export { useAuthStore } from './auth';
export { useAuthStore as default } from './auth';
