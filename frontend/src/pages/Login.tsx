import { LockKeyhole } from 'lucide-react';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { BACKOFFICE_ROLES, IB_ROLES, getUserWorkspaceRole } from '../auth/roles';
import BrandMark from '../components/BrandMark';
import { CryptoBackground } from '../components/CryptoBackground';
import {
  FormField,
  PasswordField,
  PrimaryButton,
  PublicStatusPill,
} from '../components/PublicPagePrimitives';
import { useAuthStore } from '../store/auth';
import { canSubmitLoginForm, getLoginFormErrors } from '../utils/loginForm';
import { perfMark, perfMeasure } from '../utils/perf';

const AUTH_ERROR_COPY =
  'Unable to sign in with those credentials. Check your details and try again.';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login, loading, error, mfaChallengeRequired, completeMfaChallenge, cancelMfaChallenge } =
    useAuthStore();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [mfaCode, setMfaCode] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const usernameInputRef = useRef<HTMLInputElement | null>(null);
  const errorAlertRef = useRef<HTMLDivElement | null>(null);

  const formErrors = getLoginFormErrors({ username, password });
  const usernameError = submitted ? formErrors.username : '';
  const passwordError = submitted ? formErrors.password : '';
  const isSubmitDisabled = !canSubmitLoginForm({ username, password, loading });
  const supportHref = useMemo(() => {
    const subject = encodeURIComponent('ExecutionLab account recovery request');
    const body = encodeURIComponent(
      'Hello ExecutionLab team,\n\nI need help recovering access to my account.\n'
    );
    return `mailto:support@executionlab.io?subject=${subject}&body=${body}`;
  }, []);

  useEffect(() => {
    usernameInputRef.current?.focus();
  }, []);

  useEffect(() => {
    const animationFrameId = window.requestAnimationFrame(() => {
      perfMark('login-page:rendered');
      perfMeasure('boot->login-page:rendered', 'boot:start', 'login-page:rendered');
    });

    return () => window.cancelAnimationFrame(animationFrameId);
  }, []);

  useEffect(() => {
    if (error) {
      errorAlertRef.current?.focus();
    }
  }, [error]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);

    if (username.trim().length === 0 || password.length === 0) {
      return;
    }

    try {
      await login(username.trim(), password);

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
    } catch {
      // The auth store owns state; avoid logging credential-related responses here.
    }
  };

  const handleMfaSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const code = mfaCode.replace(/\D/g, '');
    if (code.length !== 6) {
      return;
    }
    try {
      await completeMfaChallenge(code);

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
    } catch {
      // Store surfaces the invalid-code message; keep values for retry.
    }
  };

  if (mfaChallengeRequired) {
    return (
      <main className="public-page-shell relative isolate flex min-h-screen items-start overflow-x-hidden bg-[#050816] px-4 py-8 text-white sm:px-6">
        <CryptoBackground variant="login" />
        <section className="auth-column relative z-10 mx-auto w-full">
          <Link to="/" className="inline-flex">
            <BrandMark subtitle="Controlled access" />
          </Link>

          <div className="mt-7 public-auth-panel">
            <PublicStatusPill tone="info" icon={LockKeyhole}>
              Two-factor verification
            </PublicStatusPill>

            <div className="mt-6">
              <h1 className="text-[clamp(2.25rem,5vw,2.75rem)] font-semibold leading-tight tracking-normal text-white">
                Enter your authenticator code
              </h1>
              <p className="mt-3 text-base leading-7 text-slate-300">
                Enter the 6-digit code from your authenticator app to finish signing in.
              </p>
            </div>

            {error && (
              <div
                ref={errorAlertRef}
                tabIndex={-1}
                role="alert"
                aria-live="assertive"
                className="mt-5 rounded-lg border border-rose-500/35 bg-rose-950/55 p-4 text-sm leading-6 text-rose-100"
              >
                {error}
              </div>
            )}

            <form onSubmit={handleMfaSubmit} className="mt-6 space-y-5" noValidate>
              <FormField
                id="login-mfa-code"
                label="Authenticator code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={mfaCode}
                onChange={(event) => setMfaCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="123456"
                disabled={loading}
                autoFocus
                required
              />

              <PrimaryButton
                type="submit"
                disabled={loading || mfaCode.replace(/\D/g, '').length !== 6}
                loading={loading}
                className="min-h-12 w-full"
              >
                {loading ? 'Verifying...' : 'Verify and sign in'}
              </PrimaryButton>
            </form>

            <div className="mt-5 text-sm">
              <button
                type="button"
                onClick={() => {
                  cancelMfaChallenge();
                  setMfaCode('');
                }}
                className="font-medium text-slate-300 hover:text-white"
              >
                &larr; Back to sign in
              </button>
            </div>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="public-page-shell relative isolate flex min-h-screen items-start overflow-x-hidden bg-[#050816] px-4 py-8 text-white sm:px-6">
      <CryptoBackground variant="login" />
      <section className="auth-column relative z-10 mx-auto w-full">
        <Link to="/" className="inline-flex">
          <BrandMark subtitle="Controlled access" />
        </Link>

        <div className="mt-7 public-auth-panel">
          <div className="flex items-center justify-between gap-4">
            <PublicStatusPill tone="info" icon={LockKeyhole}>
              Existing credentials only
            </PublicStatusPill>
          </div>

          <div className="mt-6">
            <h1 className="text-[clamp(2.25rem,5vw,2.75rem)] font-semibold leading-tight tracking-normal text-white">
              Sign in
            </h1>
            <p className="mt-3 text-base leading-7 text-slate-300">
              Use an approved account to enter the ExecutionLab workspace.
            </p>
          </div>

          {error && (
            <div
              ref={errorAlertRef}
              tabIndex={-1}
              role="alert"
              aria-live="assertive"
              className="mt-5 rounded-lg border border-rose-500/35 bg-rose-950/55 p-4 text-sm leading-6 text-rose-100"
            >
              {AUTH_ERROR_COPY}
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-6 space-y-5" noValidate>
            <FormField
              id="login-username"
              label="Username or email"
              type="text"
              autoComplete="username"
              inputRef={usernameInputRef}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="name@company.com"
              error={usernameError}
              disabled={loading}
              required
            />

            <PasswordField
              id="login-password"
              label="Password"
              value={password}
              error={passwordError}
              disabled={loading}
              showPassword={showPassword}
              onShowPasswordChange={setShowPassword}
              onChange={(event) => setPassword(event.target.value)}
            />

            <PrimaryButton
              type="submit"
              disabled={isSubmitDisabled}
              loading={loading}
              className="min-h-12 w-full"
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </PrimaryButton>
          </form>

          <div className="mt-5 flex flex-col gap-3 text-sm sm:flex-row sm:items-center sm:justify-between">
            <a href={supportHref} className="font-medium text-cyan-200 hover:text-cyan-100">
              Account recovery
            </a>
            <Link to="/" className="font-medium text-slate-300 hover:text-white">
              Return to launch page
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
};
