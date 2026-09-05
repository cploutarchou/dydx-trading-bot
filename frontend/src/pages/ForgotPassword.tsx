import { MailCheck } from 'lucide-react';
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { AuthExperienceShell } from '../components/AuthExperienceShell';
import { FormField, PrimaryButton } from '../components/PublicPagePrimitives';
import api from '../api';

/**
 * FE-009: request a password reset link. The backend answers identically for
 * known and unknown emails, so this screen always shows the same follow-up.
 */
export const ForgotPasswordPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emailError = submitted && !/^\S+@\S+\.\S+$/.test(email.trim()) ? 'Enter a valid email address' : '';

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
    if (emailError) return;

    try {
      setLoading(true);
      setError(null);
      await api.requestPasswordReset(email.trim());
      // The backend response is generic by design; treat any 2xx as sent.
      setSent(true);
    } catch {
      setError('The reset service is unavailable right now. Try again in a moment.');
    } finally {
      setLoading(false);
    }
  };

  const [sent, setSent] = useState(false);

  return (
    <AuthExperienceShell
      kicker="Account recovery"
      title="Reset your password"
      description="Enter the email on your account and we will send a single-use reset link that works for 30 minutes."
      sideLabel="Password reset"
      sideTitle="Recover access without losing your place."
      sideDescription="Reset links are single-use and expire quickly. Your current password keeps working until you choose a new one."
    >
      {sent ? (
        <div className="space-y-5">
          <div className="flex items-start gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
            <MailCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-300" />
            <div className="text-sm leading-6 text-emerald-100">
              <p className="font-semibold">Check your inbox</p>
              <p className="mt-1 text-emerald-200/80">
                If an account exists for that email, a reset link is on its way. The link works for
                30 minutes and can be used once.
              </p>
            </div>
          </div>
          <Link
            to="/login"
            className="block text-center font-medium text-cyan-200 hover:text-cyan-100"
          >
            Back to sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {error && (
            <div role="alert" className="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
              {error}
            </div>
          )}
          <FormField
            id="forgot-email"
            label="Account email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="name@company.com"
            error={emailError}
            disabled={loading}
            required
          />
          <PrimaryButton type="submit" disabled={loading} loading={loading} className="min-h-12 w-full">
            {loading ? 'Sending link...' : 'Send reset link'}
          </PrimaryButton>
          <div className="text-center">
            <Link to="/login" className="font-medium text-slate-300 hover:text-white">
              Back to sign in
            </Link>
          </div>
        </form>
      )}
    </AuthExperienceShell>
  );
};
