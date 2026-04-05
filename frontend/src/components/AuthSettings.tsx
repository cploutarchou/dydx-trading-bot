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
    const [passwordChangeStatus, setPasswordChangeStatus] = useState<{ success?: string; error?: string }>({});
    const [setupError, setSetupError] = useState<string | null>(null);
    const setupErrorAlertRef = useRef<HTMLDivElement | null>(null);
    const passwordErrorAlertRef = useRef<HTMLDivElement | null>(null);

    const handleTabKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
        const currentIndex = authTabs.indexOf(activeTab);
        if (currentIndex === -1) return;

        if (e.key === 'ArrowRight') {
            e.preventDefault();
            setActiveTab(authTabs[(currentIndex + 1) % authTabs.length]);
            return;
        }

        if (e.key === 'ArrowLeft') {
            e.preventDefault();
            setActiveTab(authTabs[(currentIndex - 1 + authTabs.length) % authTabs.length]);
            return;
        }

        if (e.key === 'Home') {
            e.preventDefault();
            setActiveTab(authTabs[0]);
            return;
        }

        if (e.key === 'End') {
            e.preventDefault();
            setActiveTab(authTabs[authTabs.length - 1]);
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
            <div className="bg-white rounded-lg shadow p-6">
                <div className="flex items-center gap-4">
                    <div className="w-16 h-16 bg-linear-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center">
                        <User className="w-8 h-8 text-white" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900">{user?.username}</h1>
                        <p className="text-slate-600">{user?.email}</p>
                        <p className="text-xs text-slate-500">
                            Joined {user?.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}
                        </p>
                    </div>
                </div>
            </div>

            {/* Tabs */}
            <div className="bg-white rounded-lg shadow">
                <div
                    className="flex border-b border-slate-200"
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
                        className={`flex-1 py-4 px-6 font-medium flex items-center justify-center gap-2 ${
                            activeTab === 'profile'
                                ? 'text-blue-600 border-b-2 border-blue-600'
                                : 'text-slate-600 hover:text-slate-900'
                        }`}
                    >
                        <User className="w-4 h-4" />
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
                        className={`flex-1 py-4 px-6 font-medium flex items-center justify-center gap-2 ${
                            activeTab === 'security'
                                ? 'text-blue-600 border-b-2 border-blue-600'
                                : 'text-slate-600 hover:text-slate-900'
                        }`}
                    >
                        <Lock className="w-4 h-4" />
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
                        className={`flex-1 py-4 px-6 font-medium flex items-center justify-center gap-2 ${
                            activeTab === 'sessions'
                                ? 'text-blue-600 border-b-2 border-blue-600'
                                : 'text-slate-600 hover:text-slate-900'
                        }`}
                    >
                        <Shield className="w-4 h-4" />
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
                                <label htmlFor="auth-profile-username" className="block text-sm font-medium text-slate-700 mb-2">
                                    Username
                                </label>
                                <input
                                    id="auth-profile-username"
                                    type="text"
                                    value={user?.username || ''}
                                    disabled
                                    className="w-full px-4 py-2 bg-slate-100 border border-slate-300 rounded-lg text-slate-700"
                                />
                                <p className="text-xs text-slate-500 mt-1">Username cannot be changed</p>
                            </div>

                            <div>
                                <label htmlFor="auth-profile-email" className="block text-sm font-medium text-slate-700 mb-2">
                                    Email Address
                                </label>
                                <input
                                    id="auth-profile-email"
                                    type="email"
                                    value={user?.email || ''}
                                    disabled
                                    className="w-full px-4 py-2 bg-slate-100 border border-slate-300 rounded-lg text-slate-700"
                                />
                                <p className="text-xs text-slate-500 mt-1">Contact support to change email</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-2">
                                    Account Status
                                </label>
                                <div className="flex items-center gap-2">
                                    <CheckCircle className="w-5 h-5 text-green-600" />
                                    <span className="text-slate-700 font-medium">
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
                            <div className="border border-slate-200 rounded-lg p-6">
                                <div className="flex items-start justify-between mb-4">
                                    <div className="flex items-center gap-3">
                                        <Shield className="w-6 h-6 text-blue-600" />
                                        <div>
                                            <h3 className="font-bold text-slate-900">
                                                Two-Factor Authentication
                                            </h3>
                                            <p className="text-sm text-slate-600">
                                                Protect your account with TOTP codes
                                            </p>
                                        </div>
                                    </div>
                                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                                        user?.is_active
                                            ? 'bg-green-100 text-green-800'
                                            : 'bg-red-100 text-red-800'
                                    }`}>
                                        {user?.is_active ? 'Enabled' : 'Disabled'}
                                    </span>
                                </div>

                                {setupError && (
                                    <div
                                        ref={setupErrorAlertRef}
                                        tabIndex={-1}
                                        role="alert"
                                        aria-live="assertive"
                                        className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3"
                                    >
                                        <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
                                        <div className="text-red-700 text-sm">{setupError}</div>
                                    </div>
                                )}

                                <p className="text-sm text-slate-600 mb-4">
                                    {user?.is_active
                                        ? 'Your account is protected with two-factor authentication.'
                                        : 'Enable TOTP-based two-factor authentication to add an extra layer of security.'}
                                </p>

                                {!user?.is_active && (
                                    <button
                                        type="button"
                                        onClick={handleSetup2FA}
                                        disabled={loading}
                                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
                                    >
                                        {loading ? 'Setting up...' : 'Enable 2FA'}
                                    </button>
                                )}
                            </div>

                            {/* Change Password Section */}
                            <div className="border border-slate-200 rounded-lg p-6">
                                <h3 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
                                    <Lock className="w-5 h-5" />
                                    Change Password
                                </h3>

                                {passwordChangeStatus.error && (
                                    <div
                                        ref={passwordErrorAlertRef}
                                        tabIndex={-1}
                                        role="alert"
                                        aria-live="assertive"
                                        className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm"
                                    >
                                        {passwordChangeStatus.error}
                                    </div>
                                )}

                                {passwordChangeStatus.success && (
                                    <div
                                        role="status"
                                        aria-live="polite"
                                        className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm"
                                    >
                                        {passwordChangeStatus.success}
                                    </div>
                                )}

                                <form onSubmit={handleChangePassword} className="space-y-4">
                                    <div>
                                        <label htmlFor="auth-current-password" className="block text-sm font-medium text-slate-700 mb-2">
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
                                            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                            required
                                        />
                                    </div>

                                    <div>
                                        <label htmlFor="auth-new-password" className="block text-sm font-medium text-slate-700 mb-2">
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
                                            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                            required
                                        />
                                    </div>

                                    <div>
                                        <label htmlFor="auth-confirm-password" className="block text-sm font-medium text-slate-700 mb-2">
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
                                            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
                            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                                <p className="text-sm text-blue-800">
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
