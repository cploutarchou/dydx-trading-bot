import { AlertCircle, CheckCircle, Copy, Eye, EyeOff, Loader, Shield } from 'lucide-react';
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/auth';

type TwoFAStep = 'setup' | 'verify' | 'backup-codes' | 'complete';

export const TwoFactorAuthPage: React.FC = () => {
    const navigate = useNavigate();
    const { setup2FA, verify2FA, loading, error, twoFAQRCode, backupCodes } = useAuthStore();
    const [step, setStep] = useState<TwoFAStep>('setup');
    const [verifyToken, setVerifyToken] = useState('');
    const [showBackupCodes, setShowBackupCodes] = useState(false);
    const [copiedCodes, setCopiedCodes] = useState(false);
    const [localError, setLocalError] = useState<string | null>(null);

    const handleSetup = async () => {
        setLocalError(null);
        try {
            await setup2FA();
            setStep('verify');
        } catch (err) {
            setLocalError(err instanceof Error ? err.message : 'Failed to initialize 2FA setup');
            console.error('❌ TwoFactorAuth: Setup failed:', err);
        }
    };

    const handleVerify = async () => {
        setLocalError(null);
        if (verifyToken.length !== 6) {
            setLocalError('Please enter a valid 6-digit code');
            return;
        }
        try {
            await verify2FA(verifyToken);
            setStep('backup-codes');
        } catch (err) {
            setLocalError(err instanceof Error ? err.message : 'Failed to verify code');
            console.error('❌ TwoFactorAuth: Verification failed:', err);
        }
    };

    const handleCopyBackupCodes = async () => {
        if (backupCodes) {
            const codesText = backupCodes.join('\n');
            try {
                await navigator.clipboard.writeText(codesText);
                setCopiedCodes(true);
                setTimeout(() => setCopiedCodes(false), 2000);
            } catch (err) {
                console.error('❌ TwoFactorAuth: Failed to copy codes:', err);
                setLocalError('Could not copy to clipboard. Please copy the backup codes manually.');
            }
        }
    };

    const handleComplete = () => {
        navigate('/dashboard');
    };

    return (
        <div className="min-h-screen bg-linear-to-br from-slate-900 to-slate-800 flex items-center justify-center p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-lg shadow-xl w-full max-w-2xl">
                {/* Header */}
                <div className="bg-linear-to-r from-blue-600 to-blue-700 p-8 text-white flex items-center gap-4">
                    <Shield className="w-8 h-8" />
                    <div>
                        <h1 className="text-3xl font-bold">Two-Factor Authentication</h1>
                        <p className="text-blue-100">Secure your account with TOTP</p>
                    </div>
                </div>

                <div className="p-8">
                    {/* Error Alert */}
                    {error && (
                        <div className="mb-6 p-4 bg-red-900 border border-red-700 rounded-lg flex items-start gap-3">
                            <AlertCircle className="w-5 h-5 text-red-300 shrink-0 mt-0.5" />
                            <div className="text-red-200">{error}</div>
                        </div>
                    )}

                    {localError && (
                        <div className="mb-6 p-4 bg-red-900 border border-red-700 rounded-lg flex items-start gap-3">
                            <AlertCircle className="w-5 h-5 text-red-300 shrink-0 mt-0.5" />
                            <div className="text-red-200">{localError}</div>
                        </div>
                    )}

                    {/* Step 1: Setup */}
                    {step === 'setup' && (
                        <div className="space-y-6">
                            <div className="bg-slate-900 border border-slate-700 rounded-lg p-6">
                                <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                                    <span className="bg-blue-600 text-white rounded-full w-8 h-8 flex items-center justify-center text-sm">1</span>
                                    Download an Authenticator App
                                </h2>
                                <p className="text-slate-300 mb-4">
                                    Use any TOTP-compatible app to generate time-based codes. Popular choices:
                                </p>
                                <ul className="grid grid-cols-2 gap-3 text-sm">
                                    <li className="flex items-center gap-2">
                                        <CheckCircle className="w-4 h-4 text-green-400" />
                                        Google Authenticator
                                    </li>
                                    <li className="flex items-center gap-2">
                                        <CheckCircle className="w-4 h-4 text-green-400" />
                                        Microsoft Authenticator
                                    </li>
                                    <li className="flex items-center gap-2">
                                        <CheckCircle className="w-4 h-4 text-green-400" />
                                        Authy
                                    </li>
                                    <li className="flex items-center gap-2">
                                        <CheckCircle className="w-4 h-4 text-green-400" />
                                        FreeOTP
                                    </li>
                                </ul>
                            </div>

                            <button
                                onClick={handleSetup}
                                disabled={loading}
                                className="w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium flex items-center justify-center gap-2"
                            >
                                {loading && <Loader className="w-4 h-4 animate-spin" />}
                                {loading ? 'Generating QR Code...' : 'Generate QR Code'}
                            </button>
                        </div>
                    )}

                    {/* Step 2: Verify */}
                    {step === 'verify' && twoFAQRCode && (
                        <div className="space-y-6">
                            <div className="bg-slate-900 border border-slate-700 rounded-lg p-6">
                                <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                                    <span className="bg-blue-600 text-white rounded-full w-8 h-8 flex items-center justify-center text-sm">2</span>
                                    Scan QR Code
                                </h2>
                                <p className="text-slate-300 mb-4">
                                    Use your authenticator app to scan this QR code:
                                </p>
                                <div className="bg-white p-4 rounded-lg inline-block">
                                    <img
                                        src={twoFAQRCode}
                                        alt="2FA QR Code"
                                        className="w-64 h-64"
                                    />
                                </div>
                            </div>

                            <div className="bg-amber-900/30 border border-amber-700 rounded-lg p-4">
                                <p className="text-sm text-amber-200">
                                    <strong>Can&apos;t scan?</strong> Manual entry may be available in your authenticator app. Contact support if needed.
                                </p>
                            </div>

                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-300 mb-2">
                                        Enter 6-Digit Code
                                    </label>
                                    <input
                                        type="text"
                                        maxLength={6}
                                        value={verifyToken}
                                        onChange={(e) => setVerifyToken(e.target.value.replace(/\D/g, ''))}
                                        placeholder="000000"
                                        className="w-full px-4 py-3 border border-slate-600 bg-slate-700 rounded-lg text-center text-2xl tracking-widest font-mono text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                    />
                                    <p className="text-xs text-slate-400 mt-2">
                                        Get a new code every 30 seconds from your authenticator app
                                    </p>
                                </div>

                                <button
                                    onClick={handleVerify}
                                    disabled={loading || verifyToken.length !== 6}
                                    className="w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium flex items-center justify-center gap-2"
                                >
                                    {loading && <Loader className="w-4 h-4 animate-spin" />}
                                    {loading ? 'Verifying...' : 'Verify Code'}
                                </button>
                            </div>
                        </div>
                    )}

                    {step === 'verify' && !twoFAQRCode && (
                        <div className="bg-red-900 border border-red-700 rounded-lg p-4">
                            <p className="text-sm text-red-200">
                                QR code is not available yet. Please go back and generate a new setup code.
                            </p>
                        </div>
                    )}

                    {/* Step 3: Backup Codes */}
                    {step === 'backup-codes' && backupCodes && (
                        <div className="space-y-6">
                            <div className="bg-green-900/30 border border-green-700 rounded-lg p-6">
                                <div className="flex items-center gap-3 mb-4">
                                    <CheckCircle className="w-6 h-6 text-green-300" />
                                    <h2 className="text-xl font-bold text-white">
                                        Backup Codes Generated
                                    </h2>
                                </div>
                                <p className="text-slate-300">
                                    Save these backup codes in a secure location. Each code can be used once if you lose access to your authenticator.
                                </p>
                            </div>

                            <div className="bg-slate-900 rounded-lg p-6 border border-slate-700">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="font-mono font-bold text-white">Backup Codes</h3>
                                    <button
                                        onClick={() => setShowBackupCodes(!showBackupCodes)}
                                        className="flex items-center gap-2 text-slate-300 hover:text-white"
                                    >
                                        {showBackupCodes ? (
                                            <EyeOff className="w-4 h-4" />
                                        ) : (
                                            <Eye className="w-4 h-4" />
                                        )}
                                        {showBackupCodes ? 'Hide' : 'Show'}
                                    </button>
                                </div>

                                {showBackupCodes ? (
                                    <div className="bg-white rounded p-4 font-mono text-sm space-y-1 mb-4">
                                        {backupCodes.map((code, idx) => (
                                            <div key={idx} className="text-slate-700">
                                                {code}
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="bg-slate-800 border border-slate-700 rounded p-4 text-center text-slate-400">
                                        •••••••• •••••••• •••••••• ••••••••
                                    </div>
                                )}

                                <button
                                    onClick={handleCopyBackupCodes}
                                    className="w-full py-2 px-4 bg-slate-700 hover:bg-slate-600 rounded text-white font-medium flex items-center justify-center gap-2 text-sm"
                                >
                                    <Copy className="w-4 h-4" />
                                    {copiedCodes ? 'Copied to Clipboard!' : 'Copy Codes'}
                                </button>
                            </div>

                            <div className="bg-red-900 border border-red-700 rounded-lg p-4">
                                <p className="text-sm text-red-200">
                                    <strong>⚠️ Important:</strong> Store these codes securely. Do not share them with anyone.
                                </p>
                            </div>

                            <button
                                onClick={() => setStep('complete')}
                                className="w-full bg-green-600 text-white py-3 rounded-lg hover:bg-green-700 font-medium"
                            >
                                I&apos;ve Saved My Backup Codes
                            </button>
                        </div>
                    )}

                    {/* Step 4: Complete */}
                    {step === 'complete' && (
                        <div className="space-y-6 text-center">
                            <div className="flex justify-center mb-4">
                                <div className="bg-green-900/30 rounded-full p-4 border border-green-700">
                                    <CheckCircle className="w-16 h-16 text-green-300" />
                                </div>
                            </div>

                            <div>
                                <h2 className="text-2xl font-bold text-white mb-2">
                                    Setup Complete!
                                </h2>
                                <p className="text-slate-300">
                                    Your account is now protected with two-factor authentication.
                                </p>
                            </div>

                            <div className="bg-green-900/30 border border-green-700 rounded-lg p-4 text-left">
                                <p className="text-sm text-green-200">
                                    <strong>What&apos;s next?</strong> You&apos;ll be asked to enter a code from your authenticator app each time you log in.
                                </p>
                            </div>

                            <button
                                onClick={handleComplete}
                                className="w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 font-medium"
                            >
                                Go to Dashboard
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
