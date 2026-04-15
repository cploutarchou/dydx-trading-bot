import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Loader, ShieldCheck, Sparkles } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import AuthExperienceShell from '../components/AuthExperienceShell';
import { useAuthStore } from '../store/auth';

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
  });

  useEffect(() => {
    usernameInputRef.current?.focus();
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
        : 'Open evaluation';

  return (
    <AuthExperienceShell
      kicker="Welcome back"
      title="Sign in to the operator workspace"
      description="Return to your research, runtime, and command surfaces with clearer access cues and stronger fintech-grade trust messaging."
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
            Authentication and follow-up security setup happen before live workflow access.
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
              Review subscriptions first, then continue through the premium onboarding flow with the
              right access model for your desk.
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
              Start free evaluation
            </button>
          </>
        )}
      </div>
    </AuthExperienceShell>
  );
};
