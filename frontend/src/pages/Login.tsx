import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { ArrowLeft, ArrowRight, Loader, ShieldCheck, Sparkles } from 'lucide-react';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { BACKOFFICE_ROLES, IB_ROLES, getUserWorkspaceRole } from '../auth/roles';
import AuthExperienceShell from '../components/AuthExperienceShell';
import { comingSoonMarketingContent } from '../content/publicSite';
import { useAuthStore } from '../store/auth';
import { perfMark, perfMeasure } from '../utils/perf';

type EntryMode = 'operator' | 'research' | 'security';

const entryModes: Array<{ id: EntryMode; label: string }> = [
  { id: 'operator', label: 'Operator mode' },
  { id: 'research', label: 'Research mode' },
  { id: 'security', label: 'Security mode' },
];

const entryModeContent: Record<
  EntryMode,
  {
    title: string;
    detail: string;
    signalA: string;
    signalB: string;
    submitLabel: string;
  }
> = {
  operator: {
    title: 'Execution-first entry',
    detail: 'Use your operator credentials to continue into runtime and monitoring surfaces.',
    signalA: 'Runtime aware',
    signalB: 'Decision ready',
    submitLabel: 'Enter workspace',
  },
  research: {
    title: 'Analysis-first entry',
    detail: 'Resume experiments, backtest reviews, and strategy validation with contextual access.',
    signalA: 'Backtest context',
    signalB: 'Signal traceable',
    submitLabel: 'Continue to research',
  },
  security: {
    title: 'Security-first entry',
    detail:
      'Verify account state first, then move into workspace controls and sensitive workflows.',
    signalA: 'MFA aligned',
    signalB: 'Role scoped',
    submitLabel: 'Proceed securely',
  },
};

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login, loading, error } = useAuthStore();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [entryMode, setEntryMode] = useState<EntryMode>('operator');
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
    enabled: true,
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
  const activeEntryMode = useMemo(() => entryModeContent[entryMode], [entryMode]);
  const getEntryPillClass = (isActive: boolean): string =>
    `fintech-pill px-3 py-2 text-xs font-semibold sm:text-sm ${isActive ? 'is-active' : ''}`;

  if (comingSoonEnabled) {
    return (
      <main className="premium-shell light-dark-surface coming-soon-surface min-h-screen text-white">
        <div className="mx-auto flex min-h-screen w-full max-w-7xl items-center px-4 py-6 sm:px-6 lg:px-8">
          <section className="grid w-full gap-6 py-10 lg:grid-cols-2 lg:py-12">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, ease: 'easeOut' }}
              className="relative overflow-hidden rounded-2xl border border-slate-700/70 bg-slate-950/70 p-6 shadow-[0_20px_60px_-30px_rgba(0,0,0,0.75)] sm:p-7 lg:p-8"
            >
              <motion.div
                aria-hidden="true"
                className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-cyan-500/10 blur-3xl"
                animate={{ scale: [1, 1.08, 1], opacity: [0.35, 0.55, 0.35] }}
                transition={{ duration: 7, repeat: Infinity, ease: 'easeInOut' }}
              />

              <div className="surface-label">
                <ShieldCheck className="h-3.5 w-3.5" />
                Simple access
              </div>

              <h1 className="fintech-heading mt-5 text-3xl font-semibold text-white sm:text-4xl">
                Use existing credentials to continue.
              </h1>

              <p className="fintech-copy coming-soon-muted mt-4 text-sm sm:text-base">
                The workspace is hidden while launch is paused. Use an approved account to continue.
              </p>

              <div className="coming-soon-muted mt-5 border-l-2 border-cyan-500/45 pl-4 text-sm text-slate-300">
                Only sign-in and required account recovery pages remain available.
              </div>

              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1, duration: 0.3 }}
                className="launch-announcement-pill mt-4"
              >
                Crypto launch signal • {comingSoonMarketingContent.icoAnnouncement}
              </motion.div>

              <div className="mt-4">
                <button
                  type="button"
                  onClick={() => navigate('/ico')}
                  className="premium-button premium-button-secondary inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm"
                >
                  View ICO briefing
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>

              <div className="fintech-flow-divider mt-5 pt-4">
                <p className="fintech-kicker">Entry profile</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {entryModes.map((mode) => {
                    const isActive = mode.id === entryMode;
                    return (
                      <motion.button
                        key={mode.id}
                        type="button"
                        onClick={() => setEntryMode(mode.id)}
                        whileHover={{ y: -1, scale: 1.01 }}
                        whileTap={{ scale: 0.99 }}
                        className={getEntryPillClass(isActive)}
                      >
                        {mode.label}
                      </motion.button>
                    );
                  })}
                </div>
              </div>

              <div className="mt-4 border-l-2 border-violet-500/35 pl-4">
                <p className="text-sm font-semibold text-white">{activeEntryMode.title}</p>
                <p className="fintech-copy mt-1 text-xs sm:text-sm">{activeEntryMode.detail}</p>
              </div>

              <div className="fintech-flow-divider coming-soon-login-helper mt-5 flex flex-col items-start gap-2 pt-4 text-sm text-slate-300 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                <span>Launch is paused for the public site.</span>
                <span>Existing credentials only.</span>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.06, duration: 0.35, ease: 'easeOut' }}
              className="space-y-5 rounded-2xl border border-slate-700/70 bg-slate-950/70 p-6 shadow-[0_20px_60px_-30px_rgba(0,0,0,0.75)] sm:p-7 lg:p-8"
            >
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="fintech-soft-strip fintech-micro-glow px-4 py-3">
                  <p className="text-[11px] uppercase text-slate-500">Access state</p>
                  <p className="mt-2 text-sm font-semibold text-white">{registrationMode}</p>
                  <p className="mt-1 text-xs leading-5 text-slate-400">
                    Sign-in remains available for existing operators.
                  </p>
                </div>
                <div className="fintech-soft-strip fintech-micro-glow px-4 py-3">
                  <p className="text-[11px] uppercase text-slate-500">Security posture</p>
                  <p className="mt-2 text-sm font-semibold text-white">Account-first entry</p>
                  <p className="mt-1 text-xs leading-5 text-slate-400">
                    Authentication and follow-up security setup happen before execution access.
                  </p>
                </div>
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

              <form onSubmit={handleSubmit} className="space-y-4">
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
                  {loading ? 'Signing in...' : activeEntryMode.submitLabel}
                </button>
              </form>

              <div className="flex justify-end pt-1">
                <button
                  type="button"
                  onClick={() => navigate('/dashboard')}
                  className="premium-button premium-button-secondary dashboard-back-action inline-flex items-center gap-2 justify-center px-4 py-2.5 text-sm"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back to dashboard
                </button>
              </div>
            </motion.div>
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

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="fintech-soft-strip fintech-micro-glow px-4 py-3">
          <p className="text-[11px] uppercase text-slate-500">Access state</p>
          <p className="mt-2 text-sm font-semibold text-white">{registrationMode}</p>
          <p className="mt-1 text-xs leading-5 text-slate-400">
            Sign-in remains available for existing operators.
          </p>
        </div>
        <div className="fintech-soft-strip fintech-micro-glow px-4 py-3">
          <p className="text-[11px] uppercase text-slate-500">Security posture</p>
          <p className="mt-2 text-sm font-semibold text-white">Account-first entry</p>
          <p className="mt-1 text-xs leading-5 text-slate-400">
            Authentication and follow-up security setup happen before execution workflow access.
          </p>
        </div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        className="fintech-soft-strip mt-4 px-4 py-4 sm:px-5"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="fintech-kicker">Session entry profile</p>
          <div className="fintech-pill inline-flex items-center gap-2 border-emerald-500/35 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-emerald-200">
            Stable path
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {entryModes.map((mode) => {
            const isActive = mode.id === entryMode;
            return (
              <motion.button
                key={mode.id}
                type="button"
                onClick={() => setEntryMode(mode.id)}
                whileHover={{ y: -1, scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
                className={getEntryPillClass(isActive)}
              >
                {mode.label}
              </motion.button>
            );
          })}
        </div>

        <div className="fintech-flow-divider mt-3 pt-3">
          <div className="flex flex-wrap items-center gap-2 text-xs sm:text-sm">
            <span className="text-slate-500">Profile:</span>
            <span className="font-semibold text-white">{activeEntryMode.title}</span>
            <span className="mx-1 text-slate-600">•</span>
            <span className="font-semibold text-cyan-200">{activeEntryMode.signalA}</span>
            <span className="mx-1 text-slate-600">•</span>
            <span className="font-semibold text-violet-200">{activeEntryMode.signalB}</span>
          </div>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.06, duration: 0.35, ease: 'easeOut' }}
        className="launch-announcement-pill mt-4 w-full"
      >
        {comingSoonMarketingContent.icoAnnouncement}
      </motion.div>

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
          <p className="login-support-copy mt-2 text-xs text-slate-500">{activeEntryMode.detail}</p>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="premium-button premium-button-primary w-full disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading && <Loader className="h-4 w-4 animate-spin" />}
          {loading ? 'Signing in...' : activeEntryMode.submitLabel}
        </button>
      </form>

      <div className="mt-4 flex justify-end">
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="premium-button premium-button-secondary dashboard-back-action inline-flex items-center gap-2 justify-center px-4 py-2.5 text-sm"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to dashboard
        </button>
      </div>

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
