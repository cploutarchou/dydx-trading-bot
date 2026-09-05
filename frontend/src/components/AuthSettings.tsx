import { AlertCircle, CheckCircle, Lock, LogOut, Shield, User } from 'lucide-react';
import React, { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { useFocusOnError } from '../hooks/useFocusOnError';
import { useAuthStore } from '../store/auth';

interface ChangePasswordForm {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

const authTabs = ['profile', 'security', 'sessions'] as const;
type AuthTab = (typeof authTabs)[number];

export const AuthSettingsComponent: React.FC = () => {
  const navigate = useNavigate();
  const { user, logout, setup2FA, loading } = useAuthStore();
  const [activeTab, setActiveTab] = useState<AuthTab>('profile');
  const [changePasswordForm, setChangePasswordForm] = useState<ChangePasswordForm>({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [passwordChangeStatus, setPasswordChangeStatus] = useState<{
    success?: string;
    error?: string;
  }>({});
  const [setupError, setSetupError] = useState<string | null>(null);
  const setupErrorAlertRef = useRef<HTMLDivElement | null>(null);
  const passwordErrorAlertRef = useRef<HTMLDivElement | null>(null);

  const handleTabKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const currentIndex = authTabs.indexOf(activeTab);
    if (currentIndex === -1) return;

    if (e.key === 'ArrowRight') {
      e.preventDefault();
      setActiveTab(authTabs[(currentIndex + 1) % authTabs.length] ?? authTabs[0]!);
      return;
    }

    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      setActiveTab(authTabs[(currentIndex - 1 + authTabs.length) % authTabs.length] ?? authTabs[0]!);
      return;
    }

    if (e.key === 'Home') {
      e.preventDefault();
      setActiveTab(authTabs[0]!);
      return;
    }

    if (e.key === 'End') {
      e.preventDefault();
      setActiveTab(authTabs[authTabs.length - 1] ?? authTabs[0]!);
    }
  };

  useFocusOnError(
    [
      { when: activeTab === 'security' && !!setupError, ref: setupErrorAlertRef },
      {
        when: activeTab === 'security' && !setupError && !!passwordChangeStatus.error,
        ref: passwordErrorAlertRef,
      },
    ],
    [activeTab, setupError, passwordChangeStatus.error]
  );

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleSetup2FA = async () => {
    setSetupError(null);
    try {
      await setup2FA();
      navigate('/2fa-setup');
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to setup 2FA';
      setSetupError(errorMsg);
      console.error('❌ AuthSettings: 2FA setup failed:', err);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();

    if (changePasswordForm.newPassword !== changePasswordForm.confirmPassword) {
      setPasswordChangeStatus({ error: 'Passwords do not match' });
      return;
    }

    if (changePasswordForm.newPassword.length < 8) {
      setPasswordChangeStatus({ error: 'Password must be at least 8 characters' });
      return;
    }

    try {
      const response = await api.changePassword({
        current_password: changePasswordForm.currentPassword,
        new_password: changePasswordForm.newPassword,
      });
      if (response.data?.user) {
        useAuthStore.setState({ user: response.data.user, error: null });
      }
      setPasswordChangeStatus({ success: 'Password changed successfully' });
      setChangePasswordForm({ currentPassword: '', newPassword: '', confirmPassword: '' });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to change password';
      setPasswordChangeStatus({ error: errorMsg });
      console.error('❌ AuthSettings: Password change failed:', err);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="premium-panel p-6">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-linear-to-br from-cyan-500 to-blue-600">
            <User className="h-8 w-8 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">{user?.username}</h1>
            <p className="text-slate-400">{user?.email}</p>
            <p className="text-xs text-slate-500">
              Joined {user?.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="premium-panel overflow-hidden p-0">
        {/* Keyboard arrow handling for the tab list lives here; the tabs
            themselves are the focusable elements, not the list container. */}
        {/* eslint-disable-next-line jsx-a11y/interactive-supports-focus */}
        <div
          className="flex border-b border-slate-700/60"
          role="tablist"
          aria-label="Auth settings sections"
          onKeyDown={handleTabKeyDown}
        >
          <button
            type="button"
            role="tab"
            id="auth-tab-profile"
            aria-selected={activeTab === 'profile'}
            aria-controls="auth-panel-profile"
            tabIndex={activeTab === 'profile' ? 0 : -1}
            onClick={() => setActiveTab('profile')}
            className={`flex flex-1 items-center justify-center gap-2 px-6 py-4 font-medium transition ${
              activeTab === 'profile'
                ? 'border-b-2 border-cyan-500 text-cyan-400'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <User className="h-4 w-4" />
            Profile
          </button>
          <button
            type="button"
            role="tab"
            id="auth-tab-security"
            aria-selected={activeTab === 'security'}
            aria-controls="auth-panel-security"
            tabIndex={activeTab === 'security' ? 0 : -1}
            onClick={() => setActiveTab('security')}
            className={`flex flex-1 items-center justify-center gap-2 px-6 py-4 font-medium transition ${
              activeTab === 'security'
                ? 'border-b-2 border-cyan-500 text-cyan-400'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Lock className="h-4 w-4" />
            Security
          </button>
          <button
            type="button"
            role="tab"
            id="auth-tab-sessions"
            aria-selected={activeTab === 'sessions'}
            aria-controls="auth-panel-sessions"
            tabIndex={activeTab === 'sessions' ? 0 : -1}
            onClick={() => setActiveTab('sessions')}
            className={`flex flex-1 items-center justify-center gap-2 px-6 py-4 font-medium transition ${
              activeTab === 'sessions'
                ? 'border-b-2 border-cyan-500 text-cyan-400'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Shield className="h-4 w-4" />
            Sessions
          </button>
        </div>

        <div className="p-6">
          {/* Profile Tab */}
          {activeTab === 'profile' && (
            <div
              className="space-y-6"
              role="tabpanel"
              id="auth-panel-profile"
              aria-labelledby="auth-tab-profile"
            >
              <div>
                <label
                  htmlFor="auth-profile-username"
                  className="mb-2 block text-sm font-medium text-slate-300"
                >
                  Username
                </label>
                <input
                  id="auth-profile-username"
                  type="text"
                  value={user?.username || ''}
                  disabled
                  className="premium-input cursor-not-allowed opacity-60"
                />
                <p className="mt-1 text-xs text-slate-500">Username cannot be changed</p>
              </div>

              <div>
                <label
                  htmlFor="auth-profile-email"
                  className="mb-2 block text-sm font-medium text-slate-300"
                >
                  Email Address
                </label>
                <input
                  id="auth-profile-email"
                  type="email"
                  value={user?.email || ''}
                  disabled
                  className="premium-input cursor-not-allowed opacity-60"
                />
                <p className="mt-1 text-xs text-slate-500">Contact support to change email</p>
              </div>

              <div>
                <p className="mb-2 block text-sm font-medium text-slate-300">
                  Account Status
                </p>
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-emerald-400" />
                  <span className="font-medium text-slate-200">
                    {user?.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Security Tab */}
          {activeTab === 'security' && (
            <div
              className="space-y-6"
              role="tabpanel"
              id="auth-panel-security"
              aria-labelledby="auth-tab-security"
            >
              {/* 2FA Section */}
              <div className="rounded-xl border border-slate-700/60 bg-slate-800/50 p-6">
                <div className="mb-4 flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <Shield className="h-6 w-6 text-cyan-400" />
                    <div>
                      <h3 className="font-bold text-white">Two-Factor Authentication</h3>
                      <p className="text-sm text-slate-400">Protect your account with TOTP codes</p>
                    </div>
                  </div>
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      user?.is_active
                        ? 'bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30'
                        : 'bg-red-500/15 text-red-400 ring-1 ring-red-500/30'
                    }`}
                  >
                    {user?.is_active ? 'Enabled' : 'Disabled'}
                  </span>
                </div>

                {setupError && (
                  <div
                    ref={setupErrorAlertRef}
                    tabIndex={-1}
                    role="alert"
                    aria-live="assertive"
                    className="mb-4 flex items-start gap-3 rounded-lg border border-red-700/40 bg-red-900/20 p-4"
                  >
                    <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />
                    <div className="text-sm text-red-300">{setupError}</div>
                  </div>
                )}

                <p className="mb-4 text-sm text-slate-400">
                  {user?.is_active
                    ? 'Your account is protected with two-factor authentication.'
                    : 'Enable TOTP-based two-factor authentication to add an extra layer of security.'}
                </p>

                {!user?.is_active && (
                  <button
                    type="button"
                    onClick={handleSetup2FA}
                    disabled={loading}
                    className="rounded-xl bg-cyan-500 px-4 py-2 text-sm font-medium text-slate-900 transition hover:bg-cyan-400 disabled:opacity-50"
                  >
                    {loading ? 'Setting up...' : 'Enable 2FA'}
                  </button>
                )}
              </div>

              {/* Change Password Section */}
              <div className="rounded-xl border border-slate-700/60 bg-slate-800/50 p-6">
                <h3 className="mb-4 flex items-center gap-2 font-bold text-white">
                  <Lock className="h-5 w-5 text-cyan-400" />
                  Change Password
                </h3>

                {passwordChangeStatus.error && (
                  <div
                    ref={passwordErrorAlertRef}
                    tabIndex={-1}
                    role="alert"
                    aria-live="assertive"
                    className="mb-4 rounded-lg border border-red-700/40 bg-red-900/20 p-4 text-sm text-red-300"
                  >
                    {passwordChangeStatus.error}
                  </div>
                )}

                {passwordChangeStatus.success && (
                  <div
                    role="status"
                    aria-live="polite"
                    className="mb-4 rounded-lg border border-emerald-700/40 bg-emerald-900/20 p-4 text-sm text-emerald-300"
                  >
                    {passwordChangeStatus.success}
                  </div>
                )}

                <form onSubmit={handleChangePassword} className="space-y-4">
                  <div>
                    <label
                      htmlFor="auth-current-password"
                      className="mb-2 block text-sm font-medium text-slate-300"
                    >
                      Current Password
                    </label>
                    <input
                      id="auth-current-password"
                      type="password"
                      autoComplete="current-password"
                      value={changePasswordForm.currentPassword}
                      onChange={(e) =>
                        setChangePasswordForm({
                          ...changePasswordForm,
                          currentPassword: e.target.value,
                        })
                      }
                      className="premium-input"
                      required
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="auth-new-password"
                      className="mb-2 block text-sm font-medium text-slate-300"
                    >
                      New Password
                    </label>
                    <input
                      id="auth-new-password"
                      type="password"
                      autoComplete="new-password"
                      value={changePasswordForm.newPassword}
                      onChange={(e) =>
                        setChangePasswordForm({
                          ...changePasswordForm,
                          newPassword: e.target.value,
                        })
                      }
                      className="premium-input"
                      required
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="auth-confirm-password"
                      className="mb-2 block text-sm font-medium text-slate-300"
                    >
                      Confirm New Password
                    </label>
                    <input
                      id="auth-confirm-password"
                      type="password"
                      autoComplete="new-password"
                      value={changePasswordForm.confirmPassword}
                      onChange={(e) =>
                        setChangePasswordForm({
                          ...changePasswordForm,
                          confirmPassword: e.target.value,
                        })
                      }
                      className="premium-input"
                      required
                    />
                  </div>

                  <button
                    type="submit"
                    className="rounded-xl bg-cyan-500 px-4 py-2 text-sm font-medium text-slate-900 transition hover:bg-cyan-400"
                  >
                    Update Password
                  </button>
                </form>
              </div>
            </div>
          )}

          {/* Sessions Tab */}
          {activeTab === 'sessions' && (
            <div
              className="space-y-4"
              role="tabpanel"
              id="auth-panel-sessions"
              aria-labelledby="auth-tab-sessions"
            >
              <div className="rounded-xl border border-cyan-700/40 bg-cyan-900/20 p-4">
                <p className="text-sm text-cyan-300">
                  <strong>Current Session:</strong> Active since {new Date().toLocaleDateString()}
                </p>
              </div>

              <button
                type="button"
                onClick={handleLogout}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-red-500/15 px-4 py-3 font-medium text-red-400 ring-1 ring-red-500/30 transition hover:bg-red-500/25 hover:text-red-300"
              >
                <LogOut className="h-4 w-4" />
                Logout from All Sessions
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
