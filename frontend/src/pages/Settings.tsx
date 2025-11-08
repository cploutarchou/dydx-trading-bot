/**
 * Settings Page - User & System Configuration Management
 * 
 * Allows users to view and modify:
 * - Profile Settings (avatar, name, email)
 * - dYdX Key Management (testnet/mainnet keys)
 * - Logging (log level, Loki integration)
 * - Telegram (notification settings)
 * - dYdX Connection (testnet/mainnet, chain ID, mnemonic)
 * 
 * NOTE: Bot Settings and Backtesting moved to Strategies page for per-strategy configuration
 */

import { useEffect, useState } from 'react';
import apiClient from '../api';
import { DYDXKeyManager } from '../components/DYDXKeyManager';
import { ProfileSettings } from '../components/ProfileSettings';

interface SettingField {
  key: string;
  label: string;
  description: string;
  value_type: string;
  default_value: any;
  required: boolean;
  value?: any;
  min_value?: number;
  max_value?: number;
  options?: string[];
  placeholder?: string;
}

interface SettingSection {
  section: string;
  title: string;
  description: string;
  fields: SettingField[];
}

interface SettingsSchema {
  sections: SettingSection[];
}

interface SavedSettings {
  sections: Array<{
    section: string;
    settings: SettingField[];
  }>;
}

