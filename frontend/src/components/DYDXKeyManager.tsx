import { AxiosError } from 'axios';
import React, { useEffect, useState } from 'react';
import api from '../api';

interface DYDXKey {
  id: number;
  network: 'testnet' | 'mainnet';
  chain_address: string;
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
  const [confirmDeleteNetwork, setConfirmDeleteNetwork] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState<CreateKeyPayload>({
    network: 'testnet',
    chain_address: '',
    secret_phrase: '',
  });

  // Form validation state
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  // Load keys on mount and set up polling
  useEffect(() => {
    loadKeys();

    // Optional: Set up auto-refresh every 30 seconds
    const interval = setInterval(loadKeys, 30000);
    return () => clearInterval(interval);
  }, []);

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
   * Load all keys for current user
   */
  const loadKeys = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getKeys();

      if (response && response.success && Array.isArray(response.data?.keys)) {
        setKeys(response.data.keys as DYDXKey[]);
      } else {
        setKeys([]);
      }
    } catch (err) {
      const axiosError = err as AxiosError<{ detail?: string; message?: string }>;
      const errorMessage =
        axiosError.response?.data?.detail ||
        axiosError.response?.data?.message ||
        'Failed to load keys';
      setError(errorMessage);
      console.error('Failed to load keys:', err);
      setKeys([]);
    } finally {
      setLoading(false);
    }
  };

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
      <div className="bg-slate-900 rounded-lg border border-slate-700 p-6">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h2 className="text-2xl font-bold text-white flex items-center gap-2">
              <span className="text-yellow-400">🔐</span>
              dYdX Key Management
            </h2>
            <p className="text-slate-400 text-sm mt-1">
              Secure storage for your testnet and mainnet dYdX credentials
            </p>
          </div>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className={`px-4 py-2 rounded-lg transition-colors font-medium ${
              showAddForm
                ? 'bg-slate-700 hover:bg-slate-600 text-white'
                : 'bg-blue-600 hover:bg-blue-700 text-white'
            }`}
          >
            {showAddForm ? '✕ Cancel' : '+ Add Key'}
          </button>
        </div>

        {/* Status Summary */}
        <div className="mt-4 p-3 bg-slate-800/50 rounded-lg border border-slate-700">
          <p className="text-slate-300 text-sm">
            <span className="font-medium">{Array.isArray(keys) ? keys.length : 0}</span> key(s)
            configured
            {Array.isArray(keys) && keys.length > 0 && (
              <>
                {' • '}
                <span className="text-green-400">All active</span>
              </>
            )}
          </p>
        </div>
      </div>

      {/* Alert Messages */}
      {error && (
        <div className="p-4 bg-red-900/30 border border-red-700 rounded-lg">
          <p className="text-red-200 font-medium">{error}</p>
        </div>
      )}
      {successMessage && (
        <div className="p-4 bg-green-900/30 border border-green-700 rounded-lg">
          <p className="text-green-200 font-medium">{successMessage}</p>
        </div>
      )}

      {/* Add Key Form */}
      {showAddForm && (
        <form
          onSubmit={handleAddKey}
          className="bg-slate-900 rounded-lg border border-slate-700 p-6"
        >
          <h3 className="text-lg font-bold text-white mb-4">Add New Key</h3>

          {/* Network Selection */}
          <div className="mb-6">
            <label className="block text-white font-medium mb-3">Select Network</label>
            <div className="grid grid-cols-2 gap-4">
              {(['testnet', 'mainnet'] as const).map((net) => (
                <label
                  key={net}
                  className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                    formData.network === net
                      ? 'border-blue-500 bg-blue-900/30'
                      : 'border-slate-600 bg-slate-800 hover:border-slate-500'
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
                  <p className="text-slate-400 text-xs mt-1">
                    {net === 'testnet' ? 'For testing and development' : 'For production trading'}
                  </p>
                </label>
              ))}
            </div>
          </div>

          {/* Chain Address */}
          <div className="mb-6">
            <label className="block text-white font-medium mb-2">
              Chain Address
              <span className="text-red-400 ml-1">*</span>
            </label>
            <input
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
              className={`w-full px-4 py-2 bg-slate-800 border-2 rounded-lg text-white placeholder-slate-500 focus:outline-none transition-all ${
                formErrors.chain_address
                  ? 'border-red-600 focus:ring-2 focus:ring-red-500/50'
                  : 'border-slate-600 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20'
              }`}
            />
            {formErrors.chain_address && (
              <p className="text-red-400 text-xs mt-1">{formErrors.chain_address}</p>
            )}
            <p className="text-slate-400 text-xs mt-2">
              Your dYdX chain address (starts with dydx1)
            </p>
          </div>

          {/* Secret Phrase */}
          <div className="mb-6">
            <label className="block text-white font-medium mb-2">
              Secret Phrase / Mnemonic
              <span className="text-red-400 ml-1">*</span>
            </label>
            <textarea
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
              className={`w-full h-32 px-4 py-2 bg-slate-800 border-2 rounded-lg text-white placeholder-slate-500 focus:outline-none font-mono text-sm transition-all resize-none ${
                formErrors.secret_phrase
                  ? 'border-red-600 focus:ring-2 focus:ring-red-500/50'
                  : 'border-slate-600 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20'
              }`}
            />
            {formErrors.secret_phrase && (
              <p className="text-red-400 text-xs mt-1">{formErrors.secret_phrase}</p>
            )}
            <div className="mt-2 p-3 bg-yellow-900/20 border border-yellow-700/50 rounded-lg">
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
            className={`w-full px-4 py-3 rounded-lg transition-colors font-medium flex items-center justify-center gap-2 ${
              formSubmitting || loading
                ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                : 'bg-green-600 hover:bg-green-700 text-white'
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
      <div className="bg-slate-900 rounded-lg border border-slate-700 p-6">
        <h3 className="text-lg font-bold text-white mb-4">Your Keys</h3>

        <div className="space-y-3">
          {loading && !keys.length ? (
            <div className="text-center py-12">
              <div className="inline-block w-8 h-8 border-3 border-slate-600 border-t-blue-500 rounded-full animate-spin mb-4"></div>
              <p className="text-slate-400">Loading keys...</p>
            </div>
          ) : Array.isArray(keys) && keys.length === 0 ? (
            <div className="text-center py-12 bg-slate-800/50 rounded-lg border border-dashed border-slate-600">
              <p className="text-slate-400 mb-2">🔑 No keys configured yet</p>
              <p className="text-slate-500 text-sm">Click &quot;Add Key&quot; to get started</p>
            </div>
          ) : (
            keys.map((key) => (
              <div
                key={key.id}
                className="p-4 bg-slate-800 border border-slate-700 rounded-lg hover:border-slate-600 transition-all"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4 flex-1">
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
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 ml-4">
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
                          className={`px-3 py-1 rounded-lg text-sm font-medium transition-all ${
                            deleting === key.network
                              ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                              : 'bg-red-700 hover:bg-red-800 border border-red-600 text-white'
                          }`}
                        >
                          {deleting === key.network ? 'Deleting...' : 'Confirm Delete'}
                        </button>
                        <button
                          onClick={() => setConfirmDeleteNetwork(null)}
                          disabled={deleting === key.network}
                          className="px-3 py-1 rounded-lg text-sm font-medium transition-all bg-slate-700 hover:bg-slate-600 text-white"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmDeleteNetwork(key.network)}
                        disabled={deleting === key.network}
                        className={`px-3 py-1 rounded-lg text-sm font-medium transition-all ${
                          deleting === key.network
                            ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
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
      <div className="bg-linear-to-r from-blue-900/30 to-indigo-900/30 rounded-lg border border-blue-700 p-6">
        <h3 className="text-white font-bold mb-3 flex items-center gap-2">
          <span className="text-lg">🔒</span>
          Security Information
        </h3>
        <ul className="space-y-2 text-slate-300 text-sm">
          <li className="flex gap-2">
            <span className="text-green-400 font-bold">✓</span>
            <span>
              Keys are encrypted with{' '}
              <code className="bg-slate-800 px-2 py-1 rounded text-xs">Fernet</code> symmetric
              encryption
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
      <div className="bg-slate-900 rounded-lg border border-slate-700 p-6">
        <h3 className="text-white font-bold mb-3">Need Help?</h3>
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
            A: Yes! It&apos;s encrypted on the server and only decrypted when you specifically request
            it.
          </p>
        </div>
      </div>
    </div>
  );
};

export default DYDXKeyManager;
