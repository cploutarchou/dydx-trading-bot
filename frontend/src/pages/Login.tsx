import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Loader } from 'lucide-react';
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(username, password);
      navigate('/dashboard');
    } catch (err) {
      console.error('❌ LoginPage: Error during login:', err);
    }
  };

  return (
    <AuthExperienceShell
      kicker="Welcome back"
      title="Sign in to your arbitrage workspace"
      description="Access your subscriptions, live execution surfaces, backtest intelligence, and operator telemetry from one premium DeFi cockpit."
    >
      {error && (
        <div
          ref={errorAlertRef}
          tabIndex={-1}
          role="alert"
          aria-live="assertive"
          className="mb-4 rounded-2xl border border-red-700 bg-red-950/55 p-4 text-red-200"
        >
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="login-username" className="block text-sm font-medium text-slate-300 mb-2">
            Username
          </label>
          <input
            id="login-username"
            type="text"
            autoComplete="username"
            ref={usernameInputRef}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="premium-input"
            required
          />
        </div>

        <div>
          <label htmlFor="login-password" className="block text-sm font-medium text-slate-300 mb-2">
            Password
          </label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="premium-input"
            required
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="premium-button premium-button-primary w-full disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading && <Loader className="w-4 h-4 animate-spin" />}
          {loading ? 'Logging in...' : 'Enter Workspace'}
        </button>
      </form>

      <div className="mt-6 rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Need access?</p>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <p className="max-w-sm text-sm text-slate-400">
            Choose a subscription path first, then enter the platform through a premium onboarding
            flow.
          </p>
          <button
            type="button"
            onClick={() => navigate('/pricing')}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-700 hover:text-white"
          >
            View subscriptions
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      <p className="mt-5 text-center text-sm text-slate-400">
        {registrationStatusQuery.data?.mode === 'invitation_only' ? (
          <>
            Registration is invitation-only right now.{' '}
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
            Don&apos;t have an account?{' '}
            <button
              type="button"
              onClick={() => navigate('/register')}
              className="font-medium text-cyan-300 hover:text-cyan-200"
            >
              Start your evaluation
            </button>
          </>
        )}
      </p>
    </AuthExperienceShell>
  );
};