export default function Settings() {
  const [schema, setSchema] = useState<SettingsSchema | null>(null);
  const [settings, setSettings] = useState<SavedSettings | null>(null);
  const [formValues, setFormValues] = useState<Record<string, Record<string, any>>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);
  const [activeSection, setActiveSection] = useState<string>('profile');

  useEffect(() => {
    fetchSettingsData();
  }, []);

  const fetchSettingsData = async () => {
    try {
      setLoading(true);
      
      // First, try to initialize settings (idempotent - no-op if already initialized)
      try {
        await apiClient.initializeSettings();
      } catch (e) {
        // Initialization might fail if settings already exist, which is fine
        console.log('Settings already initialized or initialization skipped');
      }

      const [schemaResponse, settingsResponse] = await Promise.all([
        apiClient.getSettingsSchema(),
        apiClient.getSettings(),
      ]);

      const schemaData = schemaResponse.data as SettingsSchema;
      const settingsData = settingsResponse.data as SavedSettings;

      setSchema(schemaData);
      setSettings(settingsData);

      // Build formValues from saved settings
      const formVals: Record<string, Record<string, any>> = {};
      settingsData.sections.forEach((section) => {
        formVals[section.section] = {};
        section.settings.forEach((setting) => {
          // Parse JSON values
          let value = setting.value;
          if (typeof value === 'string') {
            try {
              value = JSON.parse(value);
            } catch {
              // Not JSON, keep as string
            }
          }
          formVals[section.section][setting.key] = value !== undefined ? value : setting.default_value;
        });
      });

      setFormValues(formVals);
    } catch (error: any) {
      setMessage({
        type: 'error',
        text: `Failed to load settings: ${error.message}`,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleFieldChange = (section: string, key: string, value: any) => {
    setFormValues((prev) => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value,
      },
    }));
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setMessage(null);

      // Flatten formValues for API
      const updates: Record<string, any> = {};
      Object.entries(formValues).forEach(([section, fields]) => {
        Object.entries(fields).forEach(([key, value]) => {
          updates[`${section}.${key}`] = value;
        });
      });

      const response = await apiClient.updateSettings(updates);

      if (response.success) {
        setMessage({
          type: 'success',
          text: 'Settings saved successfully',
        });
        // Refresh settings to confirm changes
        setTimeout(() => fetchSettingsData(), 1000);
      } else {
        setMessage({
          type: 'error',
          text: response.message || 'Failed to save settings',
        });
      }
    } catch (error: any) {
      setMessage({
        type: 'error',
        text: `Error saving settings: ${error.response?.data?.message || error.message}`,
      });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (!settings) return;
    const formVals: Record<string, Record<string, any>> = {};
    settings.sections.forEach((section) => {
      formVals[section.section] = {};
      section.settings.forEach((setting) => {
        formVals[section.section][setting.key] = setting.value || setting.default_value;
      });
    });
    setFormValues(formVals);
  };

  const handleSaveProfile = async () => {
    try {
      setMessage(null);
      // TODO: Implement API call to save profile
      // const response = await apiClient.updateProfile(profileData);
      // For now, just show success message
      setMessage({
        type: 'success',
        text: 'Profile would be saved (API endpoint pending)',
      });
    } catch (error: any) {
      setMessage({
        type: 'error',
        text: error.message || 'Failed to save profile',
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading settings...</p>
        </div>
      </div>
    );
  }

  if (!schema || !settings) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          Failed to load settings. Please try again.
        </div>
      </div>
    );
  }

  const currentSection = schema.sections
    .filter((s) => !['botSettings', 'backtesting', 'bot_settings'].includes(s.section.toLowerCase()))
    .find((s) => s.section === activeSection);

  return (
    <div className="bg-gradient-to-br from-slate-900 to-slate-800 min-h-screen">
      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white">Bot Settings</h1>
          <p className="text-gray-400 mt-2">
            Configure bot behavior, backtesting parameters, and connection settings
          </p>
        </div>

      {/* Message Display */}
      {message && (
        <div
          className={`mb-6 px-4 py-3 rounded border ${
            message.type === 'success'
              ? 'bg-green-900 border-green-700 text-green-100'
              : 'bg-red-900 border-red-700 text-red-100'
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Sidebar Navigation */}
        <div className="lg:col-span-1">
          <div className="bg-slate-800 rounded-lg shadow border border-slate-700">
            <nav className="space-y-1">
              {/* Profile Section (Always First) */}
              <button
                onClick={() => setActiveSection('profile')}
                className={`w-full text-left px-4 py-3 text-sm font-medium transition-colors ${
                  activeSection === 'profile'
                    ? 'bg-blue-600 text-white border-l-4 border-blue-400'
                    : 'text-gray-300 hover:bg-slate-700 hover:text-white'
                }`}
              >
                <div className="font-semibold">👤 Profile</div>
                <div className="text-xs opacity-75">Account & Avatar</div>
              </button>

              {/* dYdX Key Management Section */}
              <button
                onClick={() => setActiveSection('dydx_keys')}
                className={`w-full text-left px-4 py-3 text-sm font-medium transition-colors ${
                  activeSection === 'dydx_keys'
                    ? 'bg-blue-600 text-white border-l-4 border-blue-400'
                    : 'text-gray-300 hover:bg-slate-700 hover:text-white'
                }`}
              >
                <div className="font-semibold">🔑 dYdX Keys</div>
                <div className="text-xs opacity-75">Testnet & Mainnet</div>
              </button>

              {/* System Settings Sections - Exclude Bot & Backtesting (moved to Strategies) */}
              {schema.sections
                .filter((section) => 
                  !['botSettings', 'backtesting', 'bot_settings'].includes(section.section.toLowerCase())
                )
                .map((section) => (
                <button
                  key={section.section}
                  onClick={() => setActiveSection(section.section)}
                  className={`w-full text-left px-4 py-3 text-sm font-medium transition-colors ${
                    activeSection === section.section
                      ? 'bg-blue-600 text-white border-l-4 border-blue-400'
                      : 'text-gray-300 hover:bg-slate-700 hover:text-white'
                  }`}
                >
                  <div className="font-semibold">{section.title}</div>
                  <div className="text-xs opacity-75">{section.description}</div>
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* Settings Form */}
        <div className="lg:col-span-3">
          {/* Profile Settings Panel */}
          {activeSection === 'profile' && (
            <ProfileSettings onSave={handleSaveProfile} />
          )}

          {/* dYdX Key Management Panel */}
          {activeSection === 'dydx_keys' && (
            <DYDXKeyManager />
          )}

          {/* Bot Settings Panel */}
          {currentSection && (
            <div className="bg-slate-800 rounded-lg shadow p-6 border border-slate-700">
              {/* Section Header */}
              <div className="mb-6">
                <h2 className="text-2xl font-bold text-white">{currentSection.title}</h2>
                <p className="text-gray-400 mt-1">{currentSection.description}</p>
              </div>

              {/* Form Fields */}
              <div className="space-y-6">
                {currentSection.fields.map((field) => {
                  const value = formValues[activeSection]?.[field.key] ?? field.default_value;

                  return (
                    <div key={field.key} className="border-b border-slate-700 pb-6 last:border-b-0">
                      <label className="block">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="font-semibold text-white">{field.label}</span>
                          {field.required && <span className="text-red-500">*</span>}
                        </div>
                        <p className="text-sm text-gray-400 mb-3">{field.description}</p>

                        {/* Text/Number Input */}
                        {(field.value_type === 'string' || field.value_type === 'float' || field.value_type === 'int') &&
                          !field.options && (
                            <input
                              type={
                                field.value_type === 'float' || field.value_type === 'int'
                                  ? 'number'
                                  : 'text'
                              }
                              value={value}
                              onChange={(e) =>
                                handleFieldChange(
                                  activeSection,
                                  field.key,
                                  field.value_type === 'float'
                                    ? parseFloat(e.target.value)
                                    : field.value_type === 'int'
                                    ? parseInt(e.target.value)
                                    : e.target.value
                                )
                              }
                              step={field.value_type === 'float' ? '0.01' : undefined}
                              min={field.min_value}
                              max={field.max_value}
                              placeholder={field.placeholder}
                              className="w-full px-4 py-2 bg-slate-700 border border-slate-600 text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-500"
                            />
                          )}

                        {/* Select Dropdown */}
                        {field.options && (
                          <select
                            value={value}
                            onChange={(e) => handleFieldChange(activeSection, field.key, e.target.value)}
                            className="w-full px-4 py-2 bg-slate-700 border border-slate-600 text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                          >
                            {field.options.map((option) => (
                              <option key={option} value={option}>
                                {option}
                              </option>
                            ))}
                          </select>
                        )}

                        {/* Checkbox */}
                        {field.value_type === 'boolean' && (
                          <label className="flex items-center gap-3 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={value || false}
                              onChange={(e) => handleFieldChange(activeSection, field.key, e.target.checked)}
                              className="w-5 h-5 text-blue-600 border-slate-600 rounded focus:ring-2 focus:ring-blue-500"
                            />
                            <span className="text-gray-300">
                              {value ? 'Enabled' : 'Disabled'}
                            </span>
                          </label>
                        )}

                        {/* Constraints */}
                        {field.min_value !== undefined || field.max_value !== undefined ? (
                          <p className="text-xs text-gray-500 mt-2">
                            {field.min_value !== undefined && `Min: ${field.min_value}`}
                            {field.min_value !== undefined && field.max_value !== undefined && ' | '}
                            {field.max_value !== undefined && `Max: ${field.max_value}`}
                          </p>
                        ) : null}
                      </label>
                    </div>
                  );
                })}
              </div>

              {/* Action Buttons */}
              <div className="mt-8 flex gap-3 pt-6 border-t border-slate-700">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="px-6 py-2 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
                <button
                  onClick={handleReset}
                  disabled={saving}
                  className="px-6 py-2 bg-slate-700 text-white font-semibold rounded-lg hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Reset
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Info Box */}
      <div className="mt-8 p-4 bg-slate-800 border border-slate-700 rounded-lg">
        <h3 className="font-semibold text-blue-400 mb-2">⚠️ Important Notes</h3>
        <ul className="text-sm text-gray-300 space-y-1 ml-4 list-disc">
          <li>Changes to bot settings take effect on the next trading cycle</li>
          <li>Sensitive settings like mnemonic phrases are stored securely</li>
          <li>Always test settings changes in testnet mode first</li>
          <li>Backtest settings only affect simulations, not live trading</li>
        </ul>
      </div>
      </div>
    </div>
  );
}
