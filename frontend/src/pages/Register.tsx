import { useQuery } from '@tanstack/react-query';
import { AlertCircle, CheckCircle, Loader } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { useAuthStore } from '../store/auth';

interface ValidationErrors {
    username?: string;
    email?: string;
    password?: string;
    confirmPassword?: string;
}

export const RegisterPage: React.FC = () => {
    const navigate = useNavigate();
    const { register, loading, error } = useAuthStore();
    const [formData, setFormData] = useState({
        username: '',
        email: '',
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

        // Username validation
        if (formData.username.length < 3) {
            errors.username = 'Username must be at least 3 characters';
        }
        if (!/^[a-zA-Z0-9_-]+$/.test(formData.username)) {
            errors.username = 'Username can only contain letters, numbers, hyphens, and underscores';
        }

        // Email validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(formData.email)) {
            errors.email = 'Please enter a valid email address';
        }

        // Password validation
        if (formData.password.length < 8) {
            errors.password = 'Password must be at least 8 characters';
        }
        if (!/[A-Z]/.test(formData.password)) {
            errors.password = 'Password must contain at least one uppercase letter';
        }
        if (!/[0-9]/.test(formData.password)) {
            errors.password = 'Password must contain at least one number';
        }

        // Confirm password validation
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

    const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const password = e.target.value;
        setFormData({ ...formData, password });
        setPasswordStrength(calculatePasswordStrength(password));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setFormError(null);

        if (registrationStatusQuery.data?.enabled === false) {
            setFormError(registrationStatusQuery.data.reason || 'Public registration is currently disabled.');
            return;
        }

        const errors = validateForm();
        if (Object.keys(errors).length > 0) {
            if (errors.username) {
                usernameInputRef.current?.focus();
            } else if (errors.email) {
                emailInputRef.current?.focus();
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
            await register(formData.username, formData.email, formData.password);
            navigate('/2fa-setup');
        } catch (err) {
            console.error('❌ RegisterPage: Registration failed:', err);
            const errorMsg = err instanceof Error ? err.message : 'Registration failed. Please try again.';
            console.error('❌ RegisterPage: Error message:', errorMsg);
        }
    };

    return (
        <div className="auth-stage flex items-center justify-center p-4">
            <div className="premium-orb left-[10%] top-[14%] h-52 w-52 bg-cyan-500/12" />
            <div className="premium-orb right-[10%] bottom-[8%] h-64 w-64 bg-emerald-500/10" />
            <div className="auth-panel w-full max-w-xl">
                <div className="rounded-t-[2rem] border-b border-slate-700/60 bg-gradient-to-r from-cyan-600/90 to-blue-600/90 p-8 text-white">
                    <div className="premium-kicker border-white/20 bg-white/10 text-cyan-50">Create your operator account</div>
                    <h1 className="mt-4 text-3xl font-bold">Build your trading command center</h1>
                    <p className="mt-2 text-cyan-50/90">Join dYdX Bot and unlock premium backtesting, runtime control, and market intelligence.</p>
                    <div className="mt-6 grid gap-3 sm:grid-cols-3">
                        <div className="rounded-2xl border border-white/15 bg-white/8 px-4 py-3">
                            <p className="text-[11px] uppercase tracking-[0.18em] text-cyan-100/70">Runtime</p>
                            <p className="mt-1 text-sm font-semibold text-white">Live strategy control</p>
                        </div>
                        <div className="rounded-2xl border border-white/15 bg-white/8 px-4 py-3">
                            <p className="text-[11px] uppercase tracking-[0.18em] text-cyan-100/70">Research</p>
                            <p className="mt-1 text-sm font-semibold text-white">Backtest intelligence</p>
                        </div>
                        <div className="rounded-2xl border border-white/15 bg-white/8 px-4 py-3">
                            <p className="text-[11px] uppercase tracking-[0.18em] text-cyan-100/70">Market Pulse</p>
                            <p className="mt-1 text-sm font-semibold text-white">News and token intel</p>
                        </div>
                    </div>
                </div>

                <div className="p-8">
                    {registrationStatusQuery.data?.enabled === false && (
                        <div
                            role="alert"
                            aria-live="polite"
                            className="mb-6 rounded-2xl border border-amber-600/50 bg-amber-950/30 p-4 text-sm text-amber-200"
                        >
                            {registrationStatusQuery.data.reason}
                        </div>
                    )}

                    {error && (
                        <div
                            ref={apiErrorAlertRef}
                            tabIndex={-1}
                            role="alert"
                            aria-live="assertive"
                            className="mb-6 p-4 bg-red-900 border border-red-700 rounded-lg flex items-start gap-3"
                        >
                            <AlertCircle className="w-5 h-5 text-red-300 shrink-0 mt-0.5" />
                            <div className="text-red-200 text-sm">{error}</div>
                        </div>
                    )}

                    {formError && (
                        <div
                            ref={formErrorAlertRef}
                            tabIndex={-1}
                            role="alert"
                            aria-live="assertive"
                            className="mb-6 p-4 bg-red-900 border border-red-700 rounded-lg flex items-start gap-3"
                        >
                            <AlertCircle className="w-5 h-5 text-red-300 shrink-0 mt-0.5" />
                            <div className="text-red-200 text-sm">{formError}</div>
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-4">
                        {/* Username */}
                        <div>
                            <label htmlFor="username" className="block text-sm font-medium text-slate-300 mb-2">
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
                                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                className={`premium-input ${
                                    validationErrors.username ? 'border-red-500' : ''
                                }`}
                                placeholder="john_doe"
                                disabled={loading}
                            />
                            {validationErrors.username && (
                                <p id="username-error" className="text-xs text-red-300 mt-1">{validationErrors.username}</p>
                            )}
                        </div>

                        {/* Email */}
                        <div>
                            <label htmlFor="email" className="block text-sm font-medium text-slate-300 mb-2">
                                Email Address
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
                                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                className={`premium-input ${
                                    validationErrors.email ? 'border-red-500' : ''
                                }`}
                                placeholder="john@example.com"
                                disabled={loading}
                            />
                            {validationErrors.email && (
                                <p id="email-error" className="text-xs text-red-300 mt-1">{validationErrors.email}</p>
                            )}
                        </div>

                        {/* Password */}
                        <div>
                            <label htmlFor="password" className="block text-sm font-medium text-slate-300 mb-2">
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
                                className={`premium-input ${
                                    validationErrors.password ? 'border-red-500' : ''
                                }`}
                                placeholder="••••••••"
                                disabled={loading}
                            />
                            {formData.password && (
                                <div className="mt-2 flex items-center gap-2">
                                    <div className={`h-1 flex-1 rounded ${
                                        passwordStrength === 'weak' ? 'bg-red-500' :
                                        passwordStrength === 'medium' ? 'bg-yellow-500' :
                                        'bg-green-500'
                                    }`} />
                                    <span className="text-xs font-medium text-slate-400">
                                        {passwordStrength.charAt(0).toUpperCase() + passwordStrength.slice(1)}
                                    </span>
                                </div>
                            )}
                            {validationErrors.password && (
                                <p id="password-error" className="text-xs text-red-300 mt-1">{validationErrors.password}</p>
                            )}
                            <p id="password-help" className="text-xs text-slate-400 mt-2">
                                At least 8 characters, one uppercase letter, and one number
                            </p>
                        </div>

                        {/* Confirm Password */}
                        <div>
                            <label htmlFor="confirmPassword" className="block text-sm font-medium text-slate-300 mb-2">
                                Confirm Password
                            </label>
                            <input
                                id="confirmPassword"
                                name="confirmPassword"
                                type="password"
                                ref={confirmPasswordInputRef}
                                autoComplete="new-password"
                                aria-invalid={!!validationErrors.confirmPassword}
                                aria-describedby={validationErrors.confirmPassword ? 'confirm-password-error' : undefined}
                                value={formData.confirmPassword}
                                onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                                className={`premium-input ${validationErrors.confirmPassword ? 'border-red-500' : ''}`}
                                placeholder="••••••••"
                                disabled={loading}
                            />
                            {formData.confirmPassword && formData.password === formData.confirmPassword && (
                                <div className="flex items-center gap-2 mt-1">
                                    <CheckCircle className="w-4 h-4 text-green-400" />
                                    <span className="text-xs text-green-400">Passwords match</span>
                                </div>
                            )}
                            {validationErrors.confirmPassword && (
                                <p id="confirm-password-error" className="text-xs text-red-300 mt-1">{validationErrors.confirmPassword}</p>
                            )}
                        </div>

                        {/* Terms Agreement */}
                        <div className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-4">
                          <div className="flex items-start gap-3">
                            <input
                                type="checkbox"
                                id="terms"
                                ref={termsCheckboxRef}
                                checked={formData.agreedToTerms}
                                onChange={(e) => setFormData({ ...formData, agreedToTerms: e.target.checked })}
                                className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-900 text-cyan-500 focus:ring-cyan-500"
                                disabled={loading}
                            />
                            <label htmlFor="terms" className="text-xs text-slate-400">
                                I agree to the{' '}
                                <a href="#" className="text-cyan-300 hover:text-cyan-200 hover:underline">
                                    Terms of Service
                                </a>
                                {' '}and{' '}
                                <a href="#" className="text-cyan-300 hover:text-cyan-200 hover:underline">
                                    Privacy Policy
                                </a>
                            </label>
                          </div>
                        </div>

                        {/* Submit Button */}
                        <button
                            type="submit"
                            disabled={loading || registrationStatusQuery.data?.enabled === false}
                            className="premium-button premium-button-primary mt-6 w-full disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {loading && <Loader className="w-4 h-4 animate-spin" />}
                            {loading ? 'Creating Account...' : 'Create Account'}
                        </button>
                    </form>

                    <p className="mt-6 text-center text-sm text-slate-400">
                        Already have an account?{' '}
                        <button
                            type="button"
                            onClick={() => navigate('/login')}
                            className="font-medium text-cyan-300 hover:text-cyan-200 hover:underline"
                        >
                            Login
                        </button>
                    </p>
                </div>
            </div>
        </div>
    );
};
