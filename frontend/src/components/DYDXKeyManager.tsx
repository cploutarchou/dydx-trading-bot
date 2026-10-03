import { AxiosError } from 'axios';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import api from '../api';

interface DYDXKey {
  id: number;
  network: 'testnet' | 'mainnet';
  chain_address: string;
  secret_masked?: string;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
}

interface CreateKeyPayload {
  network: 'testnet' | 'mainnet';
  chain_address: string;
  secret_phrase: string;
}

/**
 * DYDXKeyManager Component
 *
 * Manages secure dYdX testnet and mainnet key storage.
 * Features:
 * - Create/read/delete keys via secure API
 * - Fernet encryption on backend
 * - User isolation (each user owns their keys)
 * - Real-time status updates
 * - Comprehensive error handling
 */
export const DYDXKeyManager: React.FC = () => {
  // Ensure keys is always an array to avoid null access errors
  const [keys, setKeys] = useState<DYDXKey[]>([]);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [showMnemonic, setShowMnemonic] = useState(false);
  const [confirmDeleteNetwork, setConfirmDeleteNetwork] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState<CreateKeyPayload>({
    network: 'testnet',
    chain_address: '',
    secret_phrase: '',
  });

  // Form validation state
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  // Guard against state updates after unmount
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  /**
   * Load all keys for current user
   */
  const loadKeys = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getKeys();
      if (!mountedRef.current) return;

      if (response && response.success && Array.isArray(response.data?.keys)) {
        setKeys(response.data.keys as DYDXKey[]);
      } else {
        setKeys([]);
      }
    } catch (err) {
      if (!mountedRef.current) return;
      const axiosError = err as AxiosError<{ detail?: string; message?: string }>;
      const errorMessage =
        axiosError.response?.data?.detail ||
        axiosError.response?.data?.message ||
        'Failed to load keys';
      setError(errorMessage);
      console.error('Failed to load keys:', err);
      setKeys([]);
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  // Load keys once on mount (no polling — keys are user-controlled).
  // Microtask keeps the loader's synchronous state reset out of the effect.
  useEffect(() => {
    void Promise.resolve().then(() => loadKeys());
  }, [loadKeys]);

  // Clear messages after 5 seconds
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 7000);
      return () => clearTimeout(timer);
    }
  }, [error]);

  /**
   * Validate form data
   */
  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!formData.network) {
      errors.network = 'Network is required';
    }

    if (!formData.chain_address || formData.chain_address.trim().length === 0) {
      errors.chain_address = 'Chain address is required';
    } else if (!formData.chain_address.startsWith('dydx1')) {
      errors.chain_address = 'Invalid dYdX address (must start with dydx1)';
    }

    if (!formData.secret_phrase || formData.secret_phrase.trim().length === 0) {
      errors.secret_phrase = 'Secret phrase is required';
    } else {
      const wordCount = formData.secret_phrase.trim().split(/\s+/).length;
      if (wordCount !== 12 && wordCount !== 24) {
        errors.secret_phrase = `Mnemonic must be 12 or 24 words (found ${wordCount})`;
      }
    }

    setFormErrors(errors as Partial<CreateKeyPayload>);
    return Object.keys(errors).length === 0;
  };

  /**
   * Handle adding/updating a key
   */
  const handleAddKey = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setFormSubmitting(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const response = await api.createKey(
        formData as unknown as Record<string, unknown> & {
          network: string;
          chain_address: string;
          secret_phrase: string;
        }
      );

      if (response.success) {
        setSuccessMessage(
          `✅ ${formData.network.charAt(0).toUpperCase() + formData.network.slice(1)} key saved successfully!`
        );
        setFormData({ network: 'testnet', chain_address: '', secret_phrase: '' });
        setFormErrors({});
        setShowAddForm(false);
        await loadKeys();
      }
    } catch (err) {
      const axiosError = err as AxiosError<{ detail?: string; message?: string }>;
      const errorMessage =
        axiosError.response?.data?.detail ||
        axiosError.response?.data?.message ||
        'Failed to save key';
      setError(`❌ ${errorMessage}`);
      console.error('Failed to add key:', err);
    } finally {
      setFormSubmitting(false);
    }
  };

  /**
   * Handle deleting a key
   */
  const handleDeleteKey = async (network: string) => {
    setDeleting(network);
    setError(null);

    try {
      await api.deleteKey(network);
      setConfirmDeleteNetwork(null);
      setSuccessMessage(`✅ ${network} key deleted successfully!`);
      await loadKeys();
    } catch (err) {
      const axiosError = err as AxiosError<{ detail?: string; message?: string }>;
      const errorMessage =
        axiosError.response?.data?.detail ||
        axiosError.response?.data?.message ||
        'Failed to delete key';
      setError(`❌ ${errorMessage}`);
      console.error('Failed to delete key:', err);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Section */}
      <div className="premium-panel p-6">
        <div className="mb-2 flex items-center justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-2xl font-bold text-white">
              <span className="text-cyan-300">🔐</span>
              dYdX Key Management
            </h2>
            <p className="mt-1 text-sm text-slate-400">
              Secure storage for your testnet and mainnet dYdX credentials
            </p>
          </div>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className={`rounded-xl px-4 py-2 font-medium transition-colors ${
              showAddForm
                ? 'border border-slate-700/70 bg-slate-900/70 text-white hover:border-cyan-500/35 hover:bg-slate-900'
                : 'bg-cyan-500 text-slate-900 hover:bg-cyan-400'
            }`}
          >
            {showAddForm ? '✕ Cancel' : '+ Add Key'}
          </button>
        </div>

        {/* Status Summary */}
        <div className="mt-4 rounded-lg border border-slate-700/60 bg-slate-800/45 p-3">
          <p className="text-slate-300 text-sm">
            <span className="font-medium">{Array.isArray(keys) ? keys.length : 0}</span> key(s)
            configured
            {Array.isArray(keys) && keys.length > 0 && (
              <>
                {' • '}
                <span className="text-emerald-400">All active</span>
              </>
            )}
          </p>
        </div>
      </div>

      {/* Alert Messages */}
      {error && (
        <div className="rounded-lg border border-red-700/40 bg-red-900/20 p-4">
          <p className="font-medium text-red-200">{error}</p>
        </div>
      )}
      {successMessage && (
        <div className="rounded-lg border border-emerald-700/40 bg-emerald-900/20 p-4">
          <p className="font-medium text-emerald-200">{successMessage}</p>
        </div>
      )}

      {/* Add Key Form */}
      {showAddForm && (
        <form onSubmit={handleAddKey} className="premium-panel p-6">
          <h3 className="mb-4 text-lg font-bold text-white">
            {keys.some((key) => key.network === formData.network)
              ? 'Update Stored Key'
              : 'Add New Key'}
          </h3>

          {/* Network Selection */}
          <div className="mb-6">
            <p className="mb-3 block font-medium text-white">Select Network</p>
            <div className="grid grid-cols-2 gap-4">
              {(['testnet', 'mainnet'] as const).map((net) => (
                <label
                  key={net}
                  className={`cursor-pointer rounded-lg border p-4 transition-all ${
                    formData.network === net
                      ? 'border-cyan-500/60 bg-cyan-500/10'
                      : 'border-slate-700 bg-slate-900/45 hover:border-slate-600'
                  }`}
                >
                  <input
                    type="radio"
                    name="network"
                    value={net}
                    checked={formData.network === net}
                    onChange={(e) => {
                      setFormData({
                        ...formData,
                        network: e.target.value as CreateKeyPayload['network'],
                      });
                      setFormErrors({});
                    }}
                    className="mr-2"
                  />
                  <span className="text-white font-medium capitalize">
                    {net === 'testnet' ? '🧪 Testnet' : '🚀 Mainnet'}
                  </span>
                  <p className="mt-1 text-xs text-slate-400">
                    {net === 'testnet' ? 'For testing and development' : 'For production trading'}
                  </p>
                  {keys.some((key) => key.network === net) && (
                    <p className="mt-2 text-xs text-cyan-300">
                      Existing stored secret will be updated
                    </p>
                  )}
                </label>
              ))}
            </div>
          </div>

          {/* Chain Address */}
          <div className="mb-6">
            <label className="mb-2 block font-medium text-white" htmlFor="chain-address">
              Chain Address
              <span className="text-red-400 ml-1">*</span>
            </label>
            <input
              id="chain-address"
              type="text"
              placeholder="dydx1xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              value={formData.chain_address}
              onChange={(e) => {
                setFormData({ ...formData, chain_address: e.target.value });
                if (formErrors.chain_address) {
                  const newErrors = { ...formErrors };
                  delete newErrors.chain_address;
                  setFormErrors(newErrors);
                }
              }}
              className={`premium-input ${
                formErrors.chain_address
                  ? 'border-red-600 focus:border-red-500 focus:ring-red-500'
                  : ''
              }`}
            />
            {formErrors.chain_address && (
              <p className="mt-1 text-xs text-red-400">{formErrors.chain_address}</p>
            )}
            <p className="mt-2 text-xs text-slate-400">
              Your dYdX chain address (starts with dydx1)
            </p>
          </div>

          {/* Secret Phrase */}
          <div className="mb-6">
            <label className="mb-2 block font-medium text-white" htmlFor="secret-phrase">
              Secret Phrase / Mnemonic
              <span className="text-red-400 ml-1">*</span>
            </label>
            {/* Masked while typing, matching the bot creation form: seed
                phrases are operational secrets and should not render on screen. */}
            <div className="relative">
              <input
                id="secret-phrase"
                type={showMnemonic ? 'text' : 'password'}
                autoComplete="off"
                spellCheck={false}
                placeholder="Enter your mnemonic seed phrase (12 or 24 words, space-separated)"
                value={formData.secret_phrase}
                onChange={(e) => {
                  setFormData({ ...formData, secret_phrase: e.target.value });
                  if (formErrors.secret_phrase) {
                    const newErrors = { ...formErrors };
                    delete newErrors.secret_phrase;
                    setFormErrors(newErrors);
                  }
                }}
                className={`premium-input pr-20 font-mono text-sm ${
                  formErrors.secret_phrase
                    ? 'border-red-600 focus:border-red-500 focus:ring-red-500'
                    : ''
                }`}
              />
              <button
                type="button"
                onClick={() => setShowMnemonic((visible) => !visible)}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded px-2 py-1 text-xs text-slate-400 hover:text-white"
                aria-label={showMnemonic ? 'Hide mnemonic' : 'Show mnemonic'}
              >
                {showMnemonic ? 'Hide' : 'Show'}
              </button>
            </div>
            {formErrors.secret_phrase && (
              <p className="mt-1 text-xs text-red-400">{formErrors.secret_phrase}</p>
            )}
            <div className="mt-2 rounded-lg border border-amber-700/40 bg-amber-900/20 p-3">
              <p className="text-yellow-200 text-xs">
                ⚠️ <span className="font-medium">Important:</span> Your seed phrase is encrypted and
                never stored in plain text. Keep it safe and never share it.
              </p>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={formSubmitting || loading}
            className={`flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 font-medium transition-colors ${
              formSubmitting || loading
                ? 'cursor-not-allowed bg-slate-700 text-slate-400'
                : 'bg-cyan-500 text-slate-900 hover:bg-cyan-400'
            }`}
          >
            {formSubmitting ? (
              <>
                <span className="inline-block w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></span>
                Saving...
              </>
            ) : (
              <>✓ Save Key</>
            )}
          </button>
        </form>
      )}

      {/* Keys List */}
      <div className="premium-panel p-6">
        <h3 className="mb-4 text-lg font-bold text-white">Your Keys</h3>

        <div className="space-y-3">
          {loading && !keys.length ? (
            <div className="py-12 text-center">
              <div className="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-3 border-slate-600 border-t-cyan-500"></div>
              <p className="text-slate-400">Loading keys...</p>
            </div>
          ) : Array.isArray(keys) && keys.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-600 bg-slate-800/50 py-12 text-center">
              <p className="mb-2 text-slate-400">🔑 No keys configured yet</p>
              <p className="text-slate-500 text-sm">Click &quot;Add Key&quot; to get started</p>
            </div>
          ) : (
            keys.map((key) => (
              <div
                key={key.id}
                className="rounded-lg border border-slate-700/60 bg-slate-800/45 p-4 transition-all hover:border-cyan-500/35"
              >
                <div className="flex items-center justify-between">
                  <div className="flex flex-1 items-center gap-4">
                    {/* Network Badge */}
                    <div
                      className={`flex items-center justify-center w-12 h-12 rounded-lg font-bold text-lg ${
                        key.network === 'testnet'
                          ? 'bg-orange-900/30 text-orange-400 border border-orange-700'
                          : 'bg-purple-900/30 text-purple-400 border border-purple-700'
                      }`}
                    >
                      {key.network === 'testnet' ? '🧪' : '🚀'}
                    </div>

                    {/* Key Info */}
                    <div className="flex-1 min-w-0">
                      <h4 className="text-white font-medium capitalize">{key.network} Key</h4>
                      <p className="text-slate-400 text-sm font-mono truncate">
                        {key.chain_address}
                      </p>
                      <p className="text-slate-500 text-xs mt-1">
                        📅 Added:{' '}
                        {key.created_at
                          ? `${new Date(key.created_at).toLocaleDateString()} at ${new Date(key.created_at).toLocaleTimeString()}`
                          : 'Unknown'}
                      </p>
                      <p className="mt-2 text-xs text-slate-500">Masked secret</p>
                      <p className="max-w-full overflow-hidden break-all whitespace-normal font-mono text-xs text-slate-300">
                        {key.secret_masked || 'Stored and masked'}
                      </p>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="ml-4 flex items-center gap-2">
                    {/* Active Badge */}
                    {key.is_active && (
                      <span className="px-3 py-1 bg-green-900/50 border border-green-700 text-green-300 rounded-full text-xs font-medium">
                        ✓ Active
                      </span>
                    )}

                    {/* Delete Button */}
                    {confirmDeleteNetwork === key.network ? (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => void handleDeleteKey(key.network)}
                          disabled={deleting === key.network}
                          className={`rounded-lg px-3 py-1 text-sm font-medium transition-all ${
                            deleting === key.network
                              ? 'cursor-not-allowed bg-slate-700 text-slate-400'
                              : 'bg-red-700 hover:bg-red-800 border border-red-600 text-white'
                          }`}
                        >
                          {deleting === key.network ? 'Deleting...' : 'Confirm Delete'}
                        </button>
                        <button
                          onClick={() => setConfirmDeleteNetwork(null)}
                          disabled={deleting === key.network}
                          className="rounded-lg bg-slate-700 px-3 py-1 text-sm font-medium text-white transition-all hover:bg-slate-600"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmDeleteNetwork(key.network)}
                        disabled={deleting === key.network}
                        className={`rounded-lg px-3 py-1 text-sm font-medium transition-all ${
                          deleting === key.network
                            ? 'cursor-not-allowed bg-slate-700 text-slate-400'
                            : 'bg-red-900/50 hover:bg-red-900 border border-red-700 text-red-300 hover:text-red-200'
                        }`}
                      >
                        🗑️ Delete
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Security Info Card */}
      <div className="rounded-lg border border-cyan-700/40 bg-cyan-900/20 p-6">
        <h3 className="mb-3 flex items-center gap-2 font-bold text-white">
          <span className="text-lg">🔒</span>
          Security Information
        </h3>
        <ul className="space-y-2 text-slate-300 text-sm">
          <li className="flex gap-2">
            <span className="text-green-400 font-bold">✓</span>
            <span>
              Keys are encrypted at rest and stored with an additional one-way fingerprint for safer
              operational handling
            </span>
          </li>
          <li className="flex gap-2">
            <span className="text-green-400 font-bold">✓</span>
            <span>Your secret phrase is never stored in plain text</span>
          </li>
          <li className="flex gap-2">
            <span className="text-green-400 font-bold">✓</span>
            <span>Only you can access your own keys (user isolation)</span>
          </li>
          <li className="flex gap-2">
            <span className="text-green-400 font-bold">✓</span>
            <span>All communication is encrypted over HTTPS</span>
          </li>
          <li className="flex gap-2">
            <span className="text-orange-400 font-bold">⚠</span>
            <span>Deleted keys cannot be recovered - be careful</span>
          </li>
        </ul>
      </div>

      {/* Help Section */}
      <div className="premium-panel p-6">
        <h3 className="mb-3 font-bold text-white">Need Help?</h3>
        <div className="space-y-2 text-slate-400 text-sm">
          <p>
            <span className="text-white font-medium">
              Q: Where do I get my dYdX address and seed phrase?
            </span>
            <br className="mt-1" />
            A: You&apos;ll find these in your dYdX wallet or when you create a new account on dYdX.
          </p>
          <p className="pt-2">
            <span className="text-white font-medium">
              Q: Can I use the same key for both testnet and mainnet?
            </span>
            <br className="mt-1" />
            A: No, testnet and mainnet use different keys. You need to add both separately.
          </p>
          <p className="pt-2">
            <span className="text-white font-medium">Q: Is my seed phrase secure here?</span>
            <br className="mt-1" />
            A: Yes! It&apos;s encrypted on the server and only decrypted when you specifically
            request it.
          </p>
        </div>
      </div>
    </div>
  );
};

export default DYDXKeyManager;
