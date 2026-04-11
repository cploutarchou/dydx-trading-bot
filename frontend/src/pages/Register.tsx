import { useQuery } from '@tanstack/react-query';
import { AlertCircle, CheckCircle, Loader, ShieldCheck, Sparkles } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import AuthExperienceShell from '../components/AuthExperienceShell';
import { useAuthStore } from '../store/auth';

interface ValidationErrors {
  username?: string;
  email?: string;
  invitationCode?: string;
  password?: string;
  confirmPassword?: string;
}

export const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const { register, loading, error } = useAuthStore();
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    invitationCode: '',
    password: '',
    confirmPassword: '',
    agreedToTerms: false,
  });
  const [validationErrors, setValidationErrors] = useState<ValidationErrors>({});
  const [passwordStrength, setPasswordStrength] = useState<'weak' | 'medium' | 'strong'>('weak');
  const [formError, setFormError] = useState<string | null>(null);
  const usernameInputRef = useRef<HTMLInputElement | null>(null);
  const emailInputRef = useRef<HTMLInputElement | null>(null);
  const passwordInputRef = useRef<HTMLInputElement | null>(null);
  const confirmPasswordInputRef = useRef<HTMLInputElement | null>(null);
  const invitationCodeInputRef = useRef<HTMLInputElement | null>(null);
  const termsCheckboxRef = useRef<HTMLInputElement | null>(null);
  const apiErrorAlertRef = useRef<HTMLDivElement | null>(null);
  const formErrorAlertRef = useRef<HTMLDivElement | null>(null);
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
      apiErrorAlertRef.current?.focus();
      return;
    }
    if (formError) {
      formErrorAlertRef.current?.focus();
    }
  }, [error, formError]);

  const validateForm = (): ValidationErrors => {
    const errors: ValidationErrors = {};

    if (formData.username.length < 3) {
      errors.username = 'Username must be at least 3 characters';
    } else if (!/^[a-zA-Z0-9_-]+$/.test(formData.username)) {
      errors.username = 'Username can only contain letters, numbers, hyphens, and underscores';
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      errors.email = 'Please enter a valid email address';
    }

    if (
      registrationStatusQuery.data?.invitation_required &&
      formData.invitationCode.trim().length === 0
    ) {
      errors.invitationCode = 'Invitation code is required';
    }

    if (formData.password.length < 8) {
      errors.password = 'Password must be at least 8 characters';
    } else if (!/[A-Z]/.test(formData.password)) {
      errors.password = 'Password must contain at least one uppercase letter';
    } else if (!/[0-9]/.test(formData.password)) {
      errors.password = 'Password must contain at least one number';
    }

    if (formData.password !== formData.confirmPassword) {
      errors.confirmPassword = 'Passwords do not match';
    }

    setValidationErrors(errors);
    return errors;
  };

  const calculatePasswordStrength = (password: string) => {
    if (password.length < 8) return 'weak';
    if (password.length < 12) return 'medium';
    return 'strong';
  };

  const handlePasswordChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const password = event.target.value;
    setFormData({ ...formData, password });
    setPasswordStrength(calculatePasswordStrength(password));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);

    if (registrationStatusQuery.data?.enabled === false) {
      setFormError(
        registrationStatusQuery.data.reason || 'Public registration is currently disabled.'
      );
      return;
    }

    const errors = validateForm();
    if (Object.keys(errors).length > 0) {
      if (errors.username) {
        usernameInputRef.current?.focus();
      } else if (errors.email) {
        emailInputRef.current?.focus();
      } else if (errors.invitationCode) {
        invitationCodeInputRef.current?.focus();
      } else if (errors.password) {
        passwordInputRef.current?.focus();
      } else if (errors.confirmPassword) {
        confirmPasswordInputRef.current?.focus();
      }
      return;
    }

    if (!formData.agreedToTerms) {
      setFormError('Please agree to the Terms of Service and Privacy Policy');
      termsCheckboxRef.current?.focus();
      return;
    }

    try {
      await register(
        formData.username,
        formData.email,
        formData.password,
        registrationStatusQuery.data?.invitation_required
          ? formData.invitationCode.trim()
          : undefined
      );
      navigate('/2fa-setup');
    } catch (err) {
      console.error('Registration failed:', err);
    }
  };

  return (
    <AuthExperienceShell
      kicker="Create operator access"
      title="Start a premium evaluation account"
      description="The registration flow now reads more like fintech onboarding: clearer access state, cleaner password guidance, and stronger security framing before the workspace opens."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="metric-tile px-4 py-4">
          <p className="text-[11px] uppercase text-slate-500">Registration mode</p>
          <p className="mt-2 text-sm font-semibold text-white">
            {registrationStatusQuery.data?.invitation_required ? 'Invitation required' : 'Open evaluation'}
          </p>
          <p className="mt-1 text-xs leading-5 text-slate-400">
            Account creation flows into security setup before live product use.
          </p>
        </div>
        <div className="metric-tile px-4 py-4">
          <p className="text-[11px] uppercase text-slate-500">Onboarding standard</p>
          <p className="mt-2 text-sm font-semibold text-white">Security-aware entry</p>
          <p className="mt-1 text-xs leading-5 text-slate-400">
            Password quality, invitation state, and next steps are all visible during signup.
          </p>
        </div>
      </div>

      {registrationStatusQuery.data?.enabled === false && (
        <div
          role="alert"
          aria-live="polite"
          className="mt-5 rounded-lg border border-amber-600/50 bg-amber-950/30 p-4 text-sm text-amber-200"
        >
          {registrationStatusQuery.data.reason}
        </div>
      )}

      {registrationStatusQuery.data?.invitation_required && (
        <div className="mt-5 rounded-lg border border-cyan-500/30 bg-cyan-950/30 p-4 text-sm text-cyan-200">
          This workspace is currently invite-only. Enter your invitation code to continue.
        </div>
      )}

      {error && (
        <div
          ref={apiErrorAlertRef}
          tabIndex={-1}
          role="alert"
          aria-live="assertive"
          className="mt-5 flex items-start gap-3 rounded-lg border border-red-700 bg-red-950/55 p-4"
        >
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-300" />
          <div className="text-sm text-red-200">{error}</div>
        </div>
      )}

      {formError && (
        <div
          ref={formErrorAlertRef}
          tabIndex={-1}
          role="alert"
          aria-live="assertive"
          className="mt-5 flex items-start gap-3 rounded-lg border border-red-700 bg-red-950/55 p-4"
        >
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-300" />
          <div className="text-sm text-red-200">{formError}</div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <div>
          <label htmlFor="username" className="mb-2 block text-sm font-medium text-slate-300">
            Username
          </label>
          <input
            id="username"
            name="username"
            type="text"
            ref={usernameInputRef}
            autoComplete="username"
            aria-invalid={!!validationErrors.username}
            aria-describedby={validationErrors.username ? 'username-error' : undefined}
            value={formData.username}
            onChange={(event) => setFormData({ ...formData, username: event.target.value })}
            className={`premium-input ${validationErrors.username ? 'border-red-500' : ''}`}
            placeholder="desk_operator"
            disabled={loading}
          />
          {validationErrors.username && (
            <p id="username-error" className="mt-1 text-xs text-red-300">
              {validationErrors.username}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="email" className="mb-2 block text-sm font-medium text-slate-300">
            Email address
          </label>
          <input
            id="email"
            name="email"
            type="email"
            ref={emailInputRef}
            autoComplete="email"
            aria-invalid={!!validationErrors.email}
            aria-describedby={validationErrors.email ? 'email-error' : undefined}
            value={formData.email}
            onChange={(event) => setFormData({ ...formData, email: event.target.value })}
            className={`premium-input ${validationErrors.email ? 'border-red-500' : ''}`}
            placeholder="operator@example.com"
            disabled={loading}
          />
          {validationErrors.email && (
            <p id="email-error" className="mt-1 text-xs text-red-300">
              {validationErrors.email}
            </p>
          )}
        </div>

        {registrationStatusQuery.data?.invitation_required && (
          <div>
            <label htmlFor="invitationCode" className="mb-2 block text-sm font-medium text-slate-300">
              Invitation code
            </label>
            <input
              id="invitationCode"
              name="invitationCode"
              type="text"
              ref={invitationCodeInputRef}
              aria-invalid={!!validationErrors.invitationCode}
              aria-describedby={
                validationErrors.invitationCode ? 'invitation-code-error' : undefined
              }
              value={formData.invitationCode}
              onChange={(event) =>
                setFormData({ ...formData, invitationCode: event.target.value })
              }
              className={`premium-input ${validationErrors.invitationCode ? 'border-red-500' : ''}`}
              placeholder="Enter invitation code"
              disabled={loading}
            />
            {validationErrors.invitationCode && (
              <p id="invitation-code-error" className="mt-1 text-xs text-red-300">
                {validationErrors.invitationCode}
              </p>
            )}
          </div>
        )}

        <div>
          <label htmlFor="password" className="mb-2 block text-sm font-medium text-slate-300">
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            ref={passwordInputRef}
            autoComplete="new-password"
            aria-invalid={!!validationErrors.password}
            aria-describedby={validationErrors.password ? 'password-error' : 'password-help'}
            value={formData.password}
            onChange={handlePasswordChange}
            className={`premium-input ${validationErrors.password ? 'border-red-500' : ''}`}
            placeholder="Create a strong password"
            disabled={loading}
          />
          {formData.password && (
            <div className="mt-3 flex items-center gap-3">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
                <div
                  className={`h-full rounded-full transition-all ${
                    passwordStrength === 'weak'
                      ? 'w-1/3 bg-red-500'
                      : passwordStrength === 'medium'
                        ? 'w-2/3 bg-amber-400'
                        : 'w-full bg-emerald-400'
                  }`}
                />
              </div>
              <span className="text-xs font-medium text-slate-400">
                {passwordStrength.charAt(0).toUpperCase() + passwordStrength.slice(1)}
              </span>
            </div>
          )}
          {validationErrors.password && (
            <p id="password-error" className="mt-1 text-xs text-red-300">
              {validationErrors.password}
            </p>
          )}
          <p id="password-help" className="mt-2 text-xs text-slate-500">
            Use at least 8 characters, one uppercase letter, and one number.
          </p>
        </div>

        <div>
          <label htmlFor="confirmPassword" className="mb-2 block text-sm font-medium text-slate-300">
            Confirm password
          </label>
          <input
            id="confirmPassword"
            name="confirmPassword"
            type="password"
            ref={confirmPasswordInputRef}
            autoComplete="new-password"
            aria-invalid={!!validationErrors.confirmPassword}
            aria-describedby={
              validationErrors.confirmPassword ? 'confirm-password-error' : undefined
            }
            value={formData.confirmPassword}
            onChange={(event) =>
              setFormData({ ...formData, confirmPassword: event.target.value })
            }
            className={`premium-input ${validationErrors.confirmPassword ? 'border-red-500' : ''}`}
            placeholder="Repeat your password"
            disabled={loading}
          />
          {formData.confirmPassword && formData.password === formData.confirmPassword && (
            <div className="mt-2 flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-emerald-400" />
              <span className="text-xs text-emerald-400">Passwords match</span>
            </div>
          )}
          {validationErrors.confirmPassword && (
            <p id="confirm-password-error" className="mt-1 text-xs text-red-300">
              {validationErrors.confirmPassword}
            </p>
          )}
        </div>

        <div className="signal-card px-4 py-4">
          <div className="flex items-start gap-3">
            <input
              type="checkbox"
              id="terms"
              ref={termsCheckboxRef}
              checked={formData.agreedToTerms}
              onChange={(event) =>
                setFormData({ ...formData, agreedToTerms: event.target.checked })
              }
              className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-900 text-cyan-500 focus:ring-cyan-500"
              disabled={loading}
            />
            <label htmlFor="terms" className="text-xs leading-6 text-slate-400">
              I agree to the{' '}
              <span className="font-medium text-cyan-300">
                Terms of Service
              </span>{' '}
              and{' '}
              <span className="font-medium text-cyan-300">
                Privacy Policy
              </span>
              . I understand the account will continue into security setup before I reach the live
              workspace.
            </label>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading || registrationStatusQuery.data?.enabled === false}
          className="premium-button premium-button-primary mt-2 w-full disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading && <Loader className="h-4 w-4 animate-spin" />}
          {loading ? 'Creating account...' : 'Create evaluation account'}
        </button>
      </form>

      <div className="signal-card mt-6 px-4 py-4">
        <div className="flex items-start gap-3 text-sm text-slate-300">
          <ShieldCheck className="mt-0.5 h-4 w-4 text-cyan-300" />
          <p>
            The next step after registration is security setup. The flow is designed to make access
            readiness explicit before the operator reaches live controls.
          </p>
        </div>
      </div>

      <div className="mt-6 flex items-center justify-center gap-2 text-center text-sm text-slate-400">
        <Sparkles className="h-4 w-4 text-cyan-300" />
        Already have an account?
        <button
          type="button"
          onClick={() => navigate('/login')}
          className="font-medium text-cyan-300 hover:text-cyan-200 hover:underline"
        >
          Sign in
        </button>
      </div>
    </AuthExperienceShell>
  );
};
