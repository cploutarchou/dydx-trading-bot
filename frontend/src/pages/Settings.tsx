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

import { Loader } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import apiClient from '../api';
import { AuthSettingsComponent } from '../components/AuthSettings';
import { DYDXKeyManager } from '../components/DYDXKeyManager';
import { ProfileSettings } from '../components/ProfileSettings';

type SettingValue = string | number | boolean | null | undefined | Record<string, unknown> | unknown[];

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const getApiErrorMessage = (error: unknown, fallback: string): string => {
  if (error instanceof Error) {
    return error.message;
  }

  if (isRecord(error) && isRecord(error.response) && isRecord(error.response.data)) {
    const apiMessage = error.response.data.message;
    if (typeof apiMessage === 'string' && apiMessage.trim().length > 0) {
      return apiMessage;
    }
  }

  return fallback;
};

interface SettingField {
  key: string;
  label: string;
  description: string;
  value_type: string;
  default_value: SettingValue;
  required: boolean;
  value?: SettingValue;
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

type FieldErrors = Record<string, Record<string, string>>;

interface SidebarSectionItem {
  section: string;
  title: string;
  description: string;
}

interface PendingFocusTarget {
  section: string;
  fieldKey: string;
}

const SETTINGS_LAST_SECTION_KEY = 'settings:last-section';

const getSettingsFieldDomId = (section: string, fieldKey: string): string =>
  `settings-${section}-${fieldKey}`.replace(/[^a-zA-Z0-9_-]/g, '-');

const getSettingsFieldRefKey = (section: string, fieldKey: string): string => `${section}.${fieldKey}`;

const MANUAL_SECTION_IDS = new Set([
  'profile',
  'dydx_keys',
  'security',
  'botsettings',
  'backtesting',
  'bot_settings',
]);

const parseFieldInputValue = (field: SettingField, rawValue: string): SettingValue => {
  if (field.value_type === 'float') {
    if (rawValue.trim() === '') return undefined;
    const parsed = Number.parseFloat(rawValue);
    return Number.isFinite(parsed) ? parsed : undefined;
  }

  if (field.value_type === 'int' || field.value_type === 'integer') {
    if (rawValue.trim() === '') return undefined;
    const parsed = Number.parseInt(rawValue, 10);
    return Number.isFinite(parsed) ? parsed : undefined;
  }

  return rawValue;
};

const isEmptySettingValue = (value: SettingValue): boolean => {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim().length === 0;
  if (Array.isArray(value)) return value.length === 0;
  return false;
};

const normalizeSettingValue = (value: unknown): unknown => {
  if (value === undefined) return '__undefined__';
  if (Array.isArray(value)) return value.map((item) => normalizeSettingValue(item));
  if (typeof value === 'object' && value !== null) {
    return Object.keys(value as Record<string, unknown>)
      .sort()
      .reduce<Record<string, unknown>>((acc, key) => {
        acc[key] = normalizeSettingValue((value as Record<string, unknown>)[key]);
        return acc;
      }, {});
  }
  return value;
};

const serializeFormValues = (values: Record<string, Record<string, SettingValue>>): string =>
  JSON.stringify(
    Object.keys(values)
      .sort()
      .reduce<Record<string, unknown>>((acc, sectionKey) => {
        const fields = values[sectionKey] || {};
        acc[sectionKey] = Object.keys(fields)
          .sort()
          .reduce<Record<string, unknown>>((fieldAcc, fieldKey) => {
            fieldAcc[fieldKey] = normalizeSettingValue(fields[fieldKey]);
            return fieldAcc;
          }, {});
        return acc;
      }, {})
  );

const validateFieldValue = (field: SettingField, value: SettingValue): string | null => {
  if (field.required && isEmptySettingValue(value)) {
    return `${field.label} is required.`;
  }

  if ((field.value_type === 'float' || field.value_type === 'int' || field.value_type === 'integer') &&
    value !== undefined && value !== null && value !== '') {
    const numericValue = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(numericValue)) {
      return `${field.label} must be a valid number.`;
    }
    if (field.min_value !== undefined && numericValue < field.min_value) {
      return `${field.label} must be at least ${field.min_value}.`;
    }
    if (field.max_value !== undefined && numericValue > field.max_value) {
      return `${field.label} must be at most ${field.max_value}.`;
    }
  }

  if (field.options && value !== undefined && value !== null && value !== '') {
    const optionValue = String(value);
    if (!field.options.includes(optionValue)) {
      return `${field.label} must be one of the allowed options.`;
    }
  }

