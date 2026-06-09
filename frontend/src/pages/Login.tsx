import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Loader, ShieldCheck, Sparkles } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { BACKOFFICE_ROLES, IB_ROLES, getUserWorkspaceRole } from '../auth/roles';
import AuthExperienceShell from '../components/AuthExperienceShell';
import { useAuthStore } from '../store/auth';
import { perfMark, perfMeasure } from '../utils/perf';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login, loading, error } = useAuthStore();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const usernameInputRef = useRef<HTMLInputElement | null>(null);
  const errorAlertRef = useRef<HTMLDivElement | null>(null);
  const registrationStatusQuery = useQuery({
    queryKey: ['auth', 'registration-status'],
    queryFn: async () => {
      const response = await api.getRegistrationStatus();
      return response.data;
    },
    staleTime: 60_000,
    // RegistrationDisabledLoginGate owns this fetch on /login and /register.
    // Keep LoginPage subscribed to cached data without issuing a second request.
    enabled: false,
  });
  const appConfigQuery = useQuery({
    queryKey: ['public', 'app-config'],
    queryFn: async () => {
      const response = await api.getPublicAppConfig();
      return response.data;
    },
    staleTime: 30_000,
    enabled: false,
  });

  useEffect(() => {
    usernameInputRef.current?.focus();
  }, []);

  useEffect(() => {
    const animationFrameId = window.requestAnimationFrame(() => {
      perfMark('login-page:rendered');
      perfMeasure('boot->login-page:rendered', 'boot:start', 'login-page:rendered');
    });

    return () => {
      window.cancelAnimationFrame(animationFrameId);
    };
  }, []);

  useEffect(() => {
    if (error) {
      errorAlertRef.current?.focus();
    }
  }, [error]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    try {
      await login(username, password);

      const authenticatedUser = useAuthStore.getState().user;
      const workspaceRole = getUserWorkspaceRole(authenticatedUser);

      if (BACKOFFICE_ROLES.includes(workspaceRole)) {
        navigate('/admin');
        return;
      }

      if (IB_ROLES.includes(workspaceRole)) {
        navigate('/ib-portal');
        return;
      }

      navigate('/dashboard');
    } catch (err) {
      console.error('Login failed:', err);
    }
  };

  const registrationMode =
    registrationStatusQuery.data?.mode === 'invitation_only'
      ? 'Invitation only'
      : registrationStatusQuery.data?.enabled === false
        ? 'Registration paused'
        : 'Open review';

  const comingSoonEnabled = appConfigQuery.data?.coming_soon_enabled === true;

  if (comingSoonEnabled) {
    return (
      <main className="premium-shell min-h-screen text-white">
        <div className="mx-auto flex min-h-screen w-full max-w-md items-center px-4 py-8 sm:px-6 lg:px-8">
          <section className="w-full rounded-2xl border border-slate-700 bg-slate-900/90 p-6 shadow-2xl shadow-black/40 backdrop-blur">
            <div className="surface-label">
              <ShieldCheck className="h-3.5 w-3.5" />
              Coming soon access
            </div>

            <h1 className="mt-5 text-3xl font-semibold leading-tight text-white sm:text-4xl">
              Sign in with existing credentials
            </h1>

            <p className="mt-4 text-sm leading-6 text-slate-400 sm:text-base">
              The workspace is hidden while launch is paused. Use an approved account to continue.
            </p>

            <div className="mt-5 rounded-lg border border-slate-700 bg-slate-950/60 px-4 py-3 text-sm text-slate-300">
              Only sign-in and required account recovery pages remain available.
            </div>

            {error && (
              <div
                ref={errorAlertRef}
                tabIndex={-1}
                role="alert"
                aria-live="assertive"
                className="mt-5 rounded-lg border border-red-700 bg-red-950/55 p-4 text-red-200"
              >
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              <div>
                <label
                  htmlFor="login-username"
                  className="mb-2 block text-sm font-medium text-slate-300"
                >
                  Username
                </label>
                <input
                  id="login-username"
                  type="text"
                  autoComplete="username"
                  ref={usernameInputRef}
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  className="premium-input"
                  placeholder="Enter your operator username"
                  required
                />
              </div>

              <div>
                <label
                  htmlFor="login-password"
                  className="mb-2 block text-sm font-medium text-slate-300"
                >
                  Password
                </label>
                <input
                  id="login-password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="premium-input"
                  placeholder="Enter your password"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="premium-button premium-button-primary w-full disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading && <Loader className="h-4 w-4 animate-spin" />}
                {loading ? 'Signing in...' : 'Enter workspace'}
              </button>
            </form>

            <div className="mt-5 flex items-center justify-between gap-3 text-xs text-slate-500">
              <span>Launch is paused for the public site.</span>
              <span>Existing credentials only.</span>
            </div>
          </section>
        </div>
      </main>
    );
  }

  return (
    <AuthExperienceShell
      kicker="Welcome back"
      title="Sign in to the execution workspace"
      description="Return to research, automation, runtime, and command surfaces with clear access cues and disciplined technical trust messaging."
    >
      {error && (
        <div
          ref={errorAlertRef}
          tabIndex={-1}
          role="alert"
          aria-live="assertive"
          className="mb-5 rounded-lg border border-red-700 bg-red-950/55 p-4 text-red-200"
        >
          {error}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="metric-tile px-4 py-4">
          <p className="text-[11px] uppercase text-slate-500">Access state</p>
          <p className="mt-2 text-sm font-semibold text-white">{registrationMode}</p>
          <p className="mt-1 text-xs leading-5 text-slate-400">
            Sign-in remains available for existing operators.
          </p>
        </div>
        <div className="metric-tile px-4 py-4">
          <p className="text-[11px] uppercase text-slate-500">Security posture</p>
          <p className="mt-2 text-sm font-semibold text-white">Account-first entry</p>
          <p className="mt-1 text-xs leading-5 text-slate-400">
            Authentication and follow-up security setup happen before execution workflow access.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <div>
          <label htmlFor="login-username" className="mb-2 block text-sm font-medium text-slate-300">
            Username
          </label>
          <input
            id="login-username"
            type="text"
            autoComplete="username"
            ref={usernameInputRef}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            className="premium-input"
            placeholder="Enter your operator username"
            required
          />
        </div>

        <div>
          <label htmlFor="login-password" className="mb-2 block text-sm font-medium text-slate-300">
            Password
          </label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="premium-input"
            placeholder="Enter your password"
            required
          />
          <p className="mt-2 text-xs text-slate-500">
            Operators move through account checks before reaching the workspace.
          </p>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="premium-button premium-button-primary w-full disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading && <Loader className="h-4 w-4 animate-spin" />}
          {loading ? 'Signing in...' : 'Enter workspace'}
        </button>
      </form>

      <div className="signal-card mt-6 px-4 py-4">
        <div className="grid gap-4 sm:grid-cols-[1fr,auto] sm:items-center">
          <div>
            <div className="flex items-center gap-2 text-cyan-300">
              <ShieldCheck className="h-4 w-4" />
              <p className="text-sm font-semibold text-white">Need a new operator account?</p>
            </div>
            <p className="mt-2 max-w-md text-sm leading-6 text-slate-400">
              Review engagement options first, then continue through the premium onboarding flow
              with the right access model for your work.
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate('/pricing')}
            className="premium-button premium-button-secondary justify-center px-4 py-3 text-sm"
          >
            Explore plans
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="mt-6 flex items-center justify-center gap-2 text-center text-sm text-slate-400">
        <Sparkles className="h-4 w-4 text-cyan-300" />
        {registrationStatusQuery.data?.mode === 'invitation_only' ? (
          <>
            Registration is invitation-only right now.
            <button
              type="button"
              onClick={() => navigate('/register')}
              className="font-medium text-cyan-300 hover:text-cyan-200"
            >
              Register with an invitation
            </button>
          </>
        ) : registrationStatusQuery.data?.enabled === false ? (
          <span className="text-slate-500">
            Public registration is currently disabled by the administrator.
          </span>
        ) : (
          <>
            Don&apos;t have an account?
            <button
              type="button"
              onClick={() => navigate('/register')}
              className="font-medium text-cyan-300 hover:text-cyan-200"
            >
              Start execution review
            </button>
          </>
        )}
      </div>
    </AuthExperienceShell>
  );
};
