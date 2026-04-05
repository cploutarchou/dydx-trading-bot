import { Loader2, LockKeyhole } from 'lucide-react';
import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
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
    <div className="auth-stage flex min-h-screen items-center justify-center px-4 py-10">
      <div className="premium-orb left-[8%] top-[12%] h-48 w-48 bg-cyan-500/15" />
      <div className="premium-orb right-[8%] bottom-[10%] h-56 w-56 bg-amber-500/15" />

      <div className="auth-panel relative z-10 w-full max-w-xl p-8 sm:p-10">
        <div className="premium-kicker">Security checkpoint</div>
        <h1 className="mt-4 text-3xl font-bold text-white">Change your temporary password</h1>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          {user?.username ? `${user.username},` : 'Your account'} is in first-login mode. You need to rotate the temporary password before entering the trading workspace.
        </p>

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
      </div>
    </div>
  );
}
