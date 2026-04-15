import { useQuery } from '@tanstack/react-query';
import { AlertCircle, Loader, LockKeyhole } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { useAuthStore } from '../store/auth';
import { isRegistrationDisabledByAdministrator } from '../utils/registrationStatus';

export const RegistrationDisabledLoginGate: React.FC = () => {
  const navigate = useNavigate();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
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
    enabled: !isAuthenticated,
  });

  const shouldGate =
    !isAuthenticated && isRegistrationDisabledByAdministrator(registrationStatusQuery.data);
  const visibleError = error;

  useEffect(() => {
    if (shouldGate) {
      usernameInputRef.current?.focus();
    }
  }, [shouldGate]);

  useEffect(() => {
    if (visibleError) {
      errorAlertRef.current?.focus();
    }
  }, [visibleError]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    try {
      await login(username, password);
      navigate('/dashboard');
    } catch (loginError) {
      console.error('Login failed:', loginError);
    }
  };

  if (!shouldGate) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 py-8 backdrop-blur-md">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="registration-disabled-login-title"
        className="w-full max-w-md rounded-lg border border-slate-700 bg-slate-900/95 p-6 shadow-2xl shadow-black/50"
      >
        <div className="mb-5 flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-cyan-500/40 bg-cyan-500/10 text-cyan-300">
            <LockKeyhole className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs uppercase text-slate-500">Credential access only</p>
            <h2
              id="registration-disabled-login-title"
              className="mt-1 text-xl font-semibold text-white"
            >
              Sign in to continue
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Public registration is currently disabled by the administrator.
            </p>
          </div>
        </div>

        {visibleError && (
          <div
            ref={errorAlertRef}
            tabIndex={-1}
            role="alert"
            aria-live="assertive"
            className="mb-4 flex items-start gap-3 rounded-lg border border-red-700 bg-red-950/55 p-3 text-sm text-red-200"
          >
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-300" />
            <span>{visibleError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="gate-login-username"
              className="mb-2 block text-sm font-medium text-slate-300"
            >
              Username
            </label>
            <input
              id="gate-login-username"
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
              htmlFor="gate-login-password"
              className="mb-2 block text-sm font-medium text-slate-300"
            >
              Password
            </label>
            <input
              id="gate-login-password"
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
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </section>
    </div>
  );
};
