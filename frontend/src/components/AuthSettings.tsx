import { AlertCircle, CheckCircle, Lock, LogOut, Shield, User } from 'lucide-react';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFocusOnVisibleError } from '../hooks/useFocusOnVisibleError';
import { useAuthStore } from '../store/auth';

interface ChangePasswordForm {
    currentPassword: string;
    newPassword: string;
    confirmPassword: string;
}

const authTabs = ['profile', 'security', 'sessions'] as const;
type AuthTab = (typeof authTabs)[number];

interface AuthSettingsComponentProps {
  defaultTab?: AuthTab;
  visibleTabs?: AuthTab[];
  showHeader?: boolean;
}

export const AuthSettingsComponent: React.FC<AuthSettingsComponentProps> = ({
  defaultTab = 'profile',
  visibleTabs,
  showHeader = true,
}) => {
    const navigate = useNavigate();
    const { user, logout, setup2FA, loading } = useAuthStore();
    const availableTabs = useMemo(() => visibleTabs && visibleTabs.length > 0 ? visibleTabs : [...authTabs], [visibleTabs]);
    const [activeTab, setActiveTab] = useState<AuthTab>(defaultTab);
    const [changePasswordForm, setChangePasswordForm] = useState<ChangePasswordForm>({
        currentPassword: '',
        newPassword: '',
        confirmPassword: '',
    });
    const [passwordChangeStatus, setPasswordChangeStatus] = useState<{ success?: string; error?: string }>({});
    const [setupError, setSetupError] = useState<string | null>(null);
    const setupErrorAlertRef = useRef<HTMLDivElement | null>(null);
    const passwordErrorAlertRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
      if (availableTabs.includes(defaultTab)) {
        setActiveTab(defaultTab);
      } else {
        setActiveTab(availableTabs[0] || 'profile');
      }
    }, [availableTabs, defaultTab]);

    useEffect(() => {
      if (!availableTabs.includes(activeTab)) {
        setActiveTab(availableTabs[0] || 'profile');
      }
    }, [activeTab, availableTabs]);

    const handleTabKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
        const currentIndex = availableTabs.indexOf(activeTab);
        if (currentIndex === -1) return;

        if (e.key === 'ArrowRight') {
            e.preventDefault();
            setActiveTab(availableTabs[(currentIndex + 1) % availableTabs.length]);
            return;
        }

        if (e.key === 'ArrowLeft') {
            e.preventDefault();
            setActiveTab(availableTabs[(currentIndex - 1 + availableTabs.length) % availableTabs.length]);
            return;
        }

        if (e.key === 'Home') {
            e.preventDefault();
            setActiveTab(availableTabs[0]);
            return;
        }

        if (e.key === 'End') {
            e.preventDefault();
            setActiveTab(availableTabs[availableTabs.length - 1]);
        }
    };

    useFocusOnVisibleError(
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
            // This would require a backend endpoint like PUT /api/v1/auth/change-password
            // const response = await api.changePassword({
            //     current_password: changePasswordForm.currentPassword,
            //     new_password: changePasswordForm.newPassword,
            // });
            // setPasswordChangeStatus({ success: 'Password changed successfully' });
            setPasswordChangeStatus({ success: 'Password change endpoint not yet implemented' });
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
            {showHeader && (
            <div className="bg-slate-800 rounded-lg shadow p-6 border border-slate-700">
                <div className="flex items-center gap-4">
                    <div className="w-16 h-16 bg-linear-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center">
                        <User className="w-8 h-8 text-white" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white">{user?.username}</h1>
                        <p className="text-slate-300">{user?.email}</p>
                        <p className="text-xs text-slate-400">
                            Joined {user?.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}
                        </p>
                    </div>
                </div>
            </div>
            )}

            {/* Tabs */}
            <div className="bg-slate-800 rounded-lg shadow border border-slate-700">
                <div
                    className="flex border-b border-slate-700"
                    role="tablist"
                    aria-label="Auth settings sections"
                    onKeyDown={handleTabKeyDown}
                >
                    {availableTabs.includes('profile') && (
                    <button
                        type="button"
                        role="tab"
                        id="auth-tab-profile"
                        aria-selected={activeTab === 'profile'}
                        aria-controls="auth-panel-profile"
                        tabIndex={activeTab === 'profile' ? 0 : -1}
                        onClick={() => setActiveTab('profile')}
                        className={`flex-1 py-4 px-6 font-medium flex items-center justify-center gap-2 ${
                            activeTab === 'profile'
                                ? 'text-blue-400 border-b-2 border-blue-500'
                                : 'text-slate-300 hover:text-white'
                        }`}
                    >
                        <User className="w-4 h-4" />
                        Profile
                    </button>
                    )}
                    {availableTabs.includes('security') && (
                    <button
                        type="button"
                        role="tab"
                        id="auth-tab-security"
                        aria-selected={activeTab === 'security'}
                        aria-controls="auth-panel-security"
                        tabIndex={activeTab === 'security' ? 0 : -1}
                        onClick={() => setActiveTab('security')}
                        className={`flex-1 py-4 px-6 font-medium flex items-center justify-center gap-2 ${
                            activeTab === 'security'
                                ? 'text-blue-400 border-b-2 border-blue-500'
                                : 'text-slate-300 hover:text-white'
                        }`}
                    >
                        <Lock className="w-4 h-4" />
                        Security
                    </button>
                    )}
                    {availableTabs.includes('sessions') && (
                    <button
                        type="button"
                        role="tab"
                        id="auth-tab-sessions"
                        aria-selected={activeTab === 'sessions'}
                        aria-controls="auth-panel-sessions"
                        tabIndex={activeTab === 'sessions' ? 0 : -1}
                        onClick={() => setActiveTab('sessions')}
                        className={`flex-1 py-4 px-6 font-medium flex items-center justify-center gap-2 ${
                            activeTab === 'sessions'
                                ? 'text-blue-400 border-b-2 border-blue-500'
                                : 'text-slate-300 hover:text-white'
                        }`}
                    >
                        <Shield className="w-4 h-4" />
                        Sessions
                    </button>
                    )}
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
                                <label htmlFor="auth-profile-username" className="block text-sm font-medium text-slate-300 mb-2">
                                    Username
                                </label>
                                <input
                                    id="auth-profile-username"
                                    type="text"
                                    value={user?.username || ''}
                                    disabled
                                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-300"
                                />
                                <p className="text-xs text-slate-400 mt-1">Username cannot be changed</p>
                            </div>

                            <div>
                                <label htmlFor="auth-profile-email" className="block text-sm font-medium text-slate-300 mb-2">
                                    Email Address
                                </label>
                                <input
                                    id="auth-profile-email"
                                    type="email"
                                    value={user?.email || ''}
                                    disabled
                                    className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-300"
                                />
                                <p className="text-xs text-slate-400 mt-1">Contact support to change email</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Account Status
                                </label>
                                <div className="flex items-center gap-2">
                                    <CheckCircle className="w-5 h-5 text-green-600" />
                                    <span className="text-slate-200 font-medium">
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
                            <div className="border border-slate-700 rounded-lg p-6 bg-slate-900/40">
                                <div className="flex items-start justify-between mb-4">
                                    <div className="flex items-center gap-3">
                                        <Shield className="w-6 h-6 text-blue-600" />
                                        <div>
                                            <h3 className="font-bold text-white">
                                                Two-Factor Authentication
                                            </h3>
                                            <p className="text-sm text-slate-300">
                                                Protect your account with TOTP codes
                                            </p>
                                        </div>
                                    </div>
                                    <span className="px-3 py-1 rounded-full text-xs font-medium bg-slate-700 text-slate-200">
                                        Setup available
                                    </span>
                                </div>

                                {setupError && (
                                    <div
                                        ref={setupErrorAlertRef}
                                        tabIndex={-1}
                                        role="alert"
                                        aria-live="assertive"
                                        className="mb-4 p-4 bg-red-900 border border-red-700 rounded-lg flex items-start gap-3"
                                    >
                                        <AlertCircle className="w-5 h-5 text-red-300 shrink-0 mt-0.5" />
                                        <div className="text-red-200 text-sm">{setupError}</div>
                                    </div>
                                )}

                                <p className="text-sm text-slate-300 mb-4">
                                    Enable or revisit TOTP-based two-factor authentication to add an extra layer of security.
                                </p>

                                <button
                                    type="button"
                                    onClick={handleSetup2FA}
                                    disabled={loading}
                                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
                                >
                                    {loading ? 'Setting up...' : 'Open 2FA Setup'}
                                </button>
                            </div>

                            {/* Change Password Section */}
                            <div className="border border-slate-700 rounded-lg p-6 bg-slate-900/40">
                                <h3 className="font-bold text-white mb-4 flex items-center gap-2">
                                    <Lock className="w-5 h-5" />
                                    Change Password
                                </h3>

                                {passwordChangeStatus.error && (
                                    <div
                                        ref={passwordErrorAlertRef}
                                        tabIndex={-1}
                                        role="alert"
                                        aria-live="assertive"
                                        className="mb-4 p-4 bg-red-900 border border-red-700 rounded-lg text-red-200 text-sm"
                                    >
                                        {passwordChangeStatus.error}
                                    </div>
                                )}

                                {passwordChangeStatus.success && (
                                    <div
                                        role="status"
                                        aria-live="polite"
                                        className="mb-4 p-4 bg-green-900 border border-green-700 rounded-lg text-green-200 text-sm"
                                    >
                                        {passwordChangeStatus.success}
                                    </div>
                                )}

                                <form onSubmit={handleChangePassword} className="space-y-4">
                                    <div>
                                        <label htmlFor="auth-current-password" className="block text-sm font-medium text-slate-300 mb-2">
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
                                            className="w-full px-4 py-2 bg-slate-700 border border-slate-600 text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                            required
                                        />
                                    </div>

                                    <div>
                                        <label htmlFor="auth-new-password" className="block text-sm font-medium text-slate-300 mb-2">
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
                                            className="w-full px-4 py-2 bg-slate-700 border border-slate-600 text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                            required
                                        />
                                    </div>

                                    <div>
                                        <label htmlFor="auth-confirm-password" className="block text-sm font-medium text-slate-300 mb-2">
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
                                            className="w-full px-4 py-2 bg-slate-700 border border-slate-600 text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                            required
                                        />
                                    </div>

                                    <button
                                        type="submit"
                                        className="px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 font-medium"
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
                            <div className="bg-blue-900/30 border border-blue-700 rounded-lg p-4">
                                <p className="text-sm text-blue-200">
                                    <strong>Current Session:</strong> Active since {new Date().toLocaleDateString()}
                                </p>
                            </div>

                            <button
                                type="button"
                                onClick={handleLogout}
                                className="w-full px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 font-medium flex items-center justify-center gap-2"
                            >
                                <LogOut className="w-4 h-4" />
                                Logout from All Sessions
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
