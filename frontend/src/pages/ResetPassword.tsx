import { ShieldCheck } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { AuthExperienceShell } from '../components/AuthExperienceShell';
import { FormField, PasswordField, PrimaryButton } from '../components/PublicPagePrimitives';
import api from '../api';

/**
 * FE-009: consume an emailed reset token and choose a new password. On
 * success every active session for the account is revoked server-side, so
 * the user signs in again with the new password.
 */
export const ResetPasswordPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') ?? '';

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tokenMissing = token.length === 0;
  const passwordError =
    submitted && newPassword.length < 8 ? 'Use at least 8 characters' : '';
  const confirmError =
    submitted && confirmPassword !== newPassword ? 'Passwords do not match' : '';
  const canSubmit = !tokenMissing && newPassword.length >= 8 && newPassword === confirmPassword;

  useEffect(() => {
    if (tokenMissing) {
      setError('This link is missing its reset token. Request a new reset email.');
    }
  }, [tokenMissing]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
    if (!canSubmit) return;

    try {
      setLoading(true);
      setError(null);
      await api.resetPassword(token, newPassword);
      navigate('/login?reset=success', { replace: true });
    } catch {
      setError(
        'This reset link is invalid, already used, or expired. Request a new reset email.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthExperienceShell
      kicker="Account recovery"
      title="Choose a new password"
      description="Your reset link is single-use. After saving, every active session for the account is signed out."
      sideLabel="Password reset"
      sideTitle="One link, one new password."
      sideDescription="Resetting revokes other sessions — anyone else signed in (including an attacker) is logged out with you."
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {error && (
          <div role="alert" className="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
            {error}
            {error.includes('invalid, already used, or expired') && (
              <Link to="/forgot-password" className="mt-1 block font-medium text-cyan-200 hover:text-cyan-100">
                Request a new reset email
              </Link>
            )}
          </div>
        )}

        <FormField
          id="reset-new-password"
          label="New password"
          type="password"
          autoComplete="new-password"
          value={newPassword}
          onChange={(event) => setNewPassword(event.target.value)}
          placeholder="At least 8 characters"
          error={passwordError}
          disabled={loading || tokenMissing}
          required
        />
        <PasswordField
          id="reset-confirm-password"
          label="Confirm new password"
          value={confirmPassword}
          error={confirmError}
          disabled={loading || tokenMissing}
          showPassword={showPassword}
          onShowPasswordChange={setShowPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
        />

        <PrimaryButton
          type="submit"
          // Stays clickable with invalid input: the handler re-shows the
          // inline errors on each attempt (locking it after the first failed
          // submit would strand keyboard users who fix one field at a time).
          disabled={loading || tokenMissing}
          loading={loading}
          className="min-h-12 w-full"
        >
          {loading ? 'Saving...' : 'Save new password'}
        </PrimaryButton>

        <p className="flex items-center justify-center gap-1.5 text-xs text-slate-500">
          <ShieldCheck className="h-3.5 w-3.5" />
          Saving signs out every active session for the account.
        </p>
      </form>
    </AuthExperienceShell>
  );
};