  return null;
};

const buildFieldErrors = (
  sections: SettingSection[],
  values: Record<string, Record<string, SettingValue>>
): FieldErrors => {
  const nextErrors: FieldErrors = {};

  sections.forEach((section) => {
    section.fields.forEach((field) => {
      const value = values[section.section]?.[field.key] ?? field.default_value;
      const error = validateFieldValue(field, value);
      if (!error) return;

      if (!nextErrors[section.section]) {
        nextErrors[section.section] = {};
      }

      nextErrors[section.section][field.key] = error;
    });
  });

  return nextErrors;
};

const hasAnyFieldErrors = (errors: FieldErrors): boolean =>
  Object.values(errors).some((sectionErrors) => Object.keys(sectionErrors).length > 0);

export default function Settings() {
  const [schema, setSchema] = useState<SettingsSchema | null>(null);
  const [settings, setSettings] = useState<SavedSettings | null>(null);
  const [formValues, setFormValues] = useState<Record<string, Record<string, SettingValue>>>({});
  const [initialFormValues, setInitialFormValues] = useState<Record<string, Record<string, SettingValue>>>({});
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);
  const [activeSection, setActiveSection] = useState<string>('profile');
  const [pendingFocusTarget, setPendingFocusTarget] = useState<PendingFocusTarget | null>(null);
  const [sectionSearchQuery, setSectionSearchQuery] = useState('');
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionResult, setConnectionResult] = useState<{
    connected: boolean;
    message: string;
    host?: string;
    port?: number;
    latency_ms?: number;
  } | null>(null);
  const fieldRefs = useRef<Record<string, HTMLInputElement | HTMLSelectElement | null>>({});
  const hasRestoredSectionRef = useRef(false);

  const visibleSchemaSections = useMemo(
    () =>
      (schema?.sections || []).filter(
        (section) => !MANUAL_SECTION_IDS.has(section.section.toLowerCase())
      ),
    [schema]
  );

  const sidebarSections = useMemo<SidebarSectionItem[]>(() => {
    const manualSections: SidebarSectionItem[] = [
      { section: 'profile', title: '👤 Profile', description: 'Account & Avatar' },
      { section: 'dydx_keys', title: '🔑 dYdX Keys', description: 'Testnet & Mainnet' },
      { section: 'security', title: '🛡️ Security', description: '2FA & Session Controls' },
    ];

    return [
      ...manualSections,
      ...visibleSchemaSections.map((section) => ({
        section: section.section,
        title: section.title,
        description: section.description,
      })),
    ];
  }, [visibleSchemaSections]);

  const filteredSidebarSections = useMemo(() => {
    const query = sectionSearchQuery.trim().toLowerCase();
    if (!query) return sidebarSections;

    return sidebarSections.filter((section) =>
      [section.title, section.description, section.section].some((value) =>
        value.toLowerCase().includes(query)
      )
    );
  }, [sectionSearchQuery, sidebarSections]);

  const hasUnsavedChanges = useMemo(
    () => serializeFormValues(formValues) !== serializeFormValues(initialFormValues),
    [formValues, initialFormValues]
  );

  const hasValidationErrors = useMemo(() => hasAnyFieldErrors(fieldErrors), [fieldErrors]);

  useEffect(() => {
    fetchSettingsData();
  }, []);

  useEffect(() => {
    if (hasRestoredSectionRef.current || sidebarSections.length === 0) {
      return;
    }

    hasRestoredSectionRef.current = true;

    try {
      const savedSection = localStorage.getItem(SETTINGS_LAST_SECTION_KEY);
      if (savedSection && sidebarSections.some((section) => section.section === savedSection)) {
        setActiveSection(savedSection);
      }
    } catch (error) {
      console.warn('⚠️ Settings.tsx: Failed to restore last opened section', error);
    }
  }, [sidebarSections]);

  useEffect(() => {
    if (!sidebarSections.some((section) => section.section === activeSection)) {
      return;
    }

    try {
      localStorage.setItem(SETTINGS_LAST_SECTION_KEY, activeSection);
    } catch (error) {
      console.warn('⚠️ Settings.tsx: Failed to persist last opened section', error);
    }
  }, [activeSection, sidebarSections]);

  useEffect(() => {
    if (!pendingFocusTarget || pendingFocusTarget.section !== activeSection) {
      return;
    }

    const refKey = getSettingsFieldRefKey(pendingFocusTarget.section, pendingFocusTarget.fieldKey);
    const fieldElement = fieldRefs.current[refKey];
    if (!fieldElement) {
      return;
    }

    fieldElement.focus();
    fieldElement.scrollIntoView({ block: 'center', behavior: 'smooth' });
    setPendingFocusTarget(null);
  }, [activeSection, pendingFocusTarget]);

  const fetchSettingsData = async () => {
    try {
      setLoading(true);

      // First, try to initialize settings (idempotent - no-op if already initialized)
      try {
        await apiClient.initializeSettings();
      } catch {
        // Initialization might fail if settings already exist, which is fine
      }

      const [schemaResponse, settingsResponse] = await Promise.all([
        apiClient.getSettingsSchema(),
        apiClient.getSettings(),
      ]);

      const schemaData = schemaResponse.data as unknown as SettingsSchema;
      const settingsData = settingsResponse.data as unknown as SavedSettings;

      setSchema(schemaData);
      setSettings(settingsData);

      // Build formValues from saved settings
      const formVals: Record<string, Record<string, SettingValue>> = {};
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
          formVals[section.section][setting.key] =
            value !== undefined ? value : setting.default_value;
        });
      });

      setFormValues(formVals);
      setInitialFormValues(formVals);
      setFieldErrors(buildFieldErrors(schemaData.sections, formVals));
    } catch (error: unknown) {
      setMessage({
        type: 'error',
        text: `Failed to load settings: ${getApiErrorMessage(error, 'Unknown error')}`,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleFieldChange = (section: string, key: string, value: SettingValue) => {
    setFormValues((prev) => {
      const nextValues = {
        ...prev,
        [section]: {
          ...prev[section],
          [key]: value,
        },
      };

      if (schema?.sections) {
        setFieldErrors(buildFieldErrors(schema.sections, nextValues));
      }

      return nextValues;
    });
  };

  const handleSave = async () => {
    if (!schema) return;

    const nextErrors = buildFieldErrors(schema.sections, formValues);
    setFieldErrors(nextErrors);

    if (hasAnyFieldErrors(nextErrors)) {
      const firstInvalidSection = schema.sections.find(
        (section) => nextErrors[section.section] && Object.keys(nextErrors[section.section]).length > 0
      );
      if (firstInvalidSection) {
        const firstInvalidFieldKey = Object.keys(nextErrors[firstInvalidSection.section] || {})[0];
        if (firstInvalidFieldKey) {
          setPendingFocusTarget({
            section: firstInvalidSection.section,
            fieldKey: firstInvalidFieldKey,
          });
        }
        setActiveSection(firstInvalidSection.section);
      }
      setMessage({
        type: 'error',
        text: 'Please fix validation errors before saving your changes.',
      });
      return;
    }

    if (!hasUnsavedChanges) {
      setMessage({ type: 'success', text: 'No changes to save.' });
      return;
    }

    try {
      setSaving(true);
      setMessage(null);

      // Flatten formValues for API
      const updates: Record<string, SettingValue> = {};
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
        setInitialFormValues(formValues);
        // Refresh settings to confirm changes
        setTimeout(() => fetchSettingsData(), 1000);
      } else {
        setMessage({
          type: 'error',
          text: response.message || 'Failed to save settings',
        });
      }
    } catch (error: unknown) {
      setMessage({
        type: 'error',
        text: `Error saving settings: ${getApiErrorMessage(error, 'Unknown error')}`,
      });
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    try {
      setTestingConnection(true);
      setConnectionResult(null);
      const response = await apiClient.testRedisConnection();
      if (response.success && response.data) {
        const data = response.data as {
          connected: boolean;
          message: string;
          host?: string;
          port?: number;
          latency_ms?: number;
        };
        setConnectionResult(data);
      } else {
        setConnectionResult({ connected: false, message: response.message || 'Test failed' });
      }
    } catch (error: unknown) {
      setConnectionResult({
        connected: false,
        message: getApiErrorMessage(error, 'Connection test failed'),
      });
    } finally {
      setTestingConnection(false);
    }
  };

  const handleReset = () => {
    if (!schema) return;
    setFormValues(initialFormValues);
    setFieldErrors(buildFieldErrors(schema.sections, initialFormValues));
    setMessage(null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96 bg-slate-900 rounded-lg border border-slate-700">
        <div className="text-center">
          <Loader className="w-12 h-12 animate-spin text-blue-500 mx-auto" />
          <p className="mt-4 text-slate-300">Loading settings...</p>
        </div>
      </div>
    );
  }

  if (!schema || !settings) {
    return (
      <div className="p-8 min-h-screen bg-slate-900">
        <div className="bg-red-900 border border-red-700 text-red-100 px-4 py-3 rounded">
          Failed to load settings. Please try again.
          <button
            type="button"
            onClick={fetchSettingsData}
            className="ml-4 text-sm underline underline-offset-2 hover:text-white"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const currentSection = visibleSchemaSections.find((s) => s.section === activeSection);

  return (
    <div className="bg-linear-to-br from-slate-900 to-slate-800 min-h-screen">
      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white">Settings</h1>
          <p className="text-gray-400 mt-2">
            Manage your profile, keys, and system-wide configuration
          </p>
        </div>

        {/* Message Display */}
        {message && (
          <div
            role={message.type === 'success' ? 'status' : 'alert'}
            aria-live={message.type === 'success' ? 'polite' : 'assertive'}
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
              <div className="p-4 border-b border-slate-700">
                <label htmlFor="settings-section-search" className="sr-only">
                  Search settings sections
                </label>
                <input
                  id="settings-section-search"
                  type="search"
                  value={sectionSearchQuery}
                  onChange={(e) => setSectionSearchQuery(e.target.value)}
                  placeholder="Search sections..."
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-500"
                />
              </div>
              <nav className="space-y-1">
                {filteredSidebarSections.length === 0 ? (
                  <div className="px-4 py-6 text-sm text-slate-400">
                    No settings sections match your search.
                  </div>
                ) : (
                  filteredSidebarSections.map((section) => (
                    <button
                      key={section.section}
                      type="button"
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
                  ))
                )}
              </nav>
            </div>
          </div>

          {/* Settings Form */}
          <div className="lg:col-span-3">
            {/* Profile Settings Panel */}
            {activeSection === 'profile' && <ProfileSettings />}

            {/* dYdX Key Management Panel */}
            {activeSection === 'dydx_keys' && <DYDXKeyManager />}

            {/* Security & Session Management Panel */}
            {activeSection === 'security' && (
              <AuthSettingsComponent
                defaultTab="security"
                visibleTabs={['security', 'sessions']}
                showHeader={false}
              />
            )}

            {/* Bot Settings Panel */}
            {currentSection && (
              <div className="bg-slate-800 rounded-lg shadow p-6 border border-slate-700">
                {/* Section Header */}
                <div className="mb-6">
                  <h2 className="text-2xl font-bold text-white">{currentSection.title}</h2>
                  <p className="text-gray-400 mt-1">{currentSection.description}</p>
                  <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
                    <span
                      className={`px-3 py-1 rounded-full border ${
                        hasUnsavedChanges
                          ? 'bg-yellow-900/40 border-yellow-700 text-yellow-200'
                          : 'bg-slate-700 border-slate-600 text-slate-300'
                      }`}
                    >
                      {hasUnsavedChanges ? 'Unsaved changes' : 'All changes saved'}
                    </span>
                    {hasValidationErrors && (
                      <span className="px-3 py-1 rounded-full border bg-red-900/40 border-red-700 text-red-200">
                        Validation errors need attention
                      </span>
                    )}
                  </div>
                </div>

                {/* Form Fields */}
                <div className="space-y-6">
                  {currentSection.fields.map((field) => {
                    const value = formValues[activeSection]?.[field.key] ?? field.default_value;
                    const inputValue = typeof value === 'string' || typeof value === 'number' ? value : '';
                    const selectValue =
                      typeof value === 'string' || typeof value === 'number' ? String(value) : '';
                    const fieldDomId = getSettingsFieldDomId(activeSection, field.key);
                    const fieldRefKey = getSettingsFieldRefKey(activeSection, field.key);
                    const errorMessage = fieldErrors[activeSection]?.[field.key];

                    return (
                      <div
                        key={field.key}
                        className="border-b border-slate-700 pb-6 last:border-b-0"
                      >
                        <label className="block">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="font-semibold text-white">{field.label}</span>
                            {field.required && <span className="text-red-500">*</span>}
                          </div>
                          <p className="text-sm text-gray-400 mb-3">{field.description}</p>

                          {/* Text/Number Input */}
                          {(field.value_type === 'string' ||
                            field.value_type === 'float' ||
                            field.value_type === 'int' ||
                            field.value_type === 'integer') &&
                            !field.options && (
                              <input
                                id={fieldDomId}
                                ref={(element) => {
                                  fieldRefs.current[fieldRefKey] = element;
                                }}
                                type={
                                  field.value_type === 'float' ||
                                  field.value_type === 'int' ||
                                  field.value_type === 'integer'
                                    ? 'number'
                                    : 'text'
                                }
                                aria-invalid={!!errorMessage}
                                aria-describedby={errorMessage ? `${fieldDomId}-error` : undefined}
                                value={inputValue}
                                onChange={(e) =>
                                  handleFieldChange(
                                    activeSection,
                                    field.key,
                                    parseFieldInputValue(field, e.target.value)
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
                              id={fieldDomId}
                              ref={(element) => {
                                fieldRefs.current[fieldRefKey] = element;
                              }}
                              aria-invalid={!!errorMessage}
                              aria-describedby={errorMessage ? `${fieldDomId}-error` : undefined}
                              value={selectValue}
                              onChange={(e) =>
                                handleFieldChange(activeSection, field.key, e.target.value)
                              }
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
                                id={fieldDomId}
                                ref={(element) => {
                                  fieldRefs.current[fieldRefKey] = element;
                                }}
                                type="checkbox"
                                aria-invalid={!!errorMessage}
                                aria-describedby={errorMessage ? `${fieldDomId}-error` : undefined}
                                checked={Boolean(value)}
                                onChange={(e) =>
                                  handleFieldChange(activeSection, field.key, e.target.checked)
                                }
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
                              {field.min_value !== undefined &&
                                field.max_value !== undefined &&
                                ' | '}
                              {field.max_value !== undefined && `Max: ${field.max_value}`}
                            </p>
                          ) : null}

                          {errorMessage && (
                            <p id={`${fieldDomId}-error`} className="text-xs text-red-300 mt-2">
                              {errorMessage}
                            </p>
                          )}
                        </label>
                      </div>
                    );
                  })}
                </div>

                {/* Action Buttons */}
                <div className="mt-8 flex flex-col gap-4 pt-6 border-t border-slate-700">
                  <div className="flex gap-3">
                    <button
                      type="button"
                      onClick={handleSave}
                      disabled={saving || !hasUnsavedChanges}
                      className="px-6 py-2 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {saving ? 'Saving...' : 'Save Changes'}
                    </button>
                    <button
                      type="button"
                      onClick={handleReset}
                      disabled={saving || !hasUnsavedChanges}
                      className="px-6 py-2 bg-slate-700 text-white font-semibold rounded-lg hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      Reset
                    </button>
                    {activeSection === 'redis' && (
                      <button
                        type="button"
                        onClick={handleTestConnection}
                        disabled={testingConnection || saving}
                        className="px-6 py-2 bg-teal-700 text-white font-semibold rounded-lg hover:bg-teal-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        {testingConnection ? 'Testing…' : '⚡ Test Connection'}
                      </button>
                    )}
                  </div>

                  {/* Connection test result — only shown in the Redis section */}
                  {activeSection === 'redis' && connectionResult && (
                    <div
                      className={`flex items-start gap-3 px-4 py-3 rounded-lg border text-sm ${
                        connectionResult.connected
                          ? 'bg-green-900/30 border-green-700 text-green-200'
                          : 'bg-red-900/30 border-red-700 text-red-200'
                      }`}
                    >
                      <span className="text-lg">{connectionResult.connected ? '✅' : '❌'}</span>
                      <div>
                        <p className="font-semibold">
                          {connectionResult.connected ? 'Connected' : 'Connection failed'}
                        </p>
                        <p className="opacity-80">{connectionResult.message}</p>
                        {connectionResult.connected &&
                          connectionResult.latency_ms !== undefined && (
                            <p className="opacity-60 text-xs mt-1">
                              {connectionResult.host}:{connectionResult.port} —{' '}
                              {connectionResult.latency_ms} ms
                            </p>
                          )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Info Box */}
        <div className="mt-8 p-4 bg-slate-800 border border-slate-700 rounded-lg">
          <h3 className="font-semibold text-blue-400 mb-2">⚠️ Important Notes</h3>
          <ul className="text-sm text-gray-300 space-y-1 ml-4 list-disc">
            <li>Profile and key changes are saved immediately after confirmation.</li>
            <li>Sensitive credentials are never shown in plain text after storage.</li>
            <li>For live trading, validate all settings in testnet first.</li>
            <li>Runtime strategy controls are available under Strategy Runtime and Bot Manager.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
