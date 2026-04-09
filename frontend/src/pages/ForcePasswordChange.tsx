import { Loader2, LockKeyhole } from 'lucide-react';
import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import AuthExperienceShell from '../components/AuthExperienceShell';
import { useAuthStore } from '../store/auth';

const getErrorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : 'Failed to update password';

export function ForcePasswordChangePage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');

    if (newPassword !== confirmPassword) {
      setError('New password and confirmation do not match.');
      return;
    }

    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters.');
      return;
    }

    try {
      setSaving(true);
      const response = await api.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      if (response.data?.user) {
        useAuthStore.setState({ user: response.data.user, error: null });
      }
      navigate('/dashboard', { replace: true });
    } catch (updateError: unknown) {
      setError(getErrorMessage(updateError));
    } finally {
      setSaving(false);
    }
  };

  return (
    <AuthExperienceShell
      kicker="Security checkpoint"
      title="Rotate your temporary password"
      description={`${user?.username ? `${user.username}, ` : ''}your account is in first-login mode. Rotate the temporary password before entering the live trading workspace.`}
      sideLabel="Account Hardening"
      sideTitle="Secure entry should feel premium, not punitive."
      sideDescription="This first-login checkpoint keeps account access aligned with the production-grade environment behind the platform."
    >

        {error && (
          <div className="mt-6 rounded-2xl border border-red-700 bg-red-950/55 p-4 text-sm text-red-200">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="force-current-password" className="mb-2 block text-sm font-medium text-slate-300">
              Current temporary password
            </label>
            <input
              id="force-current-password"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              className="premium-input"
              required
            />
          </div>

          <div>
            <label htmlFor="force-new-password" className="mb-2 block text-sm font-medium text-slate-300">
              New password
            </label>
            <input
              id="force-new-password"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              className="premium-input"
              required
            />
          </div>

          <div>
            <label htmlFor="force-confirm-password" className="mb-2 block text-sm font-medium text-slate-300">
              Confirm new password
            </label>
            <input
              id="force-confirm-password"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              className="premium-input"
              required
            />
          </div>

          <button
            type="submit"
            disabled={saving}
            className="premium-button premium-button-primary w-full disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <LockKeyhole className="h-4 w-4" />}
            {saving ? 'Updating password...' : 'Save new password'}
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            logout();
            navigate('/login', { replace: true });
          }}
          className="mt-4 w-full text-sm text-slate-400 transition hover:text-slate-200"
        >
          Sign out instead
        </button>
    </AuthExperienceShell>
  );
}
