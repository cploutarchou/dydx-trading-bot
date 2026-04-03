import { AlertCircle, CheckCircle, Loader } from 'lucide-react';
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
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

    const validateForm = (): boolean => {
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
        return Object.keys(errors).length === 0;
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

        if (!validateForm()) {
            return;
        }

        if (!formData.agreedToTerms) {
            setFormError('Please agree to the Terms of Service and Privacy Policy');
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
        <div className="min-h-screen bg-linear-to-br from-slate-900 to-slate-800 flex items-center justify-center p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-lg shadow-xl w-full max-w-md">
                <div className="bg-linear-to-r from-blue-600 to-blue-700 p-8 text-white">
                    <h1 className="text-3xl font-bold">Create Account</h1>
                    <p className="text-blue-100 mt-2">Join dYdX Backtest Trading</p>
                </div>

                <div className="p-8">
                    {error && (
                        <div className="mb-6 p-4 bg-red-900 border border-red-700 rounded-lg flex items-start gap-3">
                            <AlertCircle className="w-5 h-5 text-red-300 shrink-0 mt-0.5" />
                            <div className="text-red-200 text-sm">{error}</div>
                        </div>
                    )}

                    {formError && (
                        <div className="mb-6 p-4 bg-red-900 border border-red-700 rounded-lg flex items-start gap-3">
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
                                value={formData.username}
                                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                className={`w-full px-4 py-2 border rounded-lg bg-slate-700 text-white placeholder-slate-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                                    validationErrors.username ? 'border-red-500' : 'border-slate-600'
                                }`}
                                placeholder="john_doe"
                                disabled={loading}
                            />
                            {validationErrors.username && (
                                <p className="text-xs text-red-300 mt-1">{validationErrors.username}</p>
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
                                value={formData.email}
                                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                className={`w-full px-4 py-2 border rounded-lg bg-slate-700 text-white placeholder-slate-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                                    validationErrors.email ? 'border-red-500' : 'border-slate-600'
                                }`}
                                placeholder="john@example.com"
                                disabled={loading}
                            />
                            {validationErrors.email && (
                                <p className="text-xs text-red-300 mt-1">{validationErrors.email}</p>
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
                                value={formData.password}
                                onChange={handlePasswordChange}
                                className={`w-full px-4 py-2 border rounded-lg bg-slate-700 text-white placeholder-slate-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                                    validationErrors.password ? 'border-red-500' : 'border-slate-600'
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
                                <p className="text-xs text-red-300 mt-1">{validationErrors.password}</p>
                            )}
                            <p className="text-xs text-slate-400 mt-2">
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
                                value={formData.confirmPassword}
                                onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                                className={`w-full px-4 py-2 border rounded-lg bg-slate-700 text-white placeholder-slate-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                                    validationErrors.confirmPassword ? 'border-red-500' : 'border-slate-600'
                                }`}
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
                                <p className="text-xs text-red-300 mt-1">{validationErrors.confirmPassword}</p>
                            )}
                        </div>

                        {/* Terms Agreement */}
                        <div className="flex items-start gap-3 pt-2">
                            <input
                                type="checkbox"
                                id="terms"
                                checked={formData.agreedToTerms}
                                onChange={(e) => setFormData({ ...formData, agreedToTerms: e.target.checked })}
                                className="mt-1"
                                disabled={loading}
                            />
                            <label htmlFor="terms" className="text-xs text-slate-400">
                                I agree to the{' '}
                                <a href="#" className="text-blue-400 hover:underline">
                                    Terms of Service
                                </a>
                                {' '}and{' '}
                                <a href="#" className="text-blue-400 hover:underline">
                                    Privacy Policy
                                </a>
                            </label>
                        </div>

                        {/* Submit Button */}
                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium flex items-center justify-center gap-2 mt-6"
                        >
                            {loading && <Loader className="w-4 h-4 animate-spin" />}
                            {loading ? 'Creating Account...' : 'Create Account'}
                        </button>
                    </form>

                    <p className="mt-6 text-center text-sm text-slate-400">
                        Already have an account?{' '}
                        <button
                            onClick={() => navigate('/login')}
                            className="text-blue-400 hover:underline font-medium"
                        >
                            Login
                        </button>
                    </p>
                </div>
            </div>
        </div>
    );
};
