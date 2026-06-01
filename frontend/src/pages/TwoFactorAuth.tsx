import { AlertCircle, CheckCircle, Copy, Eye, EyeOff, Loader } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AuthExperienceShell from '../components/AuthExperienceShell';
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
  const setupButtonRef = useRef<HTMLButtonElement | null>(null);
  const verifyTokenInputRef = useRef<HTMLInputElement | null>(null);
  const apiErrorAlertRef = useRef<HTMLDivElement | null>(null);
  const localErrorAlertRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (step === 'setup') {
      setupButtonRef.current?.focus();
    }
    if (step === 'verify' && twoFAQRCode) {
      verifyTokenInputRef.current?.focus();
    }
  }, [step, twoFAQRCode]);

  useEffect(() => {
    if (error) {
      apiErrorAlertRef.current?.focus();
      return;
    }
    if (localError) {
      localErrorAlertRef.current?.focus();
    }
  }, [error, localError]);

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
    <AuthExperienceShell
      kicker="Security setup"
      title="Activate two-factor authentication"
      description="Protect access to your execution workspace before entering production operations. This is a critical step for any serious operator account."
      sideLabel="Operator Security"
      sideTitle="Security belongs in the core product experience, not as an afterthought."
      sideDescription="2FA setup should feel like part of a premium execution system: clear, trustworthy, and aligned with the value of the platform behind it."
    >
      <div className="twofa-stepper mb-6 grid gap-2 sm:grid-cols-4">
        {['setup', 'verify', 'backup-codes', 'complete'].map((item, index) => (
          <div
            key={item}
            className={`twofa-step-chip ${step === item ? 'is-active' : ''} ${
              ['verify', 'backup-codes', 'complete'].includes(item) && step === 'setup'
                ? 'is-locked'
                : ''
            }`}
          >
            <span>{String(index + 1).padStart(2, '0')}</span>
            <strong>{item === 'backup-codes' ? 'backup' : item}</strong>
          </div>
        ))}
      </div>

      {error && (
        <div
          ref={apiErrorAlertRef}
          tabIndex={-1}
          role="alert"
          aria-live="assertive"
          className="mb-6 flex items-start gap-3 rounded-lg border border-red-700 bg-red-950/55 p-4"
        >
          <AlertCircle className="w-5 h-5 text-red-300 shrink-0 mt-0.5" />
          <div className="text-red-200">{error}</div>
        </div>
      )}

      {localError && (
        <div
          ref={localErrorAlertRef}
          tabIndex={-1}
          role="alert"
          aria-live="assertive"
          className="mb-6 flex items-start gap-3 rounded-lg border border-red-700 bg-red-950/55 p-4"
        >
          <AlertCircle className="w-5 h-5 text-red-300 shrink-0 mt-0.5" />
          <div className="text-red-200">{localError}</div>
        </div>
      )}

      {/* Step 1: Setup */}
      {step === 'setup' && (
        <div className="space-y-6">
          <div className="twofa-step-card">
            <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <span className="twofa-step-index">1</span>
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
            type="button"
            ref={setupButtonRef}
            onClick={handleSetup}
            disabled={loading}
            className="premium-button premium-button-primary w-full disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading && <Loader className="w-4 h-4 animate-spin" />}
            {loading ? 'Generating QR Code...' : 'Generate QR Code'}
          </button>
        </div>
      )}

      {/* Step 2: Verify */}
      {step === 'verify' && twoFAQRCode && (
        <div className="space-y-6">
          <div className="twofa-step-card">
            <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <span className="twofa-step-index">2</span>
              Scan QR Code
            </h2>
            <p className="text-slate-300 mb-4">Use your authenticator app to scan this QR code:</p>
            <div className="bg-white p-4 rounded-lg inline-block">
              <img src={twoFAQRCode} alt="2FA QR Code" className="w-64 h-64" />
            </div>
          </div>

          <div className="rounded-lg border border-amber-700/60 bg-amber-950/35 p-4">
            <p className="text-sm text-amber-200">
              <strong>Can&apos;t scan?</strong> Manual entry may be available in your authenticator
              app. Contact support if needed.
            </p>
          </div>

          <div className="space-y-4">
            <div>
              <label
                htmlFor="twofa-token"
                className="block text-sm font-medium text-slate-300 mb-2"
              >
                Enter 6-Digit Code
              </label>
              <input
                id="twofa-token"
                ref={verifyTokenInputRef}
                type="text"
                maxLength={6}
                inputMode="numeric"
                autoComplete="one-time-code"
                aria-invalid={verifyToken.length > 0 && verifyToken.length !== 6}
                aria-describedby="twofa-token-help"
                value={verifyToken}
                onChange={(e) => setVerifyToken(e.target.value.replace(/\D/g, ''))}
                placeholder="000000"
                className="premium-input text-center text-2xl tracking-widest font-mono"
              />
              <p id="twofa-token-help" className="text-xs text-slate-400 mt-2">
                Get a new code every 30 seconds from your authenticator app
              </p>
            </div>

            <button
              type="button"
              onClick={handleVerify}
              disabled={loading || verifyToken.length !== 6}
              className="premium-button premium-button-primary w-full disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading && <Loader className="w-4 h-4 animate-spin" />}
              {loading ? 'Verifying...' : 'Verify Code'}
            </button>
          </div>
        </div>
      )}

      {step === 'verify' && !twoFAQRCode && (
        <div className="rounded-lg border border-red-700 bg-red-950/55 p-4">
          <p className="text-sm text-red-200">
            QR code is not available yet. Please go back and generate a new setup code.
          </p>
        </div>
      )}

      {/* Step 3: Backup Codes */}
      {step === 'backup-codes' && backupCodes && (
        <div className="space-y-6">
          <div className="rounded-lg border border-emerald-700/70 bg-emerald-950/25 p-6">
            <div className="flex items-center gap-3 mb-4">
              <CheckCircle className="w-6 h-6 text-green-300" />
              <h2 className="text-xl font-bold text-white">Backup Codes Generated</h2>
            </div>
            <p className="text-slate-300">
              Save these backup codes in a secure location. Each code can be used once if you lose
              access to your authenticator.
            </p>
          </div>

          <div className="twofa-step-card p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-mono font-bold text-white">Backup Codes</h3>
              <button
                type="button"
                onClick={() => setShowBackupCodes(!showBackupCodes)}
                className="flex items-center gap-2 text-slate-300 hover:text-white"
              >
                {showBackupCodes ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
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
              type="button"
              onClick={handleCopyBackupCodes}
              className="premium-button premium-button-secondary w-full py-2 px-4 text-sm"
            >
              <Copy className="w-4 h-4" />
              {copiedCodes ? 'Copied to Clipboard!' : 'Copy Codes'}
            </button>
          </div>

          <div className="rounded-lg border border-red-700 bg-red-950/55 p-4">
            <p className="text-sm text-red-200">
              <strong>⚠️ Important:</strong> Store these codes securely. Do not share them with
              anyone.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setStep('complete')}
            className="premium-button premium-button-primary w-full"
          >
            I&apos;ve Saved My Backup Codes
          </button>
        </div>
      )}

      {/* Step 4: Complete */}
      {step === 'complete' && (
        <div className="space-y-6 text-center">
          <div className="flex justify-center mb-4">
            <div className="rounded-full border border-emerald-700/70 bg-emerald-950/30 p-4">
              <CheckCircle className="w-16 h-16 text-green-300" />
            </div>
          </div>

          <div>
            <h2 className="text-2xl font-bold text-white mb-2">Setup Complete!</h2>
            <p className="text-slate-300">
              Your account is now protected with two-factor authentication.
            </p>
          </div>

          <div className="rounded-lg border border-emerald-700/70 bg-emerald-950/25 p-4 text-left">
            <p className="text-sm text-green-200">
              <strong>What&apos;s next?</strong> You&apos;ll be asked to enter a code from your
              authenticator app each time you log in.
            </p>
          </div>

          <button
            type="button"
            onClick={handleComplete}
            className="premium-button premium-button-primary w-full"
          >
            Go to Dashboard
          </button>
        </div>
      )}
    </AuthExperienceShell>
  );
};
