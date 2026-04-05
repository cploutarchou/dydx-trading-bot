import { useQuery } from '@tanstack/react-query';
import { Loader } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { useAuthStore } from '../store/auth';

export const LoginPage: React.FC = () => {
    const navigate = useNavigate();
    const { login, loading, error } = useAuthStore();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const usernameInputRef = useRef<HTMLInputElement | null>(null);
    const errorAlertRef = useRef<HTMLDivElement | null>(null);
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
            errorAlertRef.current?.focus();
        }
    }, [error]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await login(username, password);
            navigate('/dashboard');
        } catch (err) {
            console.error('❌ LoginPage: Error during login:', err);
        }
    };

    return (
        <div className="auth-stage flex items-center justify-center px-4 py-10">
            <div className="premium-orb left-[8%] top-[12%] h-48 w-48 bg-cyan-500/15" />
            <div className="premium-orb right-[8%] bottom-[10%] h-56 w-56 bg-blue-500/15" />

            <div className="grid w-full max-w-6xl gap-8 lg:grid-cols-[1.05fr,0.95fr] lg:items-center">
                <div className="hidden lg:block">
                    <div className="premium-kicker">Institutional-grade trading intelligence</div>
                    <h1 className="mt-5 max-w-2xl text-5xl font-bold leading-tight text-white">
                        A trading workspace that feels built for serious capital.
                    </h1>
                    <p className="mt-5 max-w-xl text-base leading-7 text-slate-300">
                        Monitor strategy quality, live runtime status, market intelligence, and backtest confidence from one polished operations cockpit.
                    </p>
                    <div className="mt-8 grid max-w-xl grid-cols-3 gap-4">
                        <div className="premium-panel premium-panel-hover">
                            <p className="text-2xl font-semibold text-white">Live</p>
                            <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-500">Runtime control</p>
                        </div>
                        <div className="premium-panel premium-panel-hover">
                            <p className="text-2xl font-semibold text-white">Risk</p>
                            <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-500">Aware analytics</p>
                        </div>
                        <div className="premium-panel premium-panel-hover">
                            <p className="text-2xl font-semibold text-white">News</p>
                            <p className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-500">Market context</p>
                        </div>
                    </div>
                </div>

                <div className="auth-panel w-full max-w-xl justify-self-center p-8 sm:p-10">
                    <div className="mb-8">
                        <div className="premium-kicker">Welcome back</div>
                        <h2 className="mt-4 text-3xl font-bold text-white">Sign in to dYdX Bot</h2>
                        <p className="mt-2 text-sm text-slate-400">
                            Access your premium trading workspace, latest intelligence, and live execution controls.
                        </p>
                    </div>

                {error && (
                    <div
                        ref={errorAlertRef}
                        tabIndex={-1}
                        role="alert"
                        aria-live="assertive"
                        className="mb-4 rounded-2xl border border-red-700 bg-red-950/55 p-4 text-red-200"
                    >
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label htmlFor="login-username" className="block text-sm font-medium text-slate-300 mb-2">
                            Username
                        </label>
                        <input
                            id="login-username"
                            type="text"
                            autoComplete="username"
                            ref={usernameInputRef}
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            className="premium-input"
                            required
                        />
                    </div>

                    <div>
                        <label htmlFor="login-password" className="block text-sm font-medium text-slate-300 mb-2">
                            Password
                        </label>
                        <input
                            id="login-password"
                            type="password"
                            autoComplete="current-password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="premium-input"
                            required
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className="premium-button premium-button-primary w-full disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        {loading && <Loader className="w-4 h-4 animate-spin" />}
                        {loading ? 'Logging in...' : 'Enter Workspace'}
                    </button>
                </form>

                <p className="mt-5 text-center text-sm text-slate-400">
                    {registrationStatusQuery.data?.enabled === false ? (
                        <span className="text-slate-500">
                            Public registration is currently disabled by the administrator.
                        </span>
                    ) : (
                        <>
                            Don&apos;t have an account?{' '}
                            <button
                                type="button"
                                onClick={() => navigate('/register')}
                                className="font-medium text-cyan-300 hover:text-cyan-200"
                            >
                                Register
                            </button>
                        </>
                    )}
                </p>
            </div>
            </div>
        </div>
    );
};
